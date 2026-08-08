"""Peak hour panel build from the OAG store (Capacity Method v0.4, section 11.1).
Author: Avia Solutions.

Built against a synthetic store shaped like C:\\Avia\\oag.duckdb as it actually is:
one row per OPERATED flight, a week period key, a region file, days_of_op with spaces
as placeholders, HHMM times with no leading zero, and VARCHAR numerics. The real store
is never committed, so the shape is reproduced here and the conventions are asserted.
"""
import pytest

duckdb = pytest.importorskip("duckdb")

from avia_forecast.ingest import oag_peak, oag_store
from avia_forecast.capacity import peakhour as ph
from avia_forecast.config import get


COLS = ["dep_airport", "arr_airport", "local_dep_time", "local_arr_time", "days_of_op",
        "seats", "dep_country", "arr_country", "week", "region", "year", "service_type"]


def make_store(tmp_path, rows, name="oag_test.duckdb"):
    import pandas as pd
    path = tmp_path / name
    df = pd.DataFrame(rows, columns=COLS)
    con = duckdb.connect(str(path))
    con.register("df", df)
    con.execute("CREATE TABLE oag AS SELECT * FROM df")
    con.close()
    return path


def month_rows(dep, arr, dep_t, arr_t, days, seats, week, region, year,
               n_ops, dep_c="GB", arr_c="FR", stype="J"):
    """n_ops rows, one per operated flight, exactly as the store holds them."""
    return [(dep, arr, dep_t, arr_t, days, str(seats), dep_c, arr_c, week, region,
             str(year), stype)] * n_ops


def full_year(dep="AAA", arr="BBB", dep_t="700", arr_t="900", seats=180,
              region="Europe", year=2019, per_day=1, dep_c="GB", arr_c="FR"):
    """A daily service across all twelve monthly period keys."""
    import calendar
    rows = []
    for mth in range(1, 13):
        n = calendar.monthrange(year, mth)[1] * per_day
        rows += month_rows(dep, arr, dep_t, arr_t, "1234567", seats,
                           f"{year}-{mth:02d}", region, year, n, dep_c, arr_c)
    return rows


def _cfg(monkeypatch, filt="service_type = 'J'"):
    m = dict(oag_peak.DEFAULT_MAPPING)
    monkeypatch.setattr(oag_peak, "mapping", lambda: m)
    monkeypatch.setattr(oag_peak, "row_filter", lambda: filt)
    return m


# --------------------------------------------------------------------------
# Store conventions
# --------------------------------------------------------------------------

def test_period_span_reads_every_key_shape():
    assert oag_store.period_span("2019-06") == ("2019-06-01", "2019-06-30")
    assert oag_store.period_span("2019-02") == ("2019-02-01", "2019-02-28")
    assert oag_store.period_span("2020-02") == ("2020-02-01", "2020-02-29")
    assert oag_store.period_span("2019") == ("2019-01-01", "2019-12-31")
    assert oag_store.period_span("2019-H1") == ("2019-01-01", "2019-06-30")
    assert oag_store.period_span("2019-H2") == ("2019-07-01", "2019-12-31")
    assert oag_store.period_span("2019-07p01") == ("2019-07-01", "2019-07-15")
    assert oag_store.period_span("2019-07p16") == ("2019-07-16", "2019-07-31")
    assert oag_store.period_span("2019-05-27") == ("2019-05-27", "2019-06-02")


def test_hhmm_handles_the_missing_leading_zero():
    """"700" is 07:00. Splitting without padding would read hour 70 and put the
    morning bank in an hour that does not exist."""
    con = duckdb.connect()
    sql = oag_store.hhmm_sql("t")
    con.execute("CREATE TABLE x AS SELECT * FROM (VALUES ('700'),('1430'),('0630'),('7:00')) v(t)")
    got = [r[0] for r in con.execute(f"SELECT {sql} FROM x").fetchall()]
    assert got == [7, 14, 6, 7]


def test_preferred_tiling_prefers_months_then_halves_then_annual(tmp_path):
    import calendar
    rows = full_year(region="Europe", year=2019)
    # a competing legacy annual key and both halves for the same region-year
    rows += month_rows("AAA", "BBB", "700", "900", "1234567", 180, "2019", "Europe", 2019, 5)
    rows += month_rows("AAA", "BBB", "700", "900", "1234567", 180, "2019-H1", "Europe", 2019, 5)
    rows += month_rows("AAA", "BBB", "700", "900", "1234567", 180, "2019-H2", "Europe", 2019, 5)
    con = duckdb.connect(str(make_store(tmp_path, rows)), read_only=True)
    pref = oag_store.preferred_tilings(con, "oag")
    con.close()
    keys = pref[("Europe", 2019)]
    assert len(keys) == 12 and all(len(k) == 7 for k in keys)
    assert "2019" not in keys and "2019-H1" not in keys


def test_home_region_is_where_the_airport_has_most_rows(tmp_path):
    rows = full_year(region="Europe") + full_year(region="North America", per_day=1)[:50]
    con = duckdb.connect(str(make_store(tmp_path, rows)), read_only=True)
    home = oag_store.home_regions(con, "oag")
    con.close()
    assert home["AAA"] == "Europe"


# --------------------------------------------------------------------------
# Panel build
# --------------------------------------------------------------------------

def test_one_row_per_operated_flight_is_not_expanded(tmp_path, monkeypatch):
    """The store already holds one row per operation. Expanding on the effective
    window, as the first version did, multiplied every count."""
    _cfg(monkeypatch)
    path = make_store(tmp_path, full_year(per_day=2))
    obs, rep = oag_peak.build_panel(path, airports=["AAA"], years=[2019])
    assert len(obs) == 1
    o = obs[0]
    # 2 departures a day plus 2 arrivals a day at BBB; AAA sees only its departures
    assert o.annual_mvts == pytest.approx(365 * 2)
    assert o.annual_pax_m == pytest.approx(365 * 2 * 180 * 0.82 / 1e6)


def test_arrivals_and_departures_are_one_combined_flow(tmp_path, monkeypatch):
    """The runway constraint is ATM. Reading dep_airport alone halves the movements
    and an airport would never appear constrained."""
    _cfg(monkeypatch)
    # AAA departs at 07:00 and receives BBB's arrivals at 09:00
    rows = full_year(dep="AAA", arr="BBB", dep_t="700", arr_t="900") \
         + full_year(dep="BBB", arr="AAA", dep_t="1200", arr_t="1400")
    path = make_store(tmp_path, rows)
    obs, _ = oag_peak.build_panel(path, airports=["AAA", "BBB"], years=[2019])
    a = {o.iata: o for o in obs}
    assert a["AAA"].annual_mvts == pytest.approx(365 * 2)      # departures + arrivals
    assert a["BBB"].annual_mvts == pytest.approx(365 * 2)


def test_the_combined_peak_is_not_twice_the_departure_peak(tmp_path, monkeypatch):
    """Arrivals and departures bank at different times, so the combined peak is the
    max of the combined flow and not the sum of the two maxima."""
    _cfg(monkeypatch)
    rows = full_year(dep="AAA", arr="BBB", dep_t="700", arr_t="900", per_day=3) \
         + full_year(dep="BBB", arr="AAA", dep_t="1200", arr_t="1400", per_day=1)
    path = make_store(tmp_path, rows)
    obs, _ = oag_peak.build_panel(path, airports=["AAA"], years=[2019])
    o = obs[0]
    # AAA: 3 departures at 07:00, 1 arrival at 14:00. Peak hour is 3, not 4.
    assert o.peak_hour_mvts == pytest.approx(3.0)


def test_cross_region_duplication_is_removed(tmp_path, monkeypatch):
    """A flight spanning two regions is listed in both files. Only the home file is
    read: at Heathrow that is 678 departures a day against 934 raw."""
    _cfg(monkeypatch)
    rows = full_year(region="Europe") + full_year(region="North America")
    path = make_store(tmp_path, rows)
    obs, _ = oag_peak.build_panel(path, airports=["AAA"], years=[2019])
    assert obs[0].annual_mvts == pytest.approx(365)          # not 730


def test_overlapping_period_tilings_are_not_summed(tmp_path, monkeypatch):
    _cfg(monkeypatch)
    rows = full_year()
    rows += month_rows("AAA", "BBB", "700", "900", "1234567", 180, "2019", "Europe", 2019, 365)
    path = make_store(tmp_path, rows)
    obs, _ = oag_peak.build_panel(path, airports=["AAA"], years=[2019])
    assert obs[0].annual_mvts == pytest.approx(365)          # monthly tiling only


def test_days_of_operation_with_space_placeholders(tmp_path, monkeypatch):
    """The store writes patterns as "12345 7" and "1 3 5 7". A day is matched by the
    presence of its ISO digit, so the spaces are harmless."""
    _cfg(monkeypatch)
    import calendar
    rows = []
    for mth in range(1, 13):
        n = sum(1 for d in range(1, calendar.monthrange(2019, mth)[1] + 1)
                if __import__("datetime").date(2019, mth, d).isoweekday() in (1, 3, 5, 7))
        rows += month_rows("AAA", "BBB", "700", "900", "1 3 5 7", 180,
                           f"2019-{mth:02d}", "Europe", 2019, n)
    path = make_store(tmp_path, rows)
    obs, _ = oag_peak.build_panel(path, airports=["AAA"], years=[2019],
                                  min_hours_covered=0.5)
    o = obs[0]
    assert 200 < o.annual_mvts < 220                          # circa 209 days a year


def test_service_type_filter_is_applied(tmp_path, monkeypatch):
    _cfg(monkeypatch)
    freight = [(r[0], r[1], "800", r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], "F")
               for r in full_year()]
    rows = full_year() + freight
    path = make_store(tmp_path, rows)
    obs, _ = oag_peak.build_panel(path, airports=["AAA"], years=[2019])
    assert obs[0].annual_mvts == pytest.approx(365)           # freight rows excluded


def test_varchar_numerics_do_not_break_the_build(tmp_path, monkeypatch):
    _cfg(monkeypatch)
    rows = full_year()
    rows.append(("AAA", "BBB", "700", "900", "1234567", "n/a", "GB", "FR",
                 "2019-06", "Europe", "2019", "J"))
    path = make_store(tmp_path, rows)
    obs, _ = oag_peak.build_panel(path, airports=["AAA"], years=[2019])
    assert obs and obs[0].annual_pax_m > 0


def test_incomplete_years_are_dropped_not_ranked(tmp_path, monkeypatch):
    _cfg(monkeypatch)
    import calendar
    rows = []
    for mth in (1, 2, 3):
        n = calendar.monthrange(2019, mth)[1]
        rows += month_rows("AAA", "BBB", "700", "900", "1234567", 180,
                           f"2019-{mth:02d}", "Europe", 2019, n)
    path = make_store(tmp_path, rows)
    obs, rep = oag_peak.build_panel(path, airports=["AAA"], years=[2019])
    assert obs == []
    assert rep.dropped_incomplete and rep.dropped_incomplete[0][0] == "AAA"


def test_convention_and_basis_travel_with_the_panel(tmp_path, monkeypatch):
    _cfg(monkeypatch)
    path = make_store(tmp_path, full_year(per_day=2))
    obs, rep = oag_peak.build_panel(path, airports=["AAA"], years=[2019])
    # The window is part of the convention name. Failure mode 4 in this module's
    # docstring is mixing conventions, and a bare "busy_30th" cannot say whether the
    # peak was measured on a clock hour or a rolling one.
    expected = f"busy_30th/{get('peak_hour.window', 'clock_hour')}"
    assert rep.convention == expected
    assert all(o.convention == expected for o in obs)
    assert any(w in rep.notes for w in oag_peak.PEAK_WINDOWS)
    assert "seats" in rep.notes and "nothing expanded" in rep.notes
    assert "row filter" in rep.notes


def test_constrained_airports_are_flagged_then_excluded_from_the_fit(tmp_path, monkeypatch):
    _cfg(monkeypatch)
    path = make_store(tmp_path, full_year(per_day=2))
    obs, _ = oag_peak.build_panel(path, airports=["AAA"], years=[2019], constrained={"AAA"})
    assert obs[0].constrained
    kept, excluded = ph.filter_sample(obs, obs[0].convention)
    assert "AAA" not in {o.iata for o in kept} and excluded["constrained"]


def test_flag_constrained_uses_the_book_threshold():
    assert oag_peak.flag_constrained({"LHR": 90.3, "BRS": 12.0},
                                     {"LHR": 92.0, "BRS": 30.0}) == {"LHR"}


def test_missing_store_fails_with_a_useful_message(tmp_path, monkeypatch):
    _cfg(monkeypatch)
    with pytest.raises(FileNotFoundError):
        oag_peak.build_panel(tmp_path / "not_here.duckdb")


def test_store_path_resolution_order(monkeypatch, tmp_path):
    monkeypatch.setenv("AVIA_OAG_STORE", str(tmp_path / "from_env.duckdb"))
    assert oag_peak.store_path(tmp_path / "explicit.duckdb").name == "explicit.duckdb"
    assert oag_peak.store_path(None).name == "from_env.duckdb"
    monkeypatch.delenv("AVIA_OAG_STORE", raising=False)
    assert str(oag_peak.store_path(None)).endswith("oag.duckdb")


def test_no_store_configured_anywhere_says_where_to_set_it(monkeypatch):
    monkeypatch.delenv("AVIA_OAG_STORE", raising=False)
    monkeypatch.setattr(oag_peak, "_load", lambda name: {"oag_schedules": {"store_path": ""}})
    with pytest.raises(FileNotFoundError) as e:
        oag_peak.store_path(None)
    assert "AVIA_OAG_STORE" in str(e.value)


def test_a_clock_panel_and_a_rolling_panel_are_not_interchangeable(tmp_path, monkeypatch):
    """Two conventions must not be pooled into one fit.

    The peak measured on a rolling hour is at or above the clock-hour figure, so
    mixing them would put a systematic step into the sample and the elasticity would
    absorb it. filter_sample is the guard, and it works by exact name.
    """
    _cfg(monkeypatch)
    path = make_store(tmp_path, full_year(per_day=2))
    clock, _ = oag_peak.build_panel(path, airports=["AAA"], years=[2019],
                                    window="clock_hour")
    roll, _ = oag_peak.build_panel(path, airports=["AAA"], years=[2019],
                                   window="rolling_60_step_10")
    assert clock and roll
    assert clock[0].convention != roll[0].convention

    kept, excluded = ph.filter_sample(clock + roll, clock[0].convention)
    assert excluded.get("convention"), "the rolling rows must be excluded by name"
    assert all(o.convention == clock[0].convention for o in kept)

    # And the invariant: a rolling peak is never below the clock-hour peak.
    assert roll[0].peak_hour_pax >= clock[0].peak_hour_pax - 1e-6


def test_an_unknown_window_is_refused_by_build_panel(tmp_path, monkeypatch):
    _cfg(monkeypatch)
    path = make_store(tmp_path, full_year(per_day=2))
    with pytest.raises(ValueError):
        oag_peak.build_panel(path, airports=["AAA"], years=[2019], window="rolling")

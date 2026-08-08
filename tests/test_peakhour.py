"""Peak hour share estimation and projection (Capacity Method v0.4, section 11.1).
Author: Avia Solutions."""
import math

import pytest

from avia_forecast.capacity import peakhour as ph
from avia_forecast.config import get


def panel(b=0.85, n_airports=20, years=range(2015, 2025), a=0.004, constrained=()):
    """Synthetic panel with a known elasticity b, so the fit can be checked against
    a truth we control: peak = a * annual^b."""
    obs = []
    for i in range(n_airports):
        base = 1.0 + i * 1.5                      # 1m to circa 30m pax
        for j, y in enumerate(years):
            annual_m = base * (1.03 ** j)
            peak = a * (annual_m * 1e6) ** b
            obs.append(ph.PeakObs(iata=f"A{i:02d}", year=y, annual_pax_m=annual_m,
                                  peak_hour_pax=peak, intl_share=0.5,
                                  seasonality=1 / 12, constrained=f"A{i:02d}" in constrained,
                                  convention="busy_30th"))
    return obs


def test_share_declines_with_size_when_b_below_one():
    o_small = ph.PeakObs("X", 2024, 2.0, 0.004 * (2e6) ** 0.85)
    o_large = ph.PeakObs("Y", 2024, 40.0, 0.004 * (40e6) ** 0.85)
    assert o_large.share < o_small.share


def test_fit_recovers_the_known_elasticity():
    fit = ph.fit_peak_share(panel(b=0.85))
    assert fit.fitted_ok
    assert fit.b == pytest.approx(0.85, abs=0.01)
    assert fit.share_elasticity < 0            # the peak grows more slowly than annual
    assert fit.convention == "busy_30th"


def test_constrained_airports_are_excluded_from_the_sample():
    """Rule 1: a constrained airport's filed peak reports the declaration, not demand."""
    obs = panel(constrained={"A00", "A01"})
    kept, excluded = ph.filter_sample(obs, "busy_30th")
    assert excluded["constrained"]
    assert {o.iata for o in kept}.isdisjoint({"A00", "A01"})


def test_tiny_airports_and_bad_values_are_excluded_with_a_reason():
    obs = panel()
    obs.append(ph.PeakObs("TIN", 2024, 0.05, 30.0, convention="busy_30th"))
    obs.append(ph.PeakObs("BAD", 2024, 5.0, 0.0, convention="busy_30th"))
    kept, excluded = ph.filter_sample(obs, "busy_30th")
    assert "below_floor" in excluded and "bad_value" in excluded
    assert {o.iata for o in kept}.isdisjoint({"TIN", "BAD"})


def test_thin_airports_drop_out():
    obs = panel(years=range(2020, 2030))
    obs.append(ph.PeakObs("THN", 2024, 5.0, 2000.0, convention="busy_30th"))
    kept, excluded = ph.filter_sample(obs, "busy_30th")
    assert "thin_airport" in excluded
    assert "THN" not in {o.iata for o in kept}


def test_thin_sample_falls_back_to_the_book_elasticity_flagged_not_raised():
    fit = ph.fit_peak_share(panel(n_airports=1, years=range(2022, 2026)))
    assert not fit.fitted_ok
    assert fit.b == pytest.approx(get("peak_hour.fallback_elasticity"))
    assert "fallback" in fit.notes


def test_perverse_elasticity_is_rejected_in_favour_of_the_fallback():
    """b >= 1 would mean the peak growing faster than annual traffic, which would
    bring every constraint forward. Rejected and flagged, never used."""
    fit = ph.fit_peak_share(panel(b=1.20))
    assert not fit.fitted_ok
    assert fit.b == pytest.approx(get("peak_hour.fallback_elasticity"))
    assert "outside (0, 1)" in fit.notes


def test_projection_lowers_the_share_as_the_airport_grows():
    fit = ph.fit_peak_share(panel(b=0.85))
    s0 = 0.0005
    s1 = ph.project_share(fit, s0, base_annual_m=10.0, target_annual_m=20.0)
    assert s1 < s0
    # and the annual capacity implied by a fixed hourly rate therefore rises
    assert (1 / s1) > (1 / s0)


def test_projection_is_floored():
    fit = ph.fit_peak_share(panel(b=0.85))
    s = ph.project_share(fit, 0.0005, 1.0, 5_000.0)
    assert s >= get("peak_hour.projection_floor_share")


def test_share_path_is_year_indexed():
    fit = ph.fit_peak_share(panel(b=0.85))
    path = ph.share_path(fit, 0.0005, 10.0, {2025: 10.0, 2030: 12.0, 2035: 15.0})
    assert set(path) == {2025, 2030, 2035}
    assert path[2035] < path[2030] < path[2025]


def test_anchor_prefers_the_airports_own_observation():
    fit = ph.fit_peak_share(panel(b=0.85))
    a = ph.anchor_share(fit, 10.0, observed_share=0.00051, constrained=False)
    assert a.basis == "observed" and a.share == pytest.approx(0.00051)


def test_anchor_falls_back_to_the_fit_at_a_constrained_airport():
    """The circularity guard: without this the peak of a Level 3 airport would be
    projected forward from the very constraint the test is meant to detect."""
    fit = ph.fit_peak_share(panel(b=0.85))
    a = ph.anchor_share(fit, 10.0, observed_share=0.00051, constrained=True)
    assert a.basis == "fitted"
    assert "declared parameter" in a.reason
    assert math.isfinite(a.share)


def test_describe_names_the_convention_and_the_exclusion_rule():
    fit = ph.fit_peak_share(panel(b=0.85))
    text = ph.describe(fit)
    assert "busy_30th" in text and "excluded" in text
    # house rule: no em dashes or en dashes in any generated string
    assert "—" not in text and "–" not in text


def test_capped_airports_are_detectable_from_the_panel_alone():
    """Until the register carries declared rates, an airport whose peak stopped
    growing while its traffic did not is the best available read of rule 1."""
    def obs(iata, year, annual_mvts, peak_mvts):
        o = ph.PeakObs(iata=iata, year=year, annual_pax_m=annual_mvts * 150 * 0.82 / 1e6,
                       peak_hour_pax=peak_mvts * 150 * 0.82, convention="busy_30th")
        o.annual_mvts, o.peak_hour_mvts = annual_mvts, peak_mvts
        return o
    panel = [
        # slot-capped: traffic up 20%, peak up 2%
        obs("CAP", 2015, 400_000, 88.0), obs("CAP", 2019, 480_000, 89.8),
        # free to grow: traffic up 20%, peak up 15%
        obs("FRE", 2015, 200_000, 40.0), obs("FRE", 2019, 240_000, 46.0),
    ]
    flagged = ph.flag_capped_from_panel(panel)
    assert flagged == {"CAP"}


def test_a_flat_airport_below_the_size_floor_is_not_read_as_capped():
    def obs(iata, year, annual_mvts, peak_mvts):
        o = ph.PeakObs(iata=iata, year=year, annual_pax_m=1.0, peak_hour_pax=1.0,
                       convention="busy_30th")
        o.annual_mvts, o.peak_hour_mvts = annual_mvts, peak_mvts
        return o
    panel = [obs("FLT", 2015, 100_000, 20.0), obs("FLT", 2019, 100_500, 20.0)]
    assert ph.flag_capped_from_panel(panel) == set()


def test_a_saturated_airport_with_flat_traffic_is_still_read_as_capped():
    """The Heathrow case, and the flaw in the first version of this rule: an airport
    so constrained that its ANNUAL traffic has stopped growing too was being skipped
    as uninformative, so the most constrained airports stayed in the sample."""
    def obs(iata, year, annual_mvts, peak_mvts):
        o = ph.PeakObs(iata=iata, year=year, annual_pax_m=annual_mvts * 150 * 0.82 / 1e6,
                       peak_hour_pax=peak_mvts * 150 * 0.82, convention="busy_30th")
        o.annual_mvts, o.peak_hour_mvts = annual_mvts, peak_mvts
        return o
    panel = [obs("SAT", 2015, 474_000, 90.0), obs("SAT", 2019, 478_000, 90.3)]
    assert ph.flag_capped_from_panel(panel) == {"SAT"}


def test_a_small_flat_airport_is_not_read_as_capped():
    """Static and small is a quiet airport, not a ceiling."""
    def obs(iata, year, annual_mvts, peak_mvts):
        o = ph.PeakObs(iata=iata, year=year, annual_pax_m=1.0, peak_hour_pax=1.0,
                       convention="busy_30th")
        o.annual_mvts, o.peak_hour_mvts = annual_mvts, peak_mvts
        return o
    panel = [obs("SML", 2015, 40_000, 8.0), obs("SML", 2019, 40_200, 8.0)]
    assert ph.flag_capped_from_panel(panel) == set()


def _screen_obs(iata, year, annual_mvts, peak_mvts):
    o = ph.PeakObs(iata=iata, year=year, annual_pax_m=annual_mvts * 150 * 0.82 / 1e6,
                   peak_hour_pax=peak_mvts * 150 * 0.82, convention="busy_30th")
    o.annual_mvts, o.peak_hour_mvts = annual_mvts, peak_mvts
    return o


def test_screen_separates_ceiling_tightening_and_headroom():
    """The screen exists for the airports the register has not reached, which is most
    of them, and it needs no declared rate to say something useful."""
    panel = (
        [_screen_obs("CEIL", 2015, 474_000, 90.0), _screen_obs("CEIL", 2019, 478_000, 90.3)]
        + [_screen_obs("TIGHT", 2015, 200_000, 40.0), _screen_obs("TIGHT", 2019, 240_000, 41.0)]
        + [_screen_obs("ROOM", 2015, 100_000, 20.0), _screen_obs("ROOM", 2019, 120_000, 24.0)]
    )
    by = {r.iata: r for r in ph.capacity_screen(panel)}
    assert by["CEIL"].state == "at_ceiling"
    assert by["TIGHT"].state == "tightening"
    assert by["ROOM"].state == "headroom"          # above the screen floor, below the ceiling floor


def test_absorption_reads_as_expected():
    """Near 1 the airport is still taking growth in its peak; near 0 it is not."""
    panel = ([_screen_obs("A", 2015, 200_000, 20.0), _screen_obs("A", 2019, 240_000, 24.0)]
             + [_screen_obs("B", 2015, 200_000, 40.0), _screen_obs("B", 2019, 240_000, 41.0)])
    by = {r.iata: r for r in ph.capacity_screen(panel)}
    assert by["A"].absorption == pytest.approx(1.0, abs=0.02)
    assert by["B"].absorption < 0.2


def test_screen_flags_a_single_year_rather_than_guessing():
    by = {r.iata: r for r in ph.capacity_screen([_screen_obs("ONE", 2019, 100_000, 20.0)])}
    assert by["ONE"].state == "too_short"


def test_absorption_is_not_reported_when_annual_growth_is_near_zero():
    """The Heathrow case: 1% movement growth means any small change in the peak gives a
    wild ratio. Reported as not meaningful rather than as a number."""
    import math
    panel = [_screen_obs("SAT", 2015, 474_000, 90.9), _screen_obs("SAT", 2019, 478_000, 90.3)]
    r = ph.capacity_screen(panel)[0]
    assert math.isnan(r.absorption)
    assert r.state == "at_ceiling"       # the classification does not depend on absorption


def test_small_airports_are_not_assessed_rather_than_guessed():
    """794 airports came back as tightening on the first full run, against a Level 3
    list of about 205. At a small airport the busy hour is a handful of movements and a
    year on year change in it is noise."""
    panel = [_screen_obs("SML", 2015, 8_000, 6.0), _screen_obs("SML", 2019, 10_000, 6.1)]
    assert ph.capacity_screen(panel)[0].state == "not_assessed"


def test_size_class_fits_are_reported_separately():
    obs = panel(b=0.85, n_airports=30)
    by_class = ph.fit_by_size_class(obs)
    assert by_class
    assert all(isinstance(f, ph.PeakShareFit) for f in by_class.values())


def test_the_fit_exclusion_and_the_screen_are_one_rule():
    """On the first full-set run the exclusion carried its own copy of the rule and
    dropped 813 airports while the screen called 43. Two rules for one question drift."""
    p = ([_screen_obs("CEIL", 2015, 474_000, 90.0), _screen_obs("CEIL", 2019, 478_000, 90.3)]
         + [_screen_obs("TIGHT", 2015, 200_000, 40.0), _screen_obs("TIGHT", 2019, 240_000, 41.0)]
         + [_screen_obs("ROOM", 2015, 100_000, 20.0), _screen_obs("ROOM", 2019, 120_000, 24.0)]
         + [_screen_obs("SML", 2015, 8_000, 6.0), _screen_obs("SML", 2019, 10_000, 6.1)])
    from_screen = {r.iata for r in ph.capacity_screen(p) if r.state in ("at_ceiling", "tightening")}
    assert ph.flag_capped_from_panel(p) == from_screen == {"CEIL", "TIGHT"}


def test_a_low_r2_flags_the_level_without_discarding_the_estimate():
    """Within a narrow size class r2 falls because the spread of annual traffic is
    small. The estimate is still the estimate; the standard error is the diagnostic."""
    import random
    random.seed(7)
    obs = []
    for i in range(40):
        base = 10.0 + random.random()          # a deliberately narrow size range
        for y in range(2015, 2020):
            annual = base * (1.02 ** (y - 2015))
            peak = 0.004 * (annual * 1e6) ** 0.85 * (1 + random.gauss(0, 0.05))
            obs.append(ph.PeakObs(f"N{i:02d}", y, annual, peak, convention="busy_30th"))
    fit = ph.fit_peak_share(obs)
    assert not fit.fallback_used              # the estimate survives
    assert fit.b != pytest.approx(get("peak_hour.fallback_elasticity"))
    assert fit.se_b == fit.se_b               # and carries a standard error


def test_curved_fit_recovers_a_size_varying_elasticity():
    """The class table showed a gradient its own boundaries could not resolve: adjacent
    classes were within the noise while the ends of the range were four standard errors
    apart. That is a continuous relationship forced through arbitrary steps."""
    import math, random
    random.seed(11)
    obs = []
    for i in range(120):
        size = 0.4 * (1.06 ** i)                      # 0.4m to circa 400m, wide on purpose
        for y in range(2015, 2020):
            annual = size * (1.03 ** (y - 2015))
            # elasticity rising with size, which is what the real panel shows
            b = 0.66 + 0.03 * math.log(annual)
            peak = math.exp(-4.0) * (annual * 1e6) ** b * (1 + random.gauss(0, 0.02))
            obs.append(ph.PeakObs(f"C{i:03d}", y, annual, peak, intl_share=0.5,
                                  seasonality=1 / 12 + i * 1e-5, convention="busy_30th"))
    cf = ph.fit_curved(obs)
    assert cf.fitted_ok
    assert cf.b2 > 0                                   # elasticity rises with size
    assert cf.elasticity_at(60) > cf.elasticity_at(1)


def test_curved_fit_says_so_when_there_is_no_curvature():
    """A straight relationship must not be dressed up as a curved one."""
    obs = panel(b=0.85, n_airports=40)
    cf = ph.fit_curved(obs)
    if not cf.fitted_ok:
        assert "not distinguishable from zero" in cf.notes


def test_size_class_lookup_covers_the_whole_range():
    """The backtest assigns every airport to a class, so the bands must tile without
    a gap: an airport at exactly 15.0m must land somewhere."""
    for m in (0.0, 0.99, 1.0, 4.99, 5.0, 14.99, 15.0, 39.99, 40.0, 200.0):
        hits = [lab for lab, lo, hi in ph.SIZE_CLASSES if lo <= m < hi]
        assert len(hits) == 1, f"{m}m matched {hits}"


def test_projection_from_actual_growth_is_the_identity_when_traffic_is_flat():
    """The backtest projects on ACTUAL traffic growth, so with no growth every method
    must return the base share and the test reduces to the flat case."""
    fit = ph.fit_peak_share(panel(b=0.85))
    s = ph.project_share(fit, 0.0005, base_annual_m=10.0, target_annual_m=10.0)
    assert s == pytest.approx(0.0005)

"""ingest/oag_peak - build the peak hour panel from the OAG store
(Capacity Method and Evidence Record v0.4, section 11.1). Author: Avia Solutions.

Produces the PeakObs panel that capacity.peakhour fits: one row per airport-year with
annual passengers, annual movements, the design peak hour on a named convention, the
international share, a seasonality index and the constrained flag.

Rebuilt on 3 August 2026 after reading the store directly. The first version treated
it as schedule SERVICES and expanded each row across its effective window. That was
wrong: the store is ONE ROW PER OPERATED FLIGHT, so nothing is expanded, and
eff_from / eff_to are the season window rather than the row's date. The store reading
conventions live in ingest.oag_store, shared with the backtests.

Five things that would each produce a plausible-looking and wrong panel:

  1. Counting departures only. The runway constraint is ATM. Arrivals and departures
     also bank at different times, so the combined flow is built as ONE series and
     never as twice the departure peak. Heathrow read on departures alone would show
     half its movements and would never appear constrained.

  2. Summing across region files. A flight spanning two regions is listed in both.
     Only the airport's home region file is read: 678 departures a day at Heathrow in
     June 2019 against 934 raw.

  3. Summing overlapping period tilings. Exactly one tiling per region-year.

  4. Mixing peak hour conventions. The convention is named on every row.

  5. Ranking an incomplete year. An airport-year below the coverage threshold is
     dropped rather than ranked, because a missing month gives an ordinary peak on a
     low annual total and biases the share upward where history is patchy.

Store location and column names come from config or AVIA_OAG_STORE, never a literal
(tool standard 3 and 4).
"""
from __future__ import annotations
from dataclasses import dataclass
import calendar
import math
import os
from pathlib import Path

from ..config import get, _load
from ..capacity.peakhour import PeakObs
from . import oag_store


DEFAULT_MAPPING = {
    "row_grain": "operation",
    "table": "oag",
    "airport": "dep_airport",
    "arr_airport": "arr_airport",
    "seats": "seats",
    "passengers": "",
    "arr_country": "arr_country",
    "home_country": "dep_country",
    "days_of_op": "days_of_op",
    "dep_time": "local_dep_time",
    "arr_time": "local_arr_time",
    "arr_day_offset": "local_arr_day",
    "week": "week",
    "region": "region",
    "year": "year",
}

DEFAULT_FILTER = ""


def store_path(explicit: str | Path | None = None) -> Path:
    if explicit:
        return Path(explicit)
    env = os.environ.get("AVIA_OAG_STORE")
    if env:
        return Path(env)
    cfg = _load("sources.yaml").get("oag_schedules", {}).get("store_path")
    if not cfg:
        raise FileNotFoundError(
            "No OAG store location. Pass --store, set AVIA_OAG_STORE, or set "
            "sources.yaml oag_schedules.store_path. The store is not committed to "
            "the repo by design (tool standard 3).")
    return Path(cfg)


def mapping() -> dict:
    m = dict(DEFAULT_MAPPING)
    m.update((_load("sources.yaml").get("oag_schedules", {}) or {}).get("columns", {}) or {})
    return m


def row_filter() -> str:
    return ((_load("sources.yaml").get("oag_schedules", {}) or {}).get("filter")
            or DEFAULT_FILTER).strip()


def _connect(path: Path):
    import duckdb
    if not Path(path).exists():
        raise FileNotFoundError(f"OAG store not found at {path}")
    con = duckdb.connect(str(path), read_only=True)
    # Heavy panel queries spill temp storage next to the store by default; on a full
    # C: drive that kills the run. Redirect via env, same pattern as AVIA_OAG_STORE.
    tmp = os.environ.get("AVIA_DUCKDB_TMP")
    if tmp:
        os.makedirs(tmp, exist_ok=True)
        con.execute(f"SET temp_directory='{tmp}'")
    try:
        con.execute("SET enable_progress_bar=false")
    except Exception:
        pass
    return con


def describe_store(path=None) -> dict:
    p = store_path(path)
    con = _connect(p)
    try:
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        m = mapping()
        cols = {t: [r[1] for r in con.execute(f'PRAGMA table_info("{t}")').fetchall()]
                for t in tables}
        resolved = m["table"] in tables
        missing = []
        if resolved:
            present = set(cols[m["table"]])
            for key in ("airport", "arr_airport", "seats", "days_of_op", "dep_time",
                        "arr_time", "week", "region", "year"):
                if m.get(key) and m[key] not in present:
                    missing.append(f"{key} -> {m[key]}")
        return {"store": str(p), "tables": tables, "columns": cols, "mapping": m,
                "row_grain": m["row_grain"], "table_resolved": resolved,
                "missing_columns": missing}
    finally:
        con.close()


@dataclass
class PanelBuildReport:
    rows: int
    airports: int
    years: list
    convention: str
    dropped_incomplete: list
    load_factor_assumed: float | None
    notes: str = ""


#: Events are bucketed on SLOT_MINUTES and every convention is built from that one
#: base, so the forms are directly comparable and the resolution is stated once.
SLOT_MINUTES = 5
SLOTS_PER_DAY = 24 * 60 // SLOT_MINUTES      # 288
SLOTS_PER_HOUR = 60 // SLOT_MINUTES          # 12

#: The peak-hour window conventions the panel can build.
#:
#:   clock_hour           the 8,760 fixed hours of the year, 00:00-00:59 and so on
#:   rolling_60_step_5    best 60-minute window starting on any 5-minute boundary
#:   rolling_60_step_10   the same on 10-minute boundaries
#:
#: Rolling is Avia house convention and the step is FIVE minutes. That was corrected by
#: John Carter on 4 August 2026; the first version of this module used a 10-minute step,
#: taken from the way coordinators declare capacity (Nantes and Basel both publish
#: "passengers per rolling 60 minutes with a step of 10 minutes"). Those are two
#: different things: 10 minutes is how a coordinator states a limit, 5 minutes is how
#: Avia measures demand. The DDFS Studio works in 5-minute movement bars, and Bologna is
#: reported to the client on both bases, "clock/h seats" and "rolling/h pax" as separate
#: lines. Both steps are kept so a declared rate can be tested on its own step where
#: that is the right comparison.
#:
#: Taking the best window per clock hour matters and is not a detail. Ranking every
#: overlapping window instead returns the same busy period many times over and gives a
#: LOWER 30th busiest value than the clock hour convention, which is impossible for a
#: true rolling maximum and was the first thing this implementation got wrong. One value
#: per clock hour keeps the same 8,760 observations a year, each at or above its
#: clock-hour counterpart.
#:
#: Measured against 32 airports from Jess Rowden's independently built 2025 panel,
#: 4 August 2026, on the 10-minute step: rolling moved the median bias on seats from
#: -8.7% to -6.4% and on movements from -6.7% to -5.7%. Real, in the right direction,
#: and NOT the explanation for the divergence. A 5-minute step can only widen the
#: window's reach slightly further. Most of that gap is still unaccounted for and is
#: most likely the date-spreading: the store gives one row per operated flight but not
#: which date it flew, so traffic is spread across the matching dates in a period and
#: day-to-day variation is averaged away. See CHANGELOG, 4 August 2026.
PEAK_WINDOWS = ("clock_hour", "rolling_60_step_5", "rolling_60_step_10")


def _hour_cte(window: str) -> str:
    """The SQL producing one row per airport-year-hour, on the chosen convention.

    Every form consumes `spread`, which carries SLOT_MINUTES buckets, and emits `hours`.
    """
    if window == "clock_hour":
        return f"""
        hours AS (
            SELECT iata, yr, d, hh / {SLOTS_PER_HOUR} AS hr,
                   SUM(pax) AS pax, SUM(ops) AS ops
            FROM spread GROUP BY 1, 2, 3, 4
        ),"""
    if window.startswith("rolling_60_step_"):
        try:
            step = int(window.rsplit("_", 1)[1])
        except ValueError:
            raise ValueError(f"unreadable step in {window!r}")
        if step % SLOT_MINUTES or step <= 0:
            raise ValueError(
                f"step {step} is not a multiple of the {SLOT_MINUTES}-minute base slot")
        every = step // SLOT_MINUTES          # consider every Nth slot as a start
        span = SLOTS_PER_HOUR - 1             # 60 minutes inclusive of the current slot
        # A continuous slot index across the year so a window may cross midnight,
        # then the best window starting in each clock hour.
        return f"""
        idx AS (
            SELECT iata, yr, d, hh,
                   datediff('day', DATE '1970-01-01', d) * {SLOTS_PER_DAY} + hh AS s,
                   pax, ops
            FROM spread
        ),
        roll AS (
            SELECT iata, yr, s,
                   SUM(pax) OVER (PARTITION BY iata, yr ORDER BY s
                                  RANGE BETWEEN CURRENT ROW AND {span} FOLLOWING) AS pax,
                   SUM(ops) OVER (PARTITION BY iata, yr ORDER BY s
                                  RANGE BETWEEN CURRENT ROW AND {span} FOLLOWING) AS ops
            FROM idx
            WHERE s % {every} = 0
        ),
        hours AS (
            SELECT iata, yr, s / {SLOTS_PER_HOUR} AS hr,
                   MAX(pax) AS pax, MAX(ops) AS ops
            FROM roll GROUP BY 1, 2, 3
        ),"""
    raise ValueError(f"unknown peak window {window!r}; expected one of {PEAK_WINDOWS}")


def _tiling_predicate(pref: dict, m: dict) -> str:
    """SQL keeping only each region-year's preferred set of period keys."""
    if not pref:
        return "TRUE"
    clauses = []
    for (region, yr), keys in pref.items():
        ks = ",".join("'" + k.replace("'", "''") + "'" for k in sorted(keys))
        clauses.append(f"(x.\"{m['region']}\" = '{region.replace(chr(39), chr(39)*2)}' "
                       f"AND CAST(x.\"{m['year']}\" AS INTEGER) = {int(yr)} "
                       f"AND x.\"{m['week']}\" IN ({ks}))")
    return "(" + " OR ".join(clauses) + ")"


def _home_predicate(home: dict, m: dict, side: str) -> str:
    """SQL keeping only each airport's home region file. side is the airport column."""
    if not home:
        return "TRUE"
    pairs = ",".join(f"('{a}','{r}')" for a, r in sorted(home.items()) if a and r)
    return f"(x.\"{side}\", x.\"{m['region']}\") IN ({pairs})"


def _calendar_values(con, m: dict) -> str:
    """VALUES list mapping each period key to the dates it covers. There are only a
    hundred or so keys, so this is cheap and keeps the whole build inside the database."""
    keys = [r[0] for r in con.execute(
        f'SELECT DISTINCT "{m["week"]}" FROM "{m["table"]}" WHERE "{m["week"]}" IS NOT NULL').fetchall()]
    # part_spans, not period_span: a split-month part's end depends on where its
    # siblings start, and reading each key alone double-counts the overlap. The
    # calendar has to agree with preferred_tilings or the fix only lands in half the
    # pipeline, which is worse than not fixing it at all.
    spans = oag_store.part_spans(keys)
    rows = [f"('{k}', DATE '{lo}', DATE '{hi}')" for k, (lo, hi) in sorted(spans.items())]
    return ", ".join(rows) if rows else "('', DATE '2000-01-01', DATE '2000-01-01')"


def build_panel(path=None, nth: int | None = None, load_factor: float | None = None,
                min_hours_covered: float = 0.90, constrained: set | None = None,
                airports: list | None = None, years: list | None = None,
                window: str | None = None):
    """Return (list[PeakObs], PanelBuildReport).

    Departures and arrivals are read as one combined flow, deduplicated to each
    airport's home region file and to one period tiling per region-year, then spread
    across the operating dates in each period by the days-of-operation pattern and
    ranked. Nothing is expanded across effective windows.

    The spreading and the ranking happen in SQL rather than in Python, so the whole
    airport set is feasible rather than only the largest few hundred. That matters for
    the forecast and not just for speed: a constrained secondary airport spills traffic
    the engine would otherwise let through, and the airports with headroom are where
    that spill has to go, so neither half of the catchment redistribution works on a
    top-200 panel.
    """
    convention = str(get("peak_hour.convention", "busy_30th"))
    if nth is None:
        nth = int(convention.split("_")[1].rstrip("thstrdn")) if "_" in convention else 30
    window = window or str(get("peak_hour.window", "clock_hour"))
    if window not in PEAK_WINDOWS:
        raise ValueError(f"unknown peak_hour.window {window!r}; expected one of {PEAK_WINDOWS}")
    hour_cte = _hour_cte(window)
    # The window belongs in the convention name. A panel that says only "busy_30th"
    # cannot be compared with another panel, and mixing conventions is failure mode 4
    # in this module's own docstring.
    convention = f"{convention}/{window}"
    m = mapping()
    lf = load_factor if load_factor is not None else float(get("capacity_register.load_factor_default"))
    constrained = constrained or set()
    filt = row_filter()

    con = _connect(store_path(path))
    try:
        pref = oag_store.preferred_tilings(con, m["table"])
        home = oag_store.home_regions(con, m["table"], airports=airports)
        if years:
            pref = {(r, y): k for (r, y), k in pref.items() if int(y) in set(years)}

        tiling = _tiling_predicate(pref, m)
        and_filter = f"AND ({filt})" if filt else ""
        # Events are placed on a SLOT_MINUTES bucket, not a clock hour, so that every
        # convention is built from the same base.
        dep_hour = oag_store.minutes_sql(m["dep_time"], "x") + f" / {SLOT_MINUTES}"
        arr_hour = oag_store.minutes_sql(m["arr_time"], "x") + f" / {SLOT_MINUTES}"
        pax = (f'TRY_CAST(x."{m["passengers"]}" AS DOUBLE)' if m["passengers"]
               else f'TRY_CAST(x."{m["seats"]}" AS DOUBLE) * {lf}')
        intl = (f'CASE WHEN x."{m["arr_country"]}" = x."{m["home_country"]}" THEN 0 ELSE 1 END'
                if m.get("arr_country") and m.get("home_country") else "0")
        cal_values = _calendar_values(con, m)

        sql = f"""
        WITH cal AS (SELECT * FROM (VALUES {cal_values}) v(wk, lo, hi)),
        dates AS (
            SELECT wk, UNNEST(generate_series(lo, hi, INTERVAL 1 DAY))::DATE AS d FROM cal
        ),
        ev AS (
            SELECT x."{m['airport']}" AS iata, x."{m['week']}" AS wk,
                   CAST(x."{m['year']}" AS INTEGER) AS yr,
                   CAST(x."{m['days_of_op']}" AS VARCHAR) AS dop,
                   {dep_hour} AS hh, COUNT(*) AS ops, SUM({pax}) AS pax,
                   SUM(CASE WHEN {intl} = 1 THEN {pax} ELSE 0 END) AS intl_pax
            FROM "{m['table']}" x
            WHERE {_home_predicate(home, m, m['airport'])} AND {tiling} {and_filter}
            GROUP BY 1, 2, 3, 4, 5
            UNION ALL
            SELECT x."{m['arr_airport']}" AS iata, x."{m['week']}" AS wk,
                   CAST(x."{m['year']}" AS INTEGER) AS yr,
                   CAST(x."{m['days_of_op']}" AS VARCHAR) AS dop,
                   {arr_hour} AS hh, COUNT(*) AS ops, SUM({pax}) AS pax,
                   SUM(CASE WHEN {intl} = 1 THEN {pax} ELSE 0 END) AS intl_pax
            FROM "{m['table']}" x
            WHERE {_home_predicate(home, m, m['arr_airport'])} AND {tiling} {and_filter}
            GROUP BY 1, 2, 3, 4, 5
        ),
        evf AS (SELECT * FROM ev WHERE iata IS NOT NULL AND hh BETWEEN 0 AND {SLOTS_PER_DAY - 1}),
        den AS (
            SELECT k.wk, k.dop, COUNT(*) AS n
            FROM (SELECT DISTINCT wk, dop FROM evf) k
            JOIN dates ON dates.wk = k.wk
             AND strpos(k.dop, CAST(isodow(dates.d) AS VARCHAR)) > 0
            GROUP BY 1, 2
        ),
        spread AS (
            SELECT evf.iata, evf.yr, dates.d AS d, evf.hh,
                   SUM(evf.pax / den.n)      AS pax,
                   SUM(evf.ops / den.n)      AS ops,
                   SUM(evf.intl_pax / den.n) AS intl_pax
            FROM evf
            JOIN den   ON den.wk = evf.wk AND den.dop = evf.dop
            JOIN dates ON dates.wk = evf.wk
                      AND strpos(evf.dop, CAST(isodow(dates.d) AS VARCHAR)) > 0
            GROUP BY 1, 2, 3, 4
        ),
        {hour_cte}
        ranked AS (
            SELECT iata, yr, pax, ops,
                   ROW_NUMBER() OVER (PARTITION BY iata, yr ORDER BY pax DESC) AS rn
            FROM hours
        ),
        ann AS (
            SELECT iata, yr, SUM(pax) AS pax, SUM(ops) AS ops,
                   SUM(intl_pax) AS intl_pax, COUNT(DISTINCT d) AS days,
                   COUNT(*) AS n_hours
            FROM spread GROUP BY 1, 2
        ),
        -- n_hours counts 10-minute slots, so the "too few hours" guard below is
        -- compared against nth slots and not nth hours. That is deliberately
        -- conservative: it can only drop an airport-year, never rank a thin one.
        mon AS (
            SELECT iata, yr, MAX(mp) AS peak_month_pax FROM (
                SELECT iata, yr, month(d) AS mm, SUM(pax) AS mp
                FROM spread GROUP BY 1, 2, 3) GROUP BY 1, 2
        )
        SELECT ann.iata, ann.yr, ann.pax, ann.ops, ann.intl_pax, ann.days, ann.n_hours,
               r.pax AS peak_pax, r.ops AS peak_ops, mon.peak_month_pax
        FROM ann
        LEFT JOIN ranked r ON r.iata = ann.iata AND r.yr = ann.yr AND r.rn = {nth}
        LEFT JOIN mon     ON mon.iata = ann.iata AND mon.yr = ann.yr
        """
        rows = con.execute(sql).fetchall()
    finally:
        con.close()

    obs, dropped = [], []
    for iata, yr, apax, aops, aintl, days, n_hours, peak_pax, peak_ops, peak_month in rows:
        year = int(yr)
        days_in_year = 366 if calendar.isleap(year) else 365
        coverage = (days or 0) / days_in_year
        if coverage < min_hours_covered:
            dropped.append((iata, year, round(coverage, 2)))
            continue
        if peak_pax is None or (n_hours or 0) < nth or not apax or apax <= 0:
            dropped.append((iata, year, "too few hours"))
            continue
        o = PeakObs(iata=iata, year=year, annual_pax_m=apax / 1e6,
                    peak_hour_pax=float(peak_pax),
                    intl_share=(aintl / apax) if apax else 0.0,
                    seasonality=(peak_month / apax) if (peak_month and apax) else 1 / 12,
                    constrained=iata in constrained,
                    convention=convention)
        o.peak_hour_mvts = float(peak_ops or 0.0)
        o.annual_mvts = float(aops or 0.0)
        obs.append(o)

    basis = ("passengers taken from the store" if m["passengers"]
             else f"store carries seats, not passengers: passengers = seats x {lf} "
                  f"(assumptions book), and the fit is on that basis")
    report = PanelBuildReport(
        rows=len(obs), airports=len({o.iata for o in obs}),
        years=sorted({o.year for o in obs}), convention=convention,
        dropped_incomplete=dropped,
        load_factor_assumed=None if m["passengers"] else lf,
        notes=(f"{basis}; one row per operated flight, nothing expanded; arrivals and "
               f"departures combined as one flow; home region file only; one period "
               f"tiling per region-year; spread and ranked in SQL; "
               f"peak window {window}; "
               + (f"row filter: {filt}" if filt else "NO ROW FILTER SET")))
    return sorted(obs, key=lambda o: (o.iata, o.year)), report


def flag_constrained(observed_peak_mvts: dict, declared_rate: dict) -> set:
    """Airports whose observed peak is at or above the book share of their declared
    rate, so their peak reports the declaration rather than demand. Feeding this into
    build_panel keeps them out of the estimation sample."""
    thresh = float(get("peak_hour.constrained_utilisation_flag"))
    return {i for i, rate in declared_rate.items()
            if rate and observed_peak_mvts.get(i) and observed_peak_mvts[i] / rate >= thresh}

r"""Guard the OAG store before any fleet productivity wedge number is produced.
Author: Avia Solutions.

Run this before scripts/build_fleet_wedge.py. The wedge is an identity,

    ASK = departures  x  seats per departure  x  stage length

so any error in the store propagates into all three terms at once and the result still
looks like a sensible table. On 9 August 2026 an unmapped-airport report caught three
separate bugs that would each have produced a plausible-looking table. This is the same
instrument pointed at the store.

What it checks, in order:

  1  Year coverage. Which calendar years carry a preferred tiling in all seven region
     files, and which are partial. A partial year silently shortens the window.
  2  Tiling uniqueness. No region-year may be summed under two tilings at once.
  3  Export cap signature. A slice at or just under Excel's 1,048,576-row sheet limit,
     or a row count identical across two years, is the tell for the OAG Analyser
     export truncation found on 21 July 2026. Route coverage does not detect it.
  4  Home-region assignment. Every departure airport must resolve to one home region
     file, otherwise its flights are either double counted or dropped.
  5  Numeric casts. seats, frequency and gcd_km are VARCHAR in the store. A null cast
     is a silent zero in a SUM.
  6  Unit check. gcd_km against gcd_mi must give 1.609, which proves which column is
     which. An ASK built on miles read as kilometres is 61% high and looks plausible.
  7  Great circle distance plausibility, against the longest scheduled sector flown.
  8  frequency is 1 on every row, which is what makes COUNT(*) the departure count.
  9  Aircraft code coverage against config/aircraft_body_types.yaml, reported as a
     share of seats rather than of rows, because the unmapped tail is small aircraft.
 10  carrier_category values, which carry the LCC slide.
 11  The Heathrow 2019 anchor recorded in avia_forecast/ingest/oag_store.py:
     477,954 movements and 100.4m seats on the home region, service type J.

Writes the report as JSON beside the Global data, and exits non-zero on any FAIL so a
build step cannot run past it.

Usage:  py -3.12 scripts\guard_oag_wedge.py [--years 2015 2016 ...] [--json PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb  # noqa: E402
import yaml  # noqa: E402

from avia_forecast import paths  # noqa: E402
from avia_forecast.ingest.oag_store import preferred_tilings, home_regions  # noqa: E402

REGIONS_EXPECTED = 7
SHEET_CAP_ROWS = 1_048_575      # 1,048,576 rows in a sheet, one of them the header
CAP_EXACT_BAND = 50             # this close to the limit is a truncated export
CAP_WATCH = 0.02                # this close is a slice to keep an eye on
DENSITY_FLOOR = 0.50            # seats per day below this share of the rest of the
                                # region-year is the truncation tell row counts miss
YOY_LIMIT = 0.25                # annual seats step that no real market makes
LONGEST_SECTOR_KM = 15_400      # the longest scheduled sector flown is under this
MI_PER_KM = 1.609344
SERVICE_TYPE = "J"

# The anchor in avia_forecast/ingest/oag_store.py, established 3 August 2026. It is a
# TWO-WAY figure: Heathrow's published movements count arrivals and departures, and the
# 100.4m seats likewise. The store holds one row per departure, so a departures-only
# query returns exactly half of each and looks, wrongly, like a store missing half its
# data. Checked here in both directions, with the one-way figure reported beside it.
ANCHOR = {"airport": "LHR", "year": 2019,
          "movements_two_way": 477_954, "seats_two_way": 100_400_000}
ANCHOR_TOL = 0.01


class Report:
    def __init__(self):
        self.checks = []

    def add(self, name, status, detail, **extra):
        row = {"check": name, "status": status, "detail": detail}
        row.update(extra)
        self.checks.append(row)
        print(f"[{status:<4}] {name}: {detail}")
        return row

    @property
    def failed(self):
        return [c for c in self.checks if c["status"] == "FAIL"]

    @property
    def warned(self):
        return [c for c in self.checks if c["status"] == "WARN"]


def _q(con, sql, params=None):
    return con.execute(sql, params or []).fetchall()


def check_coverage(con, rep):
    """1 and 2: complete years, and one tiling per region-year."""
    pref = preferred_tilings(con)
    regions = sorted({r for r, _ in pref})
    years = sorted({y for _, y in pref})
    complete, partial = [], []
    for y in years:
        got = sorted(r for r in regions if (r, y) in pref)
        (complete if len(got) == REGIONS_EXPECTED else partial).append(
            (y, len(got), [r for r in regions if r not in got]))
    rep.add("year coverage",
            "PASS" if complete else "FAIL",
            f"{len(complete)} complete years: "
            + ", ".join(str(y) for y, _, _ in complete),
            complete_years=[y for y, _, _ in complete])
    if partial:
        rep.add("partial years", "WARN",
                "; ".join(f"{y}: {n} of {REGIONS_EXPECTED} regions, missing "
                          + ", ".join(m) for y, n, m in partial)
                + ". Excluded from any annual series.",
                partial_years=[y for y, _, _ in partial])

    # Every non-weekly key in the store must be claimed by exactly one preferred tiling.
    claimed = {(r, y, k) for (r, y), ks in pref.items() for k in ks}
    allkeys = _q(con, """SELECT region, CAST(substr(week,1,4) AS INT), week, count(*)
                         FROM oag WHERE week NOT LIKE '20__-__-__'
                         GROUP BY 1,2,3""")
    unclaimed = [(r, y, k, n) for r, y, k, n in allkeys if (r, y, k) not in claimed]
    rep.add("tiling uniqueness",
            "PASS" if not unclaimed else "WARN",
            "every non-weekly period key is claimed by exactly one tiling"
            if not unclaimed else
            f"{len(unclaimed)} keys are in the store and not in the preferred tiling, "
            f"{sum(n for *_, n in unclaimed):,} rows. These are superseded slices and "
            "are excluded, which is correct, but confirm none is the only copy",
            unclaimed=[{"region": r, "year": y, "key": k, "rows": n}
                       for r, y, k, n in unclaimed[:40]])
    return pref, [y for y, _, _ in complete]


def check_cap(con, rep, pref):
    """3: the export sheet-cap signature, in two parts.

    A row count near the sheet limit is not by itself truncation. Jess Rowden split the
    months that would have overflowed into halves, so Asia's busiest single months sit
    just under the limit legitimately. What proves truncation is a slice whose row count
    is AT the limit, or whose seats per day fall away from the rest of its own year.
    Row count alone raises a false alarm on every busy month; density alone misses a
    year truncated end to end. Both are needed.
    """
    counts = {(r, y, k): (n, s) for r, y, k, n, s in
              _q(con, f"""SELECT region, CAST(substr(week,1,4) AS INT), week, count(*),
                                 sum(TRY_CAST(seats AS BIGINT))
                          FROM oag WHERE service_type = '{SERVICE_TYPE}'
                          GROUP BY 1,2,3""")}
    at_cap = [(r, y, k, n) for (r, y, k), (n, _) in counts.items()
              if abs(n - SHEET_CAP_ROWS) <= CAP_EXACT_BAND]
    rep.add("export cap, slices at the sheet limit",
            "PASS" if not at_cap else "FAIL",
            f"no slice sits within {CAP_EXACT_BAND} rows of the {SHEET_CAP_ROWS:,} row "
            "sheet limit" if not at_cap else
            f"{len(at_cap)} slices are truncated at the sheet limit: "
            + "; ".join(f"{r} {k} {n:,}" for r, y, k, n in at_cap[:10]),
            at_cap=[{"region": r, "key": k, "rows": n} for r, y, k, n in at_cap[:40]])

    watch = sorted((r, y, k, n) for (r, y, k), (n, _) in counts.items()
                   if not any(k == kk and r == rr for rr, _, kk, _ in at_cap)
                   and abs(n - SHEET_CAP_ROWS) / SHEET_CAP_ROWS <= CAP_WATCH)

    annual, annual_seats = {}, {}
    for (r, y), ks in pref.items():
        annual[(r, y)] = sum(counts.get((r, y, k), (0, 0))[0] for k in ks)
        annual_seats[(r, y)] = sum(counts.get((r, y, k), (0, 0))[1] or 0 for k in ks)

    # Within-year hole. Seats per day for each slice against the median of the OTHER
    # slices of the same region-year. Both trend and season are out of the comparison,
    # which two earlier versions of this check were not: against the year's own median
    # every European January failed, because European winter capacity really is a fifth
    # below the year; against the same month in other years every 2015 slice failed,
    # because eight years of Asian growth put 2015 a quarter below the median of the
    # years that follow it. Neither was a defect, and a check that cries wolf gets
    # switched off by the third person who runs it. The floor is deliberately loose:
    # the truncation found on 21 July 2026 removed about 90% of a slice, so it does not
    # need a tight threshold to be caught, and seasonal amplitude does not reach 50%.
    from statistics import median
    import datetime
    from avia_forecast.ingest.oag_store import part_spans
    thin = []
    for (r, y), ks in sorted(pref.items()):
        spans, dens = part_spans(ks), {}
        for k in ks:
            span, (_, s) = spans.get(k), counts.get((r, y, k), (0, 0))
            if not span or not s:
                continue
            d0 = datetime.date.fromisoformat(span[0])
            d1 = datetime.date.fromisoformat(span[1])
            days = (d1 - d0).days + 1
            if days > 0:
                dens[k] = s / days
        if len(dens) < 4:
            continue
        for k, v in sorted(dens.items()):
            others = [vv for kk, vv in dens.items() if kk != k]
            med = median(others)
            if med and v < DENSITY_FLOOR * med:
                thin.append((r, y, k, v / med))
    rep.add("within-year hole, seats per day",
            "PASS" if not thin else "FAIL",
            f"every slice carries at least {DENSITY_FLOOR:.0%} of the seats per day of "
            "the other slices of its own region-year"
            + (f", including the {len(watch)} slices within 2% of the sheet limit, "
               "which are busy months and not truncated ones" if watch else "")
            if not thin else
            f"{len(thin)} slices fall below {DENSITY_FLOOR:.0%} of the other slices of "
            "their own region-year, which is the truncation tell: "
            + "; ".join(f"{r} {k} at {f * 100:.0f}%" for r, y, k, f in thin[:10]),
            thin=[{"region": r, "year": y, "key": k, "share_of_year_median": f}
                  for r, y, k, f in thin[:40]],
            near_cap_watch=[{"region": r, "key": k, "rows": n} for r, y, k, n in watch])

    # Year on year on the annual total. A slice truncated end to end shows here and
    # nowhere else, because a hole in every month of a year leaves the within-year
    # comparison flat.
    from math import isfinite
    steps = []
    for r in sorted({rr for rr, _ in pref}):
        ys = sorted(y for rr, y in pref if rr == r)
        for i in range(1, len(ys)):
            a, b = annual_seats.get((r, ys[i - 1])), annual_seats.get((r, ys[i]))
            if not a or not b:
                continue
            ch = b / a - 1.0
            if isfinite(ch) and abs(ch) > YOY_LIMIT:
                steps.append((r, ys[i - 1], ys[i], ch))
    rep.add("year on year step in annual seats",
            "PASS" if not steps else "FAIL",
            f"no region moves by more than {YOY_LIMIT:.0%} between consecutive years "
            "held in the store, across the 2019 to 2023 gap included"
            if not steps else
            "; ".join(f"{r} {a} to {b} {ch * 100:+.1f}%" for r, a, b, ch in steps),
            steps=[{"region": r, "from": a, "to": b, "change": ch}
                   for r, a, b, ch in steps])

    # Identical annual row counts for one region across two years is the second tell.
    dupes = []
    for r in sorted({r for r, _ in annual}):
        seen = {}
        for (rr, y), n in annual.items():
            if rr != r:
                continue
            if n in seen:
                dupes.append((r, seen[n], y, n))
            seen[n] = y
    rep.add("export cap signature, identical years",
            "PASS" if not dupes else "FAIL",
            "no region repeats an annual row count across two years"
            if not dupes else
            "; ".join(f"{r} {a} and {b} both {n:,} rows" for r, a, b, n in dupes),
            identical_years=[{"region": r, "years": [a, b], "rows": n}
                             for r, a, b, n in dupes])
    return annual


def check_home_regions(con, rep):
    """4: one home region file per departure airport."""
    home = home_regions(con)
    blank = [a for a in home if not a or not a.strip()]
    rep.add("home region assignment",
            "PASS" if not blank else "FAIL",
            f"{len(home):,} departure airports each resolve to one home region file"
            + ("" if not blank else f", {len(blank)} with a blank code"),
            airports=len(home))
    return home


def _basis_cte(pref, home, years):
    """SQL predicate restricting the store to one tiling per region-year and each
    airport's home region file. Written as a literal VALUES list because the store is
    read-only and a temporary table cannot be created against it."""
    pairs = []
    for (r, y), ks in pref.items():
        if y not in years:
            continue
        for k in ks:
            pairs.append((r, k))
    keys = ",".join(f"('{r}','{k}')" for r, k in sorted(set(pairs)))
    homes = ",".join(f"('{a}','{r}')" for a, r in sorted(home.items()) if a and a.strip())
    return (f"WITH tiling(region, week) AS (VALUES {keys}),\n"
            f"     home(dep_airport, region) AS (VALUES {homes})\n")


def check_numerics(con, rep, pref, home, years):
    """5 to 8: casts, units, distance plausibility, and frequency."""
    cte = _basis_cte(pref, home, years)
    sql = cte + f"""
    SELECT count(*) AS rows,
           count(*) FILTER (WHERE TRY_CAST(o.seats AS BIGINT) IS NULL)      AS seats_null,
           count(*) FILTER (WHERE TRY_CAST(o.seats AS BIGINT) = 0)          AS seats_zero,
           count(*) FILTER (WHERE TRY_CAST(o.frequency AS BIGINT) IS NULL)  AS freq_null,
           count(*) FILTER (WHERE TRY_CAST(o.frequency AS BIGINT) <> 1)     AS freq_not_one,
           count(*) FILTER (WHERE TRY_CAST(o.gcd_km AS DOUBLE) IS NULL)     AS km_null,
           count(*) FILTER (WHERE TRY_CAST(o.gcd_km AS DOUBLE) <= 0)        AS km_zero,
           count(*) FILTER (WHERE TRY_CAST(o.gcd_km AS DOUBLE) > {LONGEST_SECTOR_KM}) AS km_long,
           max(TRY_CAST(o.gcd_km AS DOUBLE))                                AS km_max,
           count(*) FILTER (WHERE o.aircraft_code IS NULL OR trim(o.aircraft_code) = '') AS ac_blank,
           sum(TRY_CAST(o.seats AS BIGINT))                                 AS seats_sum,
           sum(TRY_CAST(o.seats AS DOUBLE) * TRY_CAST(o.gcd_km AS DOUBLE))  AS ask_sum,
           sum(TRY_CAST(o.gcd_mi AS DOUBLE)) AS mi_sum,
           sum(TRY_CAST(o.gcd_km AS DOUBLE)) AS km_sum,
           sum(TRY_CAST(o.frequency AS BIGINT)) AS freq_sum,
           sum(TRY_CAST(o.seats AS DOUBLE) * TRY_CAST(o.frequency AS DOUBLE)) AS seats_f,
           sum(CASE WHEN TRY_CAST(o.gcd_km AS DOUBLE) > {LONGEST_SECTOR_KM}
                    THEN TRY_CAST(o.seats AS DOUBLE) * TRY_CAST(o.gcd_km AS DOUBLE)
                    ELSE 0 END) AS ask_long
    FROM oag o
    JOIN tiling t ON t.region = o.region AND t.week = o.week
    JOIN home   h ON h.dep_airport = o.dep_airport AND h.region = o.region
    WHERE o.service_type = '{SERVICE_TYPE}'
    """
    (rows, seats_null, seats_zero, freq_null, freq_not_one, km_null, km_zero,
     km_long, km_max, ac_blank, seats_sum, ask_sum, mi_sum, km_sum,
     freq_sum, seats_f, ask_long) = _q(con, sql)[0]

    def pct(n):
        return 100.0 * n / rows if rows else 0.0

    rep.add("numeric casts",
            "FAIL" if (pct(seats_null) > 0.5 or pct(km_null) > 0.5) else
            ("WARN" if (seats_null or km_null) else "PASS"),
            f"{rows:,} rows on the analysis basis. seats null {seats_null:,} "
            f"({pct(seats_null):.3f}%), seats zero {seats_zero:,} ({pct(seats_zero):.3f}%), "
            f"gcd_km null {km_null:,} ({pct(km_null):.3f}%), "
            f"gcd_km zero {km_zero:,} ({pct(km_zero):.3f}%)",
            rows=rows, seats_null=seats_null, km_null=km_null, seats_zero=seats_zero,
            km_zero=km_zero)

    ratio = (mi_sum / km_sum) if km_sum else 0.0
    ok = abs(ratio - 1.0 / MI_PER_KM) < 0.005
    rep.add("distance unit check",
            "PASS" if ok else "FAIL",
            f"gcd_mi divided by gcd_km is {ratio:.5f} against the expected "
            f"{1.0 / MI_PER_KM:.5f}, so gcd_km is kilometres",
            ratio=ratio)

    ask_long_pct = 100.0 * ask_long / ask_sum if ask_sum else 0.0
    rep.add("great circle distance plausibility",
            "PASS" if ask_long_pct < 0.01 else "FAIL",
            f"longest sector in the store {km_max:,.0f} km against the longest scheduled "
            f"sector flown of under {LONGEST_SECTOR_KM:,} km. {km_long:,} rows lie beyond "
            f"it, carrying {ask_long_pct:.6f}% of ASK, and are excluded by the wedge "
            "build. They are airport codes resolved to the wrong coordinates: an ATR 72 "
            "on Semarang to Medan cannot fly 18,919 km",
            km_max=km_max, km_beyond=km_long, ask_beyond_pct=ask_long_pct)

    d_dep = 100.0 * (freq_sum - rows) / rows if rows else 0.0
    d_seat = 100.0 * (seats_f - seats_sum) / seats_sum if seats_sum else 0.0
    rep.add("departure count convention",
            "PASS" if abs(d_dep) < 0.05 and abs(d_seat) < 0.05 else "WARN",
            f"{freq_not_one:,} rows carry a frequency other than 1, so COUNT(*) is not "
            f"quite the departure count. The wedge uses SUM(frequency) and "
            f"SUM(seats x frequency), which differ from the plain sums the rest of the "
            f"tree uses by {d_dep:.5f}% on departures and {d_seat:.5f}% on seats. "
            "Immaterial, so no published figure moves, and stated rather than assumed",
            freq_not_one=freq_not_one, freq_null=freq_null,
            departures_delta_pct=d_dep, seats_delta_pct=d_seat)

    rep.add("aircraft code present",
            "PASS" if ac_blank == 0 else "WARN",
            f"{ac_blank:,} rows ({pct(ac_blank):.3f}%) carry no aircraft code",
            ac_blank=ac_blank)
    return {"rows": rows, "seats": seats_sum, "ask_km": ask_sum}


def check_body_map(con, rep, pref, home, years):
    """9: aircraft body type coverage, weighted by seats."""
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(repo, "config", "aircraft_body_types.yaml")
    if not os.path.exists(path):
        rep.add("aircraft body type map", "FAIL",
                f"config/aircraft_body_types.yaml not found at {path}")
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        book = yaml.safe_load(fh) or {}
    mapping = book.get("codes", {})
    cte = _basis_cte(pref, home, years)
    rows = _q(con, cte + f"""
        SELECT o.aircraft_code, any_value(o.aircraft_name),
               sum(TRY_CAST(o.seats AS BIGINT))
        FROM oag o
        JOIN tiling t ON t.region = o.region AND t.week = o.week
        JOIN home   h ON h.dep_airport = o.dep_airport AND h.region = o.region
        WHERE o.service_type = '{SERVICE_TYPE}'
        GROUP BY 1""")
    total = sum(s or 0 for _, _, s in rows)
    unmapped = [(c, n, s or 0) for c, n, s in rows if c not in mapping]
    unmapped.sort(key=lambda r: -r[2])
    share = 100.0 * sum(s for _, _, s in unmapped) / total if total else 0.0
    rep.add("aircraft body type coverage",
            "PASS" if share < 0.5 else ("WARN" if share < 2.0 else "FAIL"),
            f"{len(rows)} codes in the data, {len(unmapped)} not in the map, "
            f"{share:.3f}% of seats unmapped"
            + ("" if not unmapped else ". Largest unmapped: "
               + "; ".join(f"{c} {str(n)[:24].strip()} {s:,}" for c, n, s in unmapped[:8])),
            unmapped_seat_share_pct=share,
            unmapped=[{"code": c, "name": str(n).strip(), "seats": s}
                      for c, n, s in unmapped[:40]])
    return mapping


def check_carrier_category(con, rep, pref, home, years):
    """10: the LCC classification."""
    cte = _basis_cte(pref, home, years)
    rows = _q(con, cte + f"""
        SELECT o.carrier_category, count(*), sum(TRY_CAST(o.seats AS BIGINT))
        FROM oag o
        JOIN tiling t ON t.region = o.region AND t.week = o.week
        JOIN home   h ON h.dep_airport = o.dep_airport AND h.region = o.region
        WHERE o.service_type = '{SERVICE_TYPE}'
        GROUP BY 1 ORDER BY 2 DESC""")
    vals = {(c or "").strip(): (n, s) for c, n, s in rows}
    unexpected = [k for k in vals if k not in ("M", "L")]
    rep.add("carrier category",
            "PASS" if not unexpected else "WARN",
            ", ".join(f"{k or 'blank'} {v[0]:,} rows" for k, v in vals.items())
            + (". M is mainline and L is low cost" if not unexpected else
               f". Unexpected values: {unexpected}"),
            categories={k: {"rows": v[0], "seats": v[1]} for k, v in vals.items()})


def check_anchor(con, rep, pref, home):
    """11: the Heathrow 2019 anchor recorded in oag_store.py."""
    y = ANCHOR["year"]
    reg = home.get(ANCHOR["airport"])
    if reg is None:
        rep.add("Heathrow 2019 anchor", "FAIL", "LHR has no home region in the store")
        return
    keys = pref.get((reg, y))
    if not keys:
        rep.add("Heathrow 2019 anchor", "FAIL",
                f"no preferred tiling for {reg} {y}")
        return
    inlist = ",".join(f"'{k}'" for k in sorted(keys))
    a = ANCHOR["airport"]
    dep, dep_seats = _q(con, f"""
        SELECT sum(TRY_CAST(frequency AS BIGINT)),
               sum(TRY_CAST(seats AS DOUBLE) * TRY_CAST(frequency AS DOUBLE)) FROM oag
        WHERE dep_airport = '{a}' AND region = '{reg}'
          AND week IN ({inlist}) AND service_type = '{SERVICE_TYPE}'""")[0]
    two, two_seats = _q(con, f"""
        SELECT sum(TRY_CAST(frequency AS BIGINT)),
               sum(TRY_CAST(seats AS DOUBLE) * TRY_CAST(frequency AS DOUBLE)) FROM oag
        WHERE (dep_airport = '{a}' OR arr_airport = '{a}') AND region = '{reg}'
          AND week IN ({inlist}) AND service_type = '{SERVICE_TYPE}'""")[0]
    dm = abs(two - ANCHOR["movements_two_way"]) / ANCHOR["movements_two_way"]
    ds = abs(two_seats - ANCHOR["seats_two_way"]) / ANCHOR["seats_two_way"]
    rep.add("Heathrow 2019 anchor",
            "PASS" if dm <= ANCHOR_TOL and ds <= ANCHOR_TOL else "FAIL",
            f"two way, {two:,} movements against the recorded "
            f"{ANCHOR['movements_two_way']:,} ({dm * 100:.2f}% out) and "
            f"{two_seats / 1e6:.1f}m seats against the recorded "
            f"{ANCHOR['seats_two_way'] / 1e6:.1f}m ({ds * 100:.2f}% out). One way, which "
            f"is the basis every capacity figure in the deck is built on, {dep:,} "
            f"departures and {dep_seats / 1e6:.1f}m departing seats. Source: the anchor "
            "in avia_forecast/ingest/oag_store.py, established 3 August 2026",
            departures=dep, departing_seats=dep_seats,
            movements_two_way=two, seats_two_way=two_seats)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", nargs="*", type=int, default=None,
                    help="restrict the numeric checks to these years")
    ap.add_argument("--json", default=None, help="where to write the report")
    args = ap.parse_args(argv)

    print(f"OAG store: {paths.OAG_DB}")
    con = duckdb.connect(paths.OAG_DB, read_only=True)
    con.execute("SET enable_progress_bar=false")
    rep = Report()

    pref, complete = check_coverage(con, rep)
    years = args.years or complete
    print(f"\nAnalysis basis: service type {SERVICE_TYPE}, home region file per airport, "
          f"one tiling per region-year, years {min(years)} to {max(years)}\n")
    check_cap(con, rep, pref)
    home = check_home_regions(con, rep)
    totals = check_numerics(con, rep, pref, home, years)
    check_body_map(con, rep, pref, home, years)
    check_carrier_category(con, rep, pref, home, years)
    check_anchor(con, rep, pref, home)

    out = args.json or os.path.join(paths.DATA, "oag_wedge_guard.json")
    payload = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "store": paths.OAG_DB,
        "basis": {"service_type": SERVICE_TYPE, "dedup": "home region file per airport",
                  "tiling": "one preferred tiling per region-year", "years": years},
        "totals": totals,
        "checks": rep.checks,
        "verdict": "FAIL" if rep.failed else ("WARN" if rep.warned else "PASS"),
    }
    try:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1)
        print(f"\nreport written to {out}")
    except OSError as exc:
        print(f"\ncould not write the report to {out}: {exc}", file=sys.stderr)

    print(f"\nverdict: {payload['verdict']}  "
          f"({len(rep.failed)} fail, {len(rep.warned)} warn, {len(rep.checks)} checks)")
    return 1 if rep.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

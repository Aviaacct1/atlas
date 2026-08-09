r"""Schedule-side data for the Observatory OGF deck. Author: Avia Solutions.

Three of the six slides the inventory says we can fill outright come from the OAG store
rather than from the engine, and each needs an aggregation nothing else in the tree
produces. They are built here, once, into a JSON the deck builder reads, so the deck
regenerates when the store moves and nothing is typed into a slide by hand.

  network      Boeing page 18, twenty five years of traffic and network. Airport pairs
               served, departures and ASK with a CAGR on each. Ours is TEN years, 2015
               to 2025, because that is what the store holds, and the deck says so.
  lcc          Boeing page 20, low cost share of intra-regional capacity. The store
               carries OAG's own carrier_category, M for mainline and L for low cost,
               so the classification is OAG's rather than ours and can be cited as
               such. Intra-regional means both ends inside the same OAG macro region,
               taken from the first two characters of dep_region and arr_region.
  business     Boeing page 26, single aisle seat capacity by business model. Single
               aisle here is one aisle and a mainline jet, so it excludes regional
               jets, which is Boeing's segment definition. See the header of
               config/aircraft_body_types.yaml.

Basis throughout, the same as the wedge: service type J, departures only, one preferred
tiling per region-year, each airport read from its home region file, sectors beyond
15,400 km excluded. scripts/guard_oag_wedge.py proves each of those and this refuses to
run if the guard failed.

Usage:  py -3.12 scripts\build_ogf_deck_data.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb  # noqa: E402

from avia_forecast import paths  # noqa: E402
from avia_forecast.ingest.oag_store import preferred_tilings, home_regions  # noqa: E402
from build_fleet_wedge import (  # noqa: E402
    LONGEST_SECTOR_KM, SERVICE_TYPE, cagr, check_guard, load_body_map, segment_of)

YEARS = [2015, 2016, 2017, 2018, 2019, 2023, 2024, 2025]
MACRO = {"AF": "Africa", "AS": "Asia", "EU": "Europe", "LA": "Latin America",
         "ME": "Middle East", "NA": "North America", "SW": "Southwest Pacific"}


def basis_cte(pref, home, years):
    """One tiling per region-year and one home region file per airport, as a literal
    VALUES list. The store is opened read only, so a temporary table is not available.

    Restricted to ONE YEAR at a time by the caller. Read all eight years at once and a
    count of distinct airport pairs has to hold 288m rows of state, which a 4GB host
    will not do: the first attempt at this ran for twelve minutes and produced nothing.
    Year by year the working set is a tenth of that and each year is independent.
    """
    pairs = sorted({(r, y, k) for (r, y), ks in pref.items() if y in years for k in ks})
    tiling = ",".join(f"('{r}',{y},'{k}')" for r, y, k in pairs)
    homes = ",".join(f"('{a}','{r}')" for a, r in sorted(home.items()) if a and a.strip())
    return (f"WITH tiling(region, yr, week) AS (VALUES {tiling}),\n"
            f"     home(dep_airport, region) AS (VALUES {homes})\n")


FILTER = f"""
    FROM oag o
    JOIN tiling t ON t.region = o.region AND t.week = o.week
    JOIN home   h ON h.dep_airport = o.dep_airport AND h.region = o.region
    WHERE o.service_type = '{SERVICE_TYPE}'
      AND TRY_CAST(o.gcd_km AS DOUBLE) > 0
      AND TRY_CAST(o.gcd_km AS DOUBLE) <= {LONGEST_SECTOR_KM}
      AND TRY_CAST(o.seats AS DOUBLE) > 0
"""


def network_year(con, cte, yr):
    """Distinct pairs by grouping first and counting the groups, rather than a
    count(DISTINCT) over every row. Same answer, a fraction of the state."""
    pairs = con.execute(cte + f"""
      SELECT count(*) FROM (
        SELECT o.dep_airport, o.arr_airport {FILTER} GROUP BY 1, 2)""").fetchone()[0]
    dep, ask, aps, cars = con.execute(cte + f"""
      SELECT sum(TRY_CAST(o.frequency AS BIGINT)),
             sum(TRY_CAST(o.seats AS DOUBLE) * TRY_CAST(o.frequency AS DOUBLE)
                 * TRY_CAST(o.gcd_km AS DOUBLE)),
             count(DISTINCT o.dep_airport), count(DISTINCT o.carrier)
      {FILTER}""").fetchone()
    return pairs, dep, ask, aps, cars


def network(con, pref, home, years):
    out = {"years": [], "airport_pairs": {}, "departures": {}, "ask_bn": {},
           "airports": {}, "carriers": {}}
    for yr in years:
        cte = basis_cte(pref, home, [yr])
        pairs, dep, ask, aps, cars = network_year(con, cte, yr)
        print(f"  network {yr}: {pairs:,} pairs, {dep:,} departures, "
              f"{ask / 1e9:,.0f}bn ASK")
        out["years"].append(yr)
        out["airport_pairs"][str(yr)] = pairs
        out["departures"][str(yr)] = dep
        out["ask_bn"][str(yr)] = ask / 1e9
        out["airports"][str(yr)] = aps
        out["carriers"][str(yr)] = cars
    y0, y1 = out["years"][0], out["years"][-1]
    n = y1 - y0
    out["cagr"] = {k: cagr(out[k][str(y0)], out[k][str(y1)], n)
                   for k in ("airport_pairs", "departures", "ask_bn")}
    out["window"] = [y0, y1]
    out["note"] = ("Airport pairs are directional origin to destination pairs with at "
                   "least one scheduled passenger departure in the year. 2020 to 2022 "
                   "are not held in the store and are absent from the series, so the "
                   "line is drawn with a break rather than joined across the gap.")
    return out


def lcc(con, pref, home, years):
    rows = []
    for yr in years:
        cte = basis_cte(pref, home, [yr])
        rows += con.execute(cte + f"""
          SELECT {yr} AS yr, substr(o.dep_region, 1, 2) AS macro,
                 o.carrier_category AS cat,
                 sum(TRY_CAST(o.seats AS DOUBLE) * TRY_CAST(o.frequency AS DOUBLE))
          {FILTER} AND substr(o.dep_region, 1, 2) = substr(o.arr_region, 1, 2)
          GROUP BY 1, 2, 3""").fetchall()
    agg = {}
    for yr, macro, cat, seats in rows:
        name = MACRO.get(macro, macro)
        d = agg.setdefault(name, {}).setdefault(str(yr), {"L": 0.0, "M": 0.0})
        d[(cat or "M").strip() or "M"] = d.get((cat or "M").strip(), 0.0) + (seats or 0)
    out = {}
    for name, byyr in sorted(agg.items()):
        out[name] = {y: (v["L"] / (v["L"] + v["M"]) if (v["L"] + v["M"]) else None)
                     for y, v in sorted(byyr.items())}
        out[name + " (intra-regional seats m)"] = {
            y: (v["L"] + v["M"]) / 1e6 for y, v in sorted(byyr.items())}
    return {"share_of_seats": out,
            "note": ("Low cost share of seats on flights with both ends inside the same "
                     "OAG macro region. The mainline and low cost split is OAG's own "
                     "carrier_category field, not an Avia classification.")}


def business_model(con, pref, home, years, bmap):
    rows = []
    for yr in years:
        cte = basis_cte(pref, home, [yr])
        rows += con.execute(cte + f"""
          SELECT {yr} AS yr, o.aircraft_code, o.carrier_category,
                 sum(TRY_CAST(o.seats AS DOUBLE) * TRY_CAST(o.frequency AS DOUBLE)),
                 sum(TRY_CAST(o.frequency AS BIGINT))
          {FILTER} GROUP BY 1, 2, 3""").fetchall()
    out = {}
    for yr, code, cat, seats, dep in rows:
        if segment_of(code, bmap) != "single_aisle":
            continue
        c = "low cost" if (cat or "").strip() == "L" else "mainline"
        d = out.setdefault(c, {}).setdefault(str(yr), [0.0, 0.0])
        d[0] += seats or 0
        d[1] += dep or 0
    res = {}
    for c, byyr in out.items():
        res[c] = {"seats_m": {y: v[0] / 1e6 for y, v in sorted(byyr.items())},
                  "departures": {y: v[1] for y, v in sorted(byyr.items())},
                  "seats_per_departure": {y: (v[0] / v[1] if v[1] else None)
                                          for y, v in sorted(byyr.items())}}
    return {"single_aisle": res,
            "note": ("Single aisle is one aisle and a mainline jet, which excludes "
                     "regional jets, matching Boeing's segment. Business model is OAG's "
                     "carrier_category.")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-guard-check", action="store_true")
    ap.add_argument("--years", nargs="*", type=int, default=YEARS)
    ap.add_argument("--memory", default="6GB",
                    help="duckdb memory limit. Lower it on a small host; the year by "
                         "year loop keeps the working set inside it either way")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    check_guard(args.skip_guard_check)
    con = duckdb.connect(paths.OAG_DB, read_only=True)
    con.execute("SET enable_progress_bar=false")
    con.execute(f"SET memory_limit='{args.memory}'")
    if paths.DUCKDB_TMP:
        con.execute(f"SET temp_directory='{paths.DUCKDB_TMP}'")
    pref, home = preferred_tilings(con), home_regions(con)
    bmap = load_body_map()

    out = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": ("Avia Solutions analysis of the OAG schedule store, service type J, "
                   "departures only, one tiling per region-year, each airport read from "
                   "its home region file"),
        "years_held": args.years,
        "years_absent": [2020, 2021, 2022],
        "network": network(con, pref, home, args.years),
        "lcc": lcc(con, pref, home, args.years),
        "business_model": business_model(con, pref, home, args.years, bmap),
    }
    n = out["network"]
    if all(n["cagr"].get(k) is not None for k in n["cagr"]):
        print(f"network {n['window'][0]} to {n['window'][1]}: "
              f"airport pairs {n['cagr']['airport_pairs'] * 100:+.1f}% a year, "
              f"departures {n['cagr']['departures'] * 100:+.1f}%, "
              f"ASK {n['cagr']['ask_bn'] * 100:+.1f}%")
    else:
        print("network: a single year was requested, so there is no CAGR to report")
    for reg, ser in out["lcc"]["share_of_seats"].items():
        if "seats m" in reg:
            continue
        a, b = ser.get("2015"), ser.get("2025")
        if a and b:
            print(f"LCC intra-{reg}: {a * 100:.1f}% of seats in 2015 to {b * 100:.1f}% "
                  "in 2025")
    sa = out["business_model"]["single_aisle"]
    for c, v in sa.items():
        print(f"single aisle {c}: {v['seats_m']['2015']:,.0f}m seats 2015 to "
              f"{v['seats_m']['2025']:,.0f}m 2025, gauge "
              f"{v['seats_per_departure']['2015']:.0f} to "
              f"{v['seats_per_departure']['2025']:.0f}")

    dest = args.json or os.path.join(paths.DATA, "ogf_deck_data.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"written to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

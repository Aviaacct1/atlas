"""Fare LEVELS at last: the series the affordability gap analysis has lacked.

The product's fare series is a cost-driven index with no level, so real fare against
income could not be drawn, and that is the mechanism behind the remaining regional
gaps against Boeing (Southeast Asia, Africa, the Middle East, China). Discovery on
23 August 2026 found the levels were in the estate all along: the Sabre store holds
avg_total_fare_usd, revenue, passengers and distance per itinerary-year, and the DB1B
store holds an aggregated od_market table with average market fares by year.

Licensing basis (John's ruling, 16 August 2026): DOT DB1B is public and fully
citable, so the US series publishes under its own name; Sabre raw fares are used
freely inside the model and only derived outcomes and indices publish.

Guards, before any number:
  - Fare metrics are computed ONLY over fare-bearing rows (avg_total_fare_usd > 0),
    with the fare-bearing share of passengers reported per year; a year-region below
    80% coverage is flagged on the output, not silently included.
  - 2020-2022 are excluded by the store policy the estate already applies (2020
    absent; the 2021 slice reports more passengers than 2022).
  - Sabre 2013 and 2015 are point-of-origin; every other year is nondirectional
    (app/sabre_directionality_check.py, meridian). Levels per year are comparable;
    the basis note travels in the output.
  - Real terms deflate USD by US CPI (data/us_cpi_annual.json, World Bank, retrieved
    23 August 2026), base 2024, ending 2024 because 2025 CPI is unpublished. A stated
    basis: Sabre fares are USD everywhere, so this is purchasing power against the
    dollar, not against local income.

Writes data/fare_levels_exhibit.json (dump_atomic). Runs where E: is local:

    py -3.12 scripts\\build_fare_levels.py

Author: Avia Solutions. 23 August 2026.
"""
from __future__ import annotations
import json
import os
import sys

import duckdb

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from avia_forecast.io_safe import dump_atomic
from avia_forecast.paths import SABRE_DB, AVIA

EXCLUDE_YEARS = (2020, 2021, 2022)
COVERAGE_FLOOR = 0.80


def load_cpi():
    d = json.load(open(os.path.join(REPO, "data", "us_cpi_annual.json")))
    cpi = {int(y): v for y, v in d["cpi"].items()}
    base = cpi[2024]
    return cpi, base, d["meta"]


def sabre_levels(cpi, base):
    con = duckdb.connect(SABRE_DB, read_only=True)
    q = f"""
      SELECT year, poo_region_name AS region,
             sum(passengers)                                                    AS pax_all,
             sum(CASE WHEN avg_total_fare_usd > 0 THEN passengers END)          AS pax_f,
             sum(CASE WHEN avg_total_fare_usd > 0 THEN total_revenue_usd END)   AS rev_f,
             sum(CASE WHEN avg_total_fare_usd > 0 AND distance_km > 0
                      THEN passengers * distance_km END)                        AS paxkm_f
      FROM sabre
      WHERE passengers > 0 AND year NOT IN {EXCLUDE_YEARS}
      GROUP BY 1, 2
    """
    rows = con.execute(q).fetchall()
    con.close()
    out, flags = {}, []
    for year, region, pax_all, pax_f, rev_f, paxkm_f in rows:
        if not (region and pax_f and rev_f):
            continue
        cov = pax_f / pax_all if pax_all else 0.0
        fare = rev_f / pax_f
        yld = (rev_f / paxkm_f) if paxkm_f else None
        e = {"pax_m": round(pax_all / 1e6, 2), "fare_coverage": round(cov, 3),
             "fare_usd": round(fare, 2),
             "yield_usd_km": round(yld, 4) if yld else None}
        if int(year) in cpi:
            e["fare_real_usd_2024"] = round(fare * base / cpi[int(year)], 2)
        if cov < COVERAGE_FLOOR:
            e["flag"] = f"fare-bearing coverage {cov:.0%} below the {COVERAGE_FLOOR:.0%} floor"
            flags.append((int(year), region, cov))
        out.setdefault(region, {})[int(year)] = e
    # world = aggregate of the same fare-bearing rows
    world = {}
    for region, ys in out.items():
        for y, e in ys.items():
            w = world.setdefault(y, {"pax_m": 0.0, "_rev": 0.0, "_paxf": 0.0, "_paxkm": 0.0})
            w["pax_m"] += e["pax_m"]
            paxf = e["pax_m"] * 1e6 * e["fare_coverage"]
            w["_paxf"] += paxf
            w["_rev"] += paxf * e["fare_usd"]
            if e.get("yield_usd_km"):
                w["_paxkm"] += paxf * e["fare_usd"] / e["yield_usd_km"]
    for y, w in world.items():
        w["fare_usd"] = round(w["_rev"] / w["_paxf"], 2) if w["_paxf"] else None
        w["yield_usd_km"] = round(w["_rev"] / w["_paxkm"], 4) if w["_paxkm"] else None
        if y in cpi and w["fare_usd"]:
            w["fare_real_usd_2024"] = round(w["fare_usd"] * base / cpi[y], 2)
        w["pax_m"] = round(w["pax_m"], 1)
        for k in ("_rev", "_paxf", "_paxkm"):
            w.pop(k)
    return out, world, flags


def db1b_levels(cpi, base):
    con = duckdb.connect(os.path.join(AVIA, "db1b.duckdb"), read_only=True)
    rows = con.execute("""
        SELECT year, sum(pax) AS pax, sum(pax * avg_fare) / sum(pax) AS fare
        FROM od_market WHERE pax > 0 AND avg_fare > 0
        GROUP BY 1 ORDER BY 1""").fetchall()
    con.close()
    out = {}
    for year, pax, fare in rows:
        y = int(year)
        e = {"pax_m": round(pax / 1e6, 1), "fare_usd": round(fare, 2)}
        if y in cpi:
            e["fare_real_usd_2024"] = round(fare * base / cpi[y], 2)
        out[y] = e
    return out


def main():
    cpi, base, cpi_meta = load_cpi()
    print("Sabre scan (one pass of the store; a few minutes on the workstation)...")
    sab, world, flags = sabre_levels(cpi, base)
    us = db1b_levels(cpi, base)

    exhibit = {
        "meta": {
            "built": "2026-08-23",
            "basis": ("Sabre: sum(total_revenue_usd)/sum(passengers) over fare-bearing "
                      "rows only, by point-of-origin region and year; yield divides by "
                      "passenger-km. DB1B od_market: pax-weighted average market fare, "
                      "US, public and citable. Real terms: USD deflated by US CPI, base "
                      "2024. 2020-2022 excluded by store policy; Sabre 2013 and 2015 "
                      "are point-of-origin, other years nondirectional."),
            "licensing": ("DB1B publishes under its own name; Sabre-derived figures "
                          "publish as outcomes and indices only, never raw rows "
                          "(ruling of 16 August 2026)."),
            "cpi": cpi_meta,
        },
        "us_db1b": us,
        "sabre_regions": sab,
        "world": world,
        "coverage_flags": [{"year": y, "region": r, "coverage": round(c, 3)}
                           for y, r, c in sorted(flags)],
    }
    dump_atomic(exhibit, os.path.join(REPO, "data", "fare_levels_exhibit.json"), indent=1)

    print("\nUS (DB1B, citable), real 2024 USD:")
    ys = sorted(y for y in us if "fare_real_usd_2024" in us[y])
    for y in ys:
        print(f"  {y}: ${us[y]['fare_real_usd_2024']:.0f}  ({us[y]['pax_m']}m pax)")
    if len(ys) >= 2:
        y0, y1 = ys[0], ys[-1]
        chg = us[y1]["fare_real_usd_2024"] / us[y0]["fare_real_usd_2024"] - 1
        print(f"  real change {y0}-{y1}: {chg:+.1%}  (Boeing CMO 2026 states circa -25% "
              f"over the past decade; this is the cross-check)")

    print("\nWorld (Sabre-derived outcome), real 2024 USD per passenger:")
    for y in sorted(y for y in world if world[y].get("fare_real_usd_2024")):
        w = world[y]
        print(f"  {y}: ${w['fare_real_usd_2024']:.0f}  yield ${w['yield_usd_km']:.4f}/km  "
              f"({w['pax_m']:,.0f}m pax)")
    if flags:
        print(f"\n{len(flags)} year-region cells below the fare coverage floor are "
              f"flagged in the exhibit, not dropped.")
    print("\nexhibit -> data/fare_levels_exhibit.json")
    print("Next (September): the real-fare-vs-income exhibit per region joins these "
          "levels to the OEF income paths, and the affordability term enters the model "
          "as a measured change, never before.")


if __name__ == "__main__":
    main()

r"""What the airports missing from the forecast base are worth. Author: Avia Solutions.

Found on 9 August 2026 while building the fleet wedge: Beijing Daxing and Chengdu
Tianfu carry no record in data/global_airport_meta_2025.json and therefore none in
data/global_base_od_2025.json, which is the base the whole forecast is built on. They
are not missing from the data. preagg.duckdb od_p2p holds 20.4m outbound O&D for PKX in
2025 and 23.5m for TFU. They are dropped at one line of scripts/ingest_global_base.py:

    oc = apc.get(o)
    if oc is None:
        pax_origin_unmapped += pax
        continue

apc is the airport to country reference table in the Meridian application folder. An
origin absent from it is added to a running total and abandoned. The total IS reported,
at 3.22% of world outbound O&D, and 3.22% reads as acceptable noise. It is not silent,
it is aggregated, which is worse: a number small enough to ignore with the two largest
new airports in China inside it. This script opens the aggregate and names what is in
it, which is the thing the ingest report should have done from the start.

It measures and changes nothing. Fixing it means adding the missing codes to the
Meridian reference table and re-running the ingest, which moves the base year, every
regional total and the Boeing reconciliation at once. That is John's call.

Usage:  py -3.12 scripts\measure_missing_airports.py [--year 2025]
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

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEMS = [("Beijing", ["PEK", "PKX", "NAY"]), ("Chengdu", ["CTU", "TFU"]),
           ("Mexico City", ["MEX", "NLU", "TLC"]), ("Jakarta", ["CGK", "HLP"])]
SYSTEM_YEARS = [2015, 2019, 2025]


def boeing_regions():
    with open(os.path.join(REPO, "config", "region_schemes.yaml"),
              "r", encoding="utf-8") as fh:
        sch = (yaml.safe_load(fh) or {})["schemes"]["boeing_cmo"]
    out = {}
    for region, codes in sch["regions"].items():
        for c in codes:
            out[str(c).upper()] = region
    return out, sch.get("default", "Unassigned")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)
    yr = args.year

    meta_path = os.path.join(REPO, "data", f"global_airport_meta_{yr}.json")
    with open(meta_path, "r", encoding="utf-8") as fh:
        meta = json.load(fh)
    with open(os.path.join(REPO, "data", "airport_regress.json"),
              "r", encoding="utf-8") as fh:
        fits = json.load(fh)
    iso, default = boeing_regions()

    con = duckdb.connect(paths.PREAGG, read_only=True)
    con.execute("SET enable_progress_bar=false")
    rows = con.execute("SELECT o, sum(pax)/1e6 FROM od_p2p WHERE year = ? GROUP BY 1",
                       [yr]).fetchall()
    con.close()
    total = sum(p for _, p in rows)
    absent = sorted(((a, p) for a, p in rows if a not in meta), key=lambda x: -x[1])
    absent_pax = sum(p for _, p in absent)

    # Country for the absent airports, from the OAG store, which does hold them.
    oag = duckdb.connect(paths.OAG_DB, read_only=True)
    oag.execute("SET enable_progress_bar=false")
    inlist = ",".join("'" + a.replace("'", "''") + "'" for a, _ in absent)
    country = dict(oag.execute(
        f"""SELECT dep_airport, mode(dep_country) FROM oag
            WHERE dep_airport IN ({inlist}) GROUP BY 1""").fetchall()) if absent else {}

    print(f"Base year {yr}, outbound O&D from preagg od_p2p: {total:,.1f}m across "
          f"{len(rows):,} origin airports")
    print(f"Absent from the forecast base: {len(absent):,} airports, "
          f"{absent_pax:,.1f}m pax, {100 * absent_pax / total:.2f}% of the world total")
    print(f"Of those, {len(absent) - len(country):,} carry no record in the OAG store "
          "either and cannot be attributed to a country here\n")

    print(f"The {args.top} largest, by outbound O&D:")
    print(f"{'code':<6}{'country':<9}{'Boeing region':<17}{'O&D m':>8}")
    by_region = {}
    for a, p in absent[:args.top]:
        cc = country.get(a) or ""
        reg = iso.get(cc.upper(), default if cc else "unattributed")
        print(f"{a:<6}{cc:<9}{reg:<17}{p:>8.3f}")
    for a, p in absent:
        cc = (country.get(a) or "").upper()
        reg = iso.get(cc, default if cc else "unattributed")
        by_region[reg] = by_region.get(reg, 0.0) + p

    # The modelled base by the same region scheme, so the two are comparable.
    modelled = {}
    for a, m in meta.items():
        reg = iso.get(str(m.get("country") or "").upper(), default)
        modelled[reg] = modelled.get(reg, 0.0) + (m.get("term_out_m") or 0.0)

    print(f"\nBy Boeing region, {yr} outbound O&D:")
    print(f"{'region':<17}{'in the base':>13}{'absent':>10}{'absent as % of base':>22}")
    region_rows = []
    for reg in sorted(set(by_region) | set(modelled)):
        inb, ab = modelled.get(reg, 0.0), by_region.get(reg, 0.0)
        share = 100 * ab / inb if inb else None
        region_rows.append({"region": reg, "in_base_m": inb, "absent_m": ab,
                            "absent_pct_of_base": share})
        print(f"{reg:<17}{inb:>12,.1f}m{ab:>9,.1f}m"
              + (f"{share:>21.1f}%" if share is not None else f"{'n/a':>22}"))

    # The multi-airport systems the omission breaks, read from the schedule.
    print(f"\nWhere the omission breaks a city system, departing seats m from the OAG "
          f"store, one way:")
    yrs = ",".join(str(y) for y in SYSTEM_YEARS)
    systems = []
    for name, codes in SYSTEMS:
        inl = ",".join(f"'{c}'" for c in codes)
        got = oag.execute(f"""
            SELECT dep_airport, CAST(substr(week,1,4) AS INT) AS yr,
                   sum(TRY_CAST(seats AS DOUBLE) * TRY_CAST(frequency AS DOUBLE))/1e6
            FROM oag WHERE dep_airport IN ({inl}) AND service_type = 'J'
              AND CAST(substr(week,1,4) AS INT) IN ({yrs})
              AND week NOT LIKE '20__-__-__'
            GROUP BY 1, 2""").fetchall()
        # one region file per airport is not applied here: these are single airports and
        # the home file rule matters only when summing across airports, so read the
        # maximum over region files, which is the home file by definition.
        best = {}
        for a, y, s in got:
            best[(a, y)] = max(best.get((a, y), 0.0), s)
        rec = {"system": name, "airports": {}}
        print(f"\n  {name}")
        for c in codes:
            inbase = "in the base" if c in meta else "ABSENT"
            vals = [best.get((c, y), 0.0) for y in SYSTEM_YEARS]
            fit = fits.get(c)
            note = (f"  own fit bG {fit['bG_est']}, window {fit['window']}, n {fit['n']}"
                    if fit else "  no own fit")
            rec["airports"][c] = {"in_base": c in meta,
                                  "seats_m": dict(zip(map(str, SYSTEM_YEARS), vals)),
                                  "fit": fit and {k: fit[k] for k in
                                                  ("bG_est", "r2", "t", "n", "window")}}
            print(f"    {c} {inbase:<12}"
                  + "".join(f"{v:>9.2f}" for v in vals) + note)
        tot = [sum(best.get((c, y), 0.0) for c in codes) for y in SYSTEM_YEARS]
        inb = [sum(best.get((c, y), 0.0) for c in codes if c in meta)
               for y in SYSTEM_YEARS]
        rec["system_seats_m"] = dict(zip(map(str, SYSTEM_YEARS), tot))
        rec["in_base_seats_m"] = dict(zip(map(str, SYSTEM_YEARS), inb))
        g_sys = (tot[-1] / tot[1] - 1) * 100 if tot[1] else None
        g_base = (inb[-1] / inb[1] - 1) * 100 if inb[1] else None
        rec["change_2019_to_2025_pct"] = {"system": g_sys, "as_the_base_sees_it": g_base}
        print(f"    {'SYSTEM':<6}{'':<12}" + "".join(f"{v:>9.2f}" for v in tot)
              + f"  {SYSTEM_YEARS[1]} to {SYSTEM_YEARS[-1]}: {g_sys:+.1f}%")
        print(f"    {'as the base sees it':<18}"
              + "".join(f"{v:>9.2f}" for v in inb)
              + f"  {SYSTEM_YEARS[1]} to {SYSTEM_YEARS[-1]}: {g_base:+.1f}%")
        systems.append(rec)
    oag.close()

    print("\nThe growth reading is the point, not the level. A city whose new airport is "
          "outside the base reads as a market in decline, and the incumbent's own income "
          "elasticity is fitted on that reading.")

    out = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "year": yr,
        "source": ("preagg.duckdb od_p2p for the base year O&D, "
                   f"data/global_airport_meta_{yr}.json for the forecast airport set, "
                   "the OAG store for country and seats, "
                   "data/airport_regress.json for the fits"),
        "world_od_m": total, "absent_airports": len(absent), "absent_od_m": absent_pax,
        "absent_pct_of_world": 100 * absent_pax / total,
        "largest_absent": [{"code": a, "country": country.get(a),
                            "region": iso.get((country.get(a) or "").upper(),
                                              default if country.get(a) else
                                              "unattributed"),
                            "od_m": p} for a, p in absent[:args.top]],
        "by_region": region_rows,
        "systems": systems,
        "note": ("A measurement. Nothing is changed. The fix is to add the missing "
                 "codes to the Meridian airport_city_country.csv and re-run "
                 "scripts/ingest_global_base.py, which moves the base year and every "
                 "figure built on it."),
    }
    dest = args.json or os.path.join(paths.DATA, f"missing_airports_{yr}.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"\nwritten to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

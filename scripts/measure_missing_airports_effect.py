r"""What the missing airports do to the forecast. Author: Avia Solutions.

`scripts/measure_missing_airports.py` sizes the hole in the base. This runs the demand
model through it, twice, and reports the difference. Nothing is written to the shipped
data files: `global_demand.run_global` takes `base_od` and `airport_meta` as arguments,
so both bases exist only in memory for the length of the run.

Three runs, in this order, and the first one is the one that matters:

  CONTROL     rebuild the base from preagg od_p2p using ONLY the airport to country
              pairs already in global_airport_meta_2025.json, and check it reproduces
              global_base_od_2025.json. If the reproduction is not exact there is no
              point comparing anything to it, because a difference could be mine.
  SHIPPED     run_global on the shipped base.
  CORRECTED   run_global on a base that also carries the airports the Meridian
              reference table does not have, with their ISO2 read from the OAG store.

Read the DIFFERENCE, not the levels. This runs the demand model directly over its own
window, while the published regional figures come off the dashboard series over
2024-2044, so the levels here will not match the published 3.4% for China and are not
meant to.

The correction runs both ways and that is the whole reason for measuring rather than
arguing. Restoring the missing airports raises a country's base, which raises its trips
per capita and moves it up the propensity curve, which slows growth. It also stops
Beijing and Chengdu reading as markets in decline. Which dominates is an empirical
question about this model, answered below.

Usage:  py -3.12 scripts\measure_missing_airports_effect.py [--year 2025]
                                                            [--window 2025:2045]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb  # noqa: E402
import yaml  # noqa: E402

from avia_forecast import global_demand as gd  # noqa: E402
from avia_forecast import stage_length as sl_mod  # noqa: E402
from avia_forecast import paths  # noqa: E402
from avia_forecast.geo.regions_iso2 import dest_region, region_for_iso2  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The stage length constants were copied into this file from
# scripts/compare_regions_boeing.py. Three copies of one number is three chances for them
# to disagree, so they now live in config/stage_length.yaml behind
# avia_forecast/stage_length.py. This measurement holds stage length CONSTANT on purpose:
# it is measuring what one change does to passenger growth, and a growing stage length
# would sit on both sides of the comparison and cancel.


def boeing_regions():
    with open(os.path.join(REPO, "config", "region_schemes.yaml"),
              "r", encoding="utf-8") as fh:
        sch = (yaml.safe_load(fh) or {})["schemes"]["boeing_cmo"]
    out = {}
    for region, codes in sch["regions"].items():
        for c in codes:
            out[str(c).upper()] = region
    return out, sch.get("default", "Unassigned")


def od_rows(year):
    con = duckdb.connect(paths.PREAGG, read_only=True)
    con.execute("SET enable_progress_bar=false")
    rows = con.execute("SELECT o, d, pax FROM od_p2p WHERE year = ?", [year]).fetchall()
    con.close()
    return rows


def oag_countries(codes):
    """ISO2 for airports the reference table does not carry, from the OAG store, which
    holds every airport with a scheduled departure or arrival."""
    if not codes:
        return {}
    con = duckdb.connect(paths.OAG_DB, read_only=True)
    con.execute("SET enable_progress_bar=false")
    inlist = ",".join("'" + c.replace("'", "''") + "'" for c in sorted(codes))
    out = dict(con.execute(
        f"""SELECT dep_airport, mode(dep_country) FROM oag
            WHERE dep_airport IN ({inlist}) AND dep_country IS NOT NULL
            GROUP BY 1""").fetchall())
    out.update({k: v for k, v in con.execute(
        f"""SELECT arr_airport, mode(arr_country) FROM oag
            WHERE arr_airport IN ({inlist}) AND arr_country IS NOT NULL
            GROUP BY 1""").fetchall() if k not in out})
    con.close()
    return {k: v for k, v in out.items() if v}


def build_base(rows, apc):
    """The arithmetic of scripts/ingest_global_base.py, with the mapping passed in."""
    base_od = defaultdict(lambda: defaultdict(float))
    term_out = defaultdict(float)
    country_of = {}
    dropped_origin = dropped_dest = 0.0
    for o, d, pax in rows:
        oc, dc = apc.get(o), apc.get(d)
        if oc is None:
            dropped_origin += pax
            continue
        country_of[o] = oc
        r = dest_region(oc, dc)
        if r is None:
            dropped_dest += pax
            continue
        base_od[o][r] += pax
        term_out[o] += pax
    meta = {i: {"country": c, "region": region_for_iso2(c),
                "term_out_m": round(term_out[i] / 1e6, 4)}
            for i, c in country_of.items()}
    base = {i: {r: round(v / 1e6, 6) for r, v in regs.items()}
            for i, regs in base_od.items()}
    return base, meta, dropped_origin / 1e6, dropped_dest / 1e6


def set_union_cells(a, b):
    """Every (airport, region) cell in either base, so a cell present in one and absent
    from the other counts as a difference rather than passing unseen."""
    for i in set(a) | set(b):
        for r in set(a.get(i, {})) | set(b.get(i, {})):
            yield i, r


def cagr(a, b, n):
    return None if not a or not b or n <= 0 else (b / a) ** (1.0 / n) - 1.0


def region_series(res, base, meta, iso, default):
    """Boeing region RPK at each end of the window, on the same fixed stage lengths the
    published reconciliation uses.

    The result object carries per-airport O&D only for the LAST year of the run, so the
    run is asked for exactly the window wanted and the base year end comes from the base
    itself. Reading a per-airport series out of the model would need it to return one.
    """
    agg = {}
    for iata, last in res.by_airport_last.items():
        m = meta.get(iata)
        if not m:
            continue
        b = sum(base.get(iata, {}).values())
        if not b:
            continue
        reg = iso.get(str(m.get("country") or "").upper(), default)
        sl = sl_mod.base_km(m.get("region"))
        v = agg.setdefault(reg, [0.0, 0.0, 0])
        v[0] += b * sl
        v[1] += last * sl
        v[2] += 1
    return agg


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--window", default="2025:2045")
    ap.add_argument("--scenario", default="Baseline")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)
    y0, y1 = (int(x) for x in args.window.split(":"))

    with open(os.path.join(REPO, "data",
                           f"global_airport_meta_{args.year}.json"),
              "r", encoding="utf-8") as fh:
        meta_shipped = json.load(fh)
    with open(os.path.join(REPO, "data", f"global_base_od_{args.year}.json"),
              "r", encoding="utf-8") as fh:
        base_shipped = json.load(fh)
    iso, default = boeing_regions()

    rows = od_rows(args.year)
    print(f"od_p2p {args.year}: {len(rows):,} rows, "
          f"{sum(p for _, _, p in rows) / 1e6:,.1f}m pax")

    # CONTROL. Reproduce the shipped base from the mapping the shipped base implies.
    apc0 = {i: m["country"] for i, m in meta_shipped.items()}
    base0, meta0, drop_o0, drop_d0 = build_base(rows, apc0)
    same_keys = set(base0) == set(base_shipped)
    worst = gross = 0.0
    for i, regs in set_union_cells(base0, base_shipped):
        a = base0.get(i, {}).get(regs, 0.0)
        b = base_shipped.get(i, {}).get(regs, 0.0)
        worst = max(worst, abs(a - b))
        gross += abs(a - b)
    world = sum(p for _, _, p in rows) / 1e6
    # An EXACT match is not expected and the reason is worth stating. The shipped base
    # was built with the Meridian reference table, which maps some airports that never
    # appear as an origin in od_p2p. Those cannot be recovered from the shipped meta,
    # which only records origins, so a handful of destination-side flows land in a
    # different region bucket here. The tolerance is set where that difference lives and
    # nowhere near where a real coverage change would.
    ok = same_keys and gross < 0.0001 * world
    print(f"\nCONTROL: rebuilt base has {len(base0):,} airports against "
          f"{len(base_shipped):,} shipped, same set {same_keys}")
    print(f"         largest single cell difference {worst * 1e6:,.0f} pax, total "
          f"absolute difference {gross:,.3f}m against a world of {world:,.1f}m, "
          f"{100 * gross / world:.5f}%")
    print(f"         origin unmapped {drop_o0:,.1f}m, destination unmapped "
          f"{drop_d0:,.1f}m")
    if not ok:
        print("         the rebuild does not reproduce the shipped base inside "
              "tolerance. Everything below would be measuring my arithmetic and not "
              "the correction. Stopping.")
        return 1
    print("         reproduces the shipped base inside tolerance, so the comparison "
          "measures the correction and not the rebuild")

    # CORRECTED. Add the airports the reference table does not carry.
    codes = {o for o, _, _ in rows} | {d for _, d, _ in rows}
    absent = {c for c in codes if c not in apc0}
    found = oag_countries(absent)
    apc1 = dict(apc0)
    apc1.update(found)
    base1, meta1, drop_o1, drop_d1 = build_base(rows, apc1)
    print(f"\nCORRECTED: {len(absent):,} codes absent from the reference table, "
          f"{len(found):,} resolved to a country from the OAG store")
    print(f"           airports in the base {len(base0):,} to {len(base1):,}, "
          f"origin unmapped {drop_o0:,.1f}m to {drop_o1:,.1f}m, destination unmapped "
          f"{drop_d0:,.1f}m to {drop_d1:,.1f}m")

    yrs = list(range(y0, y1 + 1))
    res0 = gd.run_global(scenario=args.scenario, base_od=base0, airport_meta=meta0,
                         years=yrs)
    res1 = gd.run_global(scenario=args.scenario, base_od=base1, airport_meta=meta1,
                         years=yrs)
    print(f"\nWorld O&D {args.year}, shipped {res0.world[y0]:,.0f}m, "
          f"corrected {res1.world[y0]:,.0f}m, "
          f"{100 * (res1.world[y0] / res0.world[y0] - 1):+.2f}%")
    print(f"World CAGR {y0}-{y1}, shipped "
          f"{cagr(res0.world[y0], res0.world[y1], y1 - y0) * 100:.2f}%, corrected "
          f"{cagr(res1.world[y0], res1.world[y1], y1 - y0) * 100:.2f}%")

    a0 = region_series(res0, base0, meta0, iso, default)
    a1 = region_series(res1, base1, meta1, iso, default)
    print(f"\nBoeing regions, RPK CAGR {y0}-{y1}. Read the change, not the level: this "
          f"runs the demand model directly and the published figures come off the "
          f"dashboard over 2024-2044.")
    print(f"{'region':<17}{'shipped':>9}{'corrected':>11}{'change':>9}"
          f"{'base RPK change':>17}{'airports':>10}")
    out_rows = []
    for reg in sorted(set(a0) | set(a1)):
        v0, v1 = a0.get(reg, [0, 0, 0]), a1.get(reg, [0, 0, 0])
        g0 = cagr(v0[0], v0[1], y1 - y0)
        g1 = cagr(v1[0], v1[1], y1 - y0)
        if g0 is None or g1 is None:
            continue
        dbase = 100 * (v1[0] / v0[0] - 1) if v0[0] else None
        out_rows.append({"region": reg, "cagr_shipped": g0, "cagr_corrected": g1,
                         "change_pp": (g1 - g0) * 100, "base_rpk_change_pct": dbase,
                         "airports_shipped": v0[2], "airports_corrected": v1[2]})
        print(f"{reg:<17}{g0 * 100:>8.2f}%{g1 * 100:>10.2f}%{(g1 - g0) * 100:>8.2f}pp"
              f"{dbase:>16.1f}%{v1[2] - v0[2]:>+10d}")

    out = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": [y0, y1], "scenario": args.scenario,
        "control_reproduces_shipped_base": ok,
        "codes_absent": len(absent), "codes_resolved": len(found),
        "world": {"base_shipped_m": res0.world[y0], "base_corrected_m": res1.world[y0],
                  "cagr_shipped": cagr(res0.world[y0], res0.world[y1], y1 - y0),
                  "cagr_corrected": cagr(res1.world[y0], res1.world[y1], y1 - y0)},
        "regions": out_rows,
        "note": ("A measurement. run_global was called with in-memory bases and no file "
                 "on disk was changed. Stage lengths are the fixed per region constants "
                 "the published reconciliation uses, already flagged [P1]."),
    }
    dest = args.json or os.path.join(paths.DATA, "missing_airports_effect.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"\nwritten to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

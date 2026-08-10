r"""What extending the World Bank ingest to every country does to the forecast.
Author: Avia Solutions.

`MEASUREMENTS.md` section 4 records that `data/worldbank_pop_gdppc.json` holds 30
countries, so `global_demand.country_headroom` returns None for the other 199 in the base
and 734m of 3,341m outbound O&D, 22% of the world, compounds with no propensity ceiling.
The same record also sets maturity in `global_demand._maturity`, so a country without one
takes its region's default elasticity rather than its own GDP per head. Both channels
move when the ingest is extended, and they do not move in the same direction, which is
why this measures rather than argues.

Nothing is written. `global_demand._load` is redirected for the World Bank file alone,
for the length of each run, so every case runs against the same base, the same meta and
the same assumptions book, and the only thing that differs is the country record.

Three cases:

  SHIPPED    the 30 countries as they ship.
  COVERAGE   those same 30 records unchanged, plus every further country the ingest can
             fill. This isolates coverage: no existing number moves.
  REFRESHED  every country taken from the new pull at one vintage, so the 30 move to the
             current observation as well. Coverage plus vintage.

Read SHIPPED to COVERAGE as the effect of the decision, and COVERAGE to REFRESHED as the
price of the vintage moving at the same time.

Usage:
    py -3.12 scripts\measure_worldbank_coverage.py --staging data\_wb_staging.json
    py -3.12 scripts\measure_worldbank_coverage.py --staging FILE --json out.json

The staging file is what `scripts/ingest_worldbank.py` pulls from the World Bank API,
in the form {"pop": {ISO2: {"value", "year"}}, "gdp": {ISO2: {"value", "year"}}}.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml  # noqa: E402

from avia_forecast import global_demand as gd  # noqa: E402
from avia_forecast import stage_length as sl_mod  # noqa: E402
from avia_forecast.config import get  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")

# The stage length constants used to be copied into this file from
# scripts/compare_regions_boeing.py. They now live in config/stage_length.yaml behind
# avia_forecast/stage_length.py. Stage length is held CONSTANT here on purpose: this
# measures what one change does to passenger growth, and a growing stage length would sit
# on both sides of the comparison and cancel.

WB_FILE = "worldbank_pop_gdppc.json"


def boeing_regions():
    with open(os.path.join(REPO, "config", "region_schemes.yaml"), encoding="utf-8") as fh:
        sch = (yaml.safe_load(fh) or {})["schemes"]["boeing_cmo"]
    out = {}
    for region, codes in sch["regions"].items():
        for c in codes:
            out[str(c).upper()] = region
    return out, sch.get("default", "Unassigned")


def cagr(a, b, n):
    return None if not a or not b or n <= 0 else (b / a) ** (1.0 / n) - 1.0


def run_with(wb_data, base, meta, scenario="Baseline", years=None):
    """run_global with the World Bank record replaced, and nothing else touched."""
    real = gd._load

    def patched(name):
        if name == WB_FILE:
            return {"data": wb_data}
        return real(name)

    gd._load = patched
    try:
        return gd.run_global(scenario=scenario, base_od=base, airport_meta=meta, years=years)
    finally:
        gd._load = real


def region_agg(res, base, meta, iso, default):
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


def country_agg(res, base, meta):
    """Country level O&D at each end, for the movers table."""
    out = {}
    for iata, last in res.by_airport_last.items():
        c = (meta.get(iata) or {}).get("country")
        if not c:
            continue
        v = out.setdefault(c, [0.0, 0.0])
        v[0] += sum(base.get(iata, {}).values())
        v[1] += last
    return out


def maturity_of(country, region, wb):
    thr = get("global_drivers.maturity_gdppc_threshold_usd")
    rec = wb.get(country)
    if rec and rec.get("gdp_pc_ppp"):
        return "mature" if rec["gdp_pc_ppp"] >= thr else "emerging"
    return "mature" if region in get("global_drivers.mature_regions_default") else "emerging"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staging", required=True, help="the World Bank pull, pop and gdp by ISO2")
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--window", default=None,
                    help="run window, for example 2025:2045. Default is the full horizon "
                         "in the assumptions book")
    ap.add_argument("--scenario", default="Baseline")
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)

    base = json.load(open(os.path.join(DATA, f"global_base_od_{a.year}.json")))
    meta = json.load(open(os.path.join(DATA, f"global_airport_meta_{a.year}.json")))
    shipped = json.load(open(os.path.join(DATA, WB_FILE)))["data"]
    stage = json.load(open(a.staging))
    iso, default = boeing_regions()

    need, region_of = {}, {}
    for iata, regs in base.items():
        c = meta[iata]["country"]
        need[c] = need.get(c, 0.0) + sum(regs.values())
        region_of[c] = meta[iata]["region"]
    world_od = sum(need.values())

    pulled = {}
    for c in sorted(set(stage["pop"]) & set(stage["gdp"])):
        pulled[c] = {"pop": int(round(stage["pop"][c]["value"])),
                     "gdp_pc_ppp": round(stage["gdp"][c]["value"]),
                     "pop_year": stage["pop"][c]["year"], "gdp_year": stage["gdp"][c]["year"]}

    coverage = dict(shipped)
    coverage.update({c: r for c, r in pulled.items() if c not in shipped})
    refreshed = dict(pulled)

    cases = [("SHIPPED", shipped), ("COVERAGE", coverage), ("REFRESHED", refreshed)]

    print(f"Base {a.year}: {len(need)} countries, {world_od:,.1f}m outbound O&D\n")
    print(f"{'case':<11}{'countries':>10}{'base countries':>16}{'O&D ceilinged':>15}{'share':>8}")
    for name, wb in cases:
        hit = [c for c in need if c in wb]
        print(f"{name:<11}{len(wb):>10}{len(hit):>16}{sum(need[c] for c in hit):>14,.0f}m"
              f"{100 * sum(need[c] for c in hit) / world_od:>7.1f}%")

    still = sorted(((m, c) for c, m in need.items() if c not in refreshed), reverse=True)
    if still:
        print(f"\nStill without a record after the pull, {len(still)} countries, "
              f"{sum(m for m, _ in still):,.1f}m, {100 * sum(m for m, _ in still) / world_od:.1f}%:")
        print("  " + ", ".join(f"{c} {m:.1f}m" for m, c in still[:20]))

    flips = [(need[c], c, maturity_of(c, region_of[c], shipped), maturity_of(c, region_of[c], coverage))
             for c in need]
    flips = sorted(((m, c, x, y) for m, c, x, y in flips if x != y), reverse=True)
    print(f"\nMaturity flips on coverage: {len(flips)} countries, "
          f"{sum(m for m, _, _, _ in flips):,.1f}m outbound O&D")
    for m, c, x, y in flips[:15]:
        print(f"  {c} {m:>7.1f}m  {x} to {y}")

    win = None
    if a.window:
        w0, w1 = (int(x) for x in a.window.split(":"))
        win = list(range(w0, w1 + 1))

    results, aggs, ctys = {}, {}, {}
    for name, wb in cases:
        res = run_with(wb, base, meta, a.scenario, win)
        results[name] = res
        aggs[name] = region_agg(res, base, meta, iso, default)
        ctys[name] = country_agg(res, base, meta)

    yrs = results["SHIPPED"].years
    y0, yl = yrs[0], yrs[-1]
    marks = [y for y in (2045, 2050, yl) if y in yrs]
    marks = sorted(set(marks))
    print(f"\nWorld O&D departing passengers, {a.scenario}, run window {y0}-{yl}")
    print(f"{'case':<11}{str(y0):>10}" + "".join(f"{str(y):>10}" for y in marks)
          + f"{f'CAGR {y0}-{yl}':>14}")
    for name, _ in cases:
        w = results[name].world
        print(f"{name:<11}{w[y0]:>9,.0f}m" + "".join(f"{w[y]:>9,.0f}m" for y in marks)
              + f"{cagr(w[y0], w[yl], yl - y0) * 100:>13.2f}%")

    n = yl - y0
    print(f"\nBoeing regions, RPK CAGR {y0}-{yl}, on the fixed stage lengths the "
          f"reconciliation uses. Read the change, not the level.")
    print(f"{'region':<17}{'shipped':>9}{'coverage':>10}{'change':>9}{'refreshed':>11}{'change':>9}")
    rows = []
    for reg in sorted(set(aggs["SHIPPED"])):
        g = {}
        for name, _ in cases:
            v = aggs[name].get(reg, [0, 0, 0])
            g[name] = cagr(v[0], v[1], n)
        if g["SHIPPED"] is None:
            continue
        rows.append({"region": reg, **{k.lower(): g[k] for k in g},
                     "change_pp": (g["COVERAGE"] - g["SHIPPED"]) * 100,
                     "refresh_pp": (g["REFRESHED"] - g["SHIPPED"]) * 100})
        print(f"{reg:<17}{g['SHIPPED']*100:>8.2f}%{g['COVERAGE']*100:>9.2f}%"
              f"{(g['COVERAGE']-g['SHIPPED'])*100:>8.2f}pp{g['REFRESHED']*100:>10.2f}%"
              f"{(g['REFRESHED']-g['SHIPPED'])*100:>8.2f}pp")
    tot = {name: [sum(v[0] for v in aggs[name].values()), sum(v[1] for v in aggs[name].values())]
           for name, _ in cases}
    gw = {k: cagr(v[0], v[1], n) for k, v in tot.items()}
    print(f"{'WORLD':<17}{gw['SHIPPED']*100:>8.2f}%{gw['COVERAGE']*100:>9.2f}%"
          f"{(gw['COVERAGE']-gw['SHIPPED'])*100:>8.2f}pp{gw['REFRESHED']*100:>10.2f}%"
          f"{(gw['REFRESHED']-gw['SHIPPED'])*100:>8.2f}pp")

    print(f"\nLargest country movers, shipped to coverage, CAGR {y0}-{yl}, "
          f"countries above 5m outbound O&D")
    movers = []
    for c, m in need.items():
        if m < 5.0:
            continue
        a0, a1 = ctys["SHIPPED"].get(c), ctys["COVERAGE"].get(c)
        if not a0 or not a1 or not a0[0]:
            continue
        g0, g1 = cagr(a0[0], a0[1], n), cagr(a1[0], a1[1], n)
        if g0 is None or g1 is None:
            continue
        movers.append((abs(g1 - g0), c, m, g0, g1))
    movers.sort(reverse=True)
    print(f"{'country':<9}{'O&D':>9}{'shipped':>10}{'coverage':>10}{'change':>9}")
    for _, c, m, g0, g1 in movers[:20]:
        print(f"{c:<9}{m:>8.1f}m{g0*100:>9.2f}%{g1*100:>9.2f}%{(g1-g0)*100:>8.2f}pp")

    if a.json:
        json.dump({"scenario": a.scenario, "window": [y0, yl],
                   "world": {name: {str(y): results[name].world[y] for y in (y0, 2045, 2050, yl)}
                             for name, _ in cases},
                   "regions": rows,
                   "world_rpk_cagr": {k: v for k, v in gw.items()},
                   "coverage": {name: {"countries": len(wb),
                                       "base_countries": len([c for c in need if c in wb]),
                                       "od_m": sum(need[c] for c in need if c in wb)}
                                for name, wb in cases},
                   "uncovered": [{"country": c, "od_m": m} for m, c in still],
                   "maturity_flips": [{"country": c, "od_m": m, "from": x, "to": y}
                                      for m, c, x, y in flips],
                   "movers": [{"country": c, "od_m": m, "shipped": g0, "coverage": g1}
                              for _, c, m, g0, g1 in movers]},
                  open(a.json, "w"), indent=1)
        print(f"\nwritten: {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

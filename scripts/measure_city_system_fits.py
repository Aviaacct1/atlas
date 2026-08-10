r"""Do the airport elasticities read a city's second airport as a collapse in demand?
Author: Avia Solutions.

The hypothesis, carried since 9 August 2026. PEK carries a fitted income elasticity of
1.089 estimated over 1994-2024 and CTU 1.5 over 1999-2024, and both windows run through
the opening of a second airport that took traffic off them. A fit that reads a
reallocation between airports as a fall in demand would hold China's forecast down, and
China is our largest gap against Boeing.

Testing it means estimating the same thing on the city SYSTEM, Beijing as PEK plus PKX
plus NAY and Chengdu as CTU plus TFU, and comparing.

WHY THIS RUNS ON O&D AND NOT ON THE ACI PANEL. The shipped fits are estimated on ACI
terminal traffic. ACI does not publish Beijing Daxing at all, checked by code and by
airport name against the ACI monthly store, so a Beijing system panel cannot be built from
ACI at any window. Sabre `od_p2p` holds all three Beijing airports and both Chengdu
airports from 2013. Estimating on O&D is also what the assumptions book has carried as a
[P1] since July: a terminal panel measures hub development as well as demand.

The two are therefore NOT like for like, and the comparison that matters is inside this
run: the same estimator, the same window and the same source, on the single airport and on
the system. The shipped figure is shown for context and nothing else.

2020, 2021 and 2022 are excluded. 2020 is absent from the store; the 2021 slice reports
more passengers than 2022 and nearly as many as 2019, which is not a pandemic year.

Nothing is written to a shipped file. This measures.

Usage:  py -3.12 scripts\measure_city_system_fits.py
        py -3.12 scripts\measure_city_system_fits.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from avia_forecast import paths  # noqa: E402
from avia_forecast.estimate import od_reest  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCLUDE = (2020, 2021, 2022)

SYSTEMS = {
    "Beijing": {"country": "CN", "airports": ["PEK", "PKX", "NAY"], "incumbent": "PEK"},
    "Chengdu": {"country": "CN", "airports": ["CTU", "TFU"], "incumbent": "CTU"},
    # Two controls. Shanghai has two airports and no recent transfer, so its system fit
    # and its incumbent fit should agree; if they do not, the method is producing a
    # difference that has nothing to do with a new airport.
    "Shanghai": {"country": "CN", "airports": ["PVG", "SHA"], "incumbent": "PVG"},
    "Guangzhou": {"country": "CN", "airports": ["CAN"], "incumbent": "CAN"},
}


def od_by_year(con, codes):
    """Outbound O&D by year for a set of airports, treated as one origin. Flows BETWEEN
    the airports of a system are excluded: an itinerary from Daxing to Capital is not
    outbound traffic for the Beijing system, and counting it would inflate the system
    against its own incumbent."""
    inlist = ",".join("'" + c + "'" for c in codes)
    rows = con.execute(
        f"SELECT year, sum(pax) FROM od_p2p WHERE o IN ({inlist}) AND d NOT IN ({inlist}) "
        f"GROUP BY 1 ORDER BY 1").fetchall()
    return {int(y): float(p) for y, p in rows if int(y) not in EXCLUDE}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)

    import duckdb

    oef = json.load(open(os.path.join(paths.DATA, "oef_gdp_pop_by_iso2.json")))
    shipped = json.load(open(os.path.join(REPO, "data", "airport_regress.json")))
    con = duckdb.connect(paths.PREAGG, read_only=True)
    con.execute("SET enable_progress_bar=false")

    print("City system elasticities against single airport elasticities, same estimator")
    print(f"  passengers  {paths.PREAGG}, od_p2p, outbound, flows inside a system excluded")
    print(f"  income      {os.path.join(paths.DATA, 'oef_gdp_pop_by_iso2.json')}")
    print(f"  excluded    {', '.join(str(y) for y in EXCLUDE)}\n")

    out = {}
    for name, s in SYSTEMS.items():
        gdp = oef["gdp"].get(s["country"]) or {}
        sys_od = od_by_year(con, s["airports"])
        inc_od = od_by_year(con, [s["incumbent"]])
        sys_fit = od_reest.estimate_od_bG(sys_od, gdp)
        inc_fit = od_reest.estimate_od_bG(inc_od, gdp)
        ship = shipped.get(s["incumbent"]) or {}
        out[name] = {"airports": s["airports"], "incumbent": s["incumbent"],
                     "system_od": sys_od, "incumbent_od": inc_od,
                     "system_fit": sys_fit, "incumbent_fit": inc_fit,
                     "shipped_terminal_fit": {k: ship.get(k) for k in
                                              ("bG_est", "reliable", "window", "r2")}}

        yrs = sorted(sys_od)
        print(f"{name}: {' plus '.join(s['airports'])}")
        print(f"  outbound O&D, m, {yrs[0]} to {yrs[-1]}")
        print("    system    " + " ".join(f"{sys_od[y] / 1e6:7.1f}" for y in yrs))
        print("    " + f"{s['incumbent']:<9}" + " ".join(f"{inc_od[y] / 1e6:7.1f}" for y in yrs))
        for label, fit in (("system", sys_fit), (s["incumbent"], inc_fit)):
            if not fit:
                print(f"  {label:<9} too few observations")
                continue
            print(f"  {label:<9} bG {fit['bG_raw']:>6.3f} raw, {fit['bG_clamped']:>5.3f} "
                  f"applied, R2 {fit['r2']:.3f}, t {fit['t']:.2f}, n {fit['n']}, "
                  f"reliable {fit['reliable']}"
                  + (", CLAMP BINDS" if fit["clamp_binds"] else ""))
        if ship.get("bG_est") is not None:
            print(f"  shipped   bG {ship['bG_est']:.3f} on ACI terminal over "
                  f"{ship.get('window')}, reliable {ship.get('reliable')}. Different "
                  f"source, different window, shown for context only.")
        print()

    con.close()

    b, c = out.get("Beijing"), out.get("Chengdu")
    sh, gz = out.get("Shanghai"), out.get("Guangzhou")
    print("READ IT AGAINST THE CONTROLS.")
    if sh and sh["system_fit"] and sh["incumbent_fit"]:
        d = sh["system_fit"]["bG_raw"] - sh["incumbent_fit"]["bG_raw"]
        print(f"  Shanghai has two airports and no recent transfer: system less incumbent "
              f"{d:+.3f}. That is the size of difference the method produces with no new "
              f"airport in the window.")
    for name in ("Beijing", "Chengdu"):
        r = out.get(name)
        if r and r["system_fit"] and r["incumbent_fit"]:
            d = r["system_fit"]["bG_raw"] - r["incumbent_fit"]["bG_raw"]
            print(f"  {name} system less incumbent {d:+.3f}.")
    print("\n  A city whose second airport is outside the fit should show the SYSTEM fit "
          "above the incumbent's. Where it does not, the transfer is not what is holding "
          "the elasticity down and the hypothesis is wrong for that city.")

    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
        print(f"\nwritten: {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

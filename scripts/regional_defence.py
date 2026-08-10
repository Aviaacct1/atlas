r"""What is behind each regional difference against Boeing, from our own inputs.
Author: Avia Solutions.

The reconciliation says where we differ. It does not say why, and a difference that
cannot be accounted for in a room is a difference that will be read as an error.

Atlas is built bottom up from airports, so every regional growth rate decomposes into
things that were put in: the income path, the population path, where the region sits on
its propensity curve, the elasticity actually applied to its traffic and the stage length
carried into the RPK conversion. This assembles them side by side with Boeing's published
rate, so each regional difference has a stated cause rather than a shrug.

Read the implied elasticity column first. It is our O&D growth divided by the region's own
real GDP growth, and Boeing's RPK growth divided by the same GDP growth. Where the two
implied elasticities are close, the difference is arithmetic, a base or a conversion. Where
they are far apart, we and Boeing hold different views of how strongly demand answers
income, and that is a position to argue.

Nothing is written to a forecast file.

Usage:  py -3.12 scripts\regional_defence.py [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml  # noqa: E402

from avia_forecast import global_demand as gd  # noqa: E402
from avia_forecast import paths  # noqa: E402
from avia_forecast import stage_length as sl_mod  # noqa: E402
from avia_forecast.config import get  # noqa: E402
from avia_forecast.estimate import propensity as pr  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W0, W1 = 2025, 2044


def scheme():
    s = yaml.safe_load(open(os.path.join(REPO, "config", "region_schemes.yaml"),
                            encoding="utf-8"))["schemes"]["boeing_cmo"]
    return ({c: r for r, cs in s["regions"].items() for c in cs}, s.get("default"))


def boeing_published():
    """Read Boeing's regional rates from the comparator note rather than retyping them,
    which is how compare_regions_boeing.py gets them."""
    cfg = yaml.safe_load(open(os.path.join(REPO, "config", "comparators.yaml"),
                              encoding="utf-8"))
    note = (cfg["comparators"]["boeing_cmo"].get("prior_edition") or {}).get("note", "")
    out = {}
    for part in note.split("workbook:")[-1].split(","):
        part = part.strip().rstrip(".")
        if "%" not in part:
            continue
        name, val = part.rsplit(" ", 1)
        try:
            out[name.strip()] = float(val.strip().rstrip("%")) / 100.0
        except ValueError:
            pass
    return out


def cagr(a, b, n):
    return None if not a or not b or n <= 0 else (b / a) ** (1.0 / n) - 1.0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)

    lookup, default = scheme()
    pub = boeing_published()
    base = json.load(open(os.path.join(REPO, "data", "global_base_od_2025.json")))
    meta = json.load(open(os.path.join(REPO, "data", "global_airport_meta_2025.json")))
    wb = json.load(open(os.path.join(REPO, "data", "worldbank_pop_gdppc.json")))["data"]
    oef = json.load(open(os.path.join(paths.DATA, "oef_gdp_pop_by_iso2.json")))

    res = gd.run_global()
    yrs = res.years

    country_od = {}
    for iata, regs in base.items():
        c = meta[iata]["country"]
        country_od[c] = country_od.get(c, 0.0) + sum(regs.values())

    rows = {}
    for iata, regs in base.items():
        m = meta[iata]
        c = m["country"]
        reg = lookup.get(c, default)
        b = sum(regs.values())
        if b <= 0:
            continue
        r = rows.setdefault(reg, {"base": 0.0, "end": 0.0, "countries": set(),
                                  "bG_w": 0.0, "own_fit": 0.0, "pop0": 0.0, "pop1": 0.0,
                                  "gdp0": 0.0, "gdp1": 0.0, "engine_regions": {}})
        r["base"] += b
        r["end"] += res.by_airport_last.get(iata, 0.0)
        r["countries"].add(c)
        r["engine_regions"][m["region"]] = r["engine_regions"].get(m["region"], 0.0) + b
        # the elasticity actually applied to this airport's traffic, on the same rules the
        # engine uses, so the average below is what the forecast ran on and not a default
        pop = (wb.get(c) or {}).get("pop")
        tpc = (country_od.get(c, 0.0) * 1e6 / pop) if pop else None
        w = gd._maturity_weight(c, m["region"], wb, tpc)
        own = gd._airport_applied_bG(iata)
        bG = own if own is not None else gd._bG("Domestic", w)
        r["bG_w"] += b * gd._clamp_bG(bG)
        if own is not None:
            r["own_fit"] += b

    for reg, r in rows.items():
        for c in r["countries"]:
            for y, key in ((W0, "0"), (W1, "1")):
                g = (oef["gdp"].get(c) or {}).get(str(y))
                p = (oef["pop"].get(c) or {}).get(str(y))
                if g:
                    r["gdp" + key] += g
                if p:
                    r["pop" + key] += p

    n = W1 - W0
    out = []
    for reg, r in rows.items():
        od_cagr = cagr(r["base"], r["end"], yrs[-1] - yrs[0])
        gdp_cagr = cagr(r["gdp0"], r["gdp1"], n)
        pop_cagr = cagr(r["pop0"], r["pop1"], n)
        gdp_pc = cagr(r["gdp0"] / r["pop0"], r["gdp1"] / r["pop1"], n) if r["pop0"] and r["pop1"] else None
        # trips per capita on the model's own definition, and where that sits against the
        # ceiling the propensity module applies
        eng = max(r["engine_regions"], key=r["engine_regions"].get)
        asym = pr.asymptote_for(eng)
        tpc0 = r["base"] * 1e6 / (r["pop0"] * 1000) if r["pop0"] else None
        stage = sl_mod.growth(reg)
        ours_rpk = ((1 + od_cagr) * (1 + stage) - 1) if od_cagr is not None else None
        theirs = pub.get(reg)
        out.append({
            "region": reg, "base_od_m": r["base"], "airports": None,
            "od_cagr": od_cagr, "rpk_cagr": ours_rpk, "boeing_rpk_cagr": theirs,
            "gdp_cagr": gdp_cagr, "gdp_pc_cagr": gdp_pc, "pop_cagr": pop_cagr,
            "applied_bG": r["bG_w"] / r["base"], "own_fit_share": r["own_fit"] / r["base"],
            "trips_pc": tpc0, "asymptote": asym,
            "saturation": (tpc0 / asym) if (tpc0 and asym) else None,
            "stage_growth": stage,
            "implied_elasticity_avia": (od_cagr / gdp_cagr) if (od_cagr and gdp_cagr) else None,
            "implied_elasticity_boeing": (theirs / gdp_cagr) if (theirs and gdp_cagr) else None,
        })

    out.sort(key=lambda r: (r["rpk_cagr"] or 0) - (r["boeing_rpk_cagr"] or 0))

    print(f"What is behind each regional difference, Baseline case, {W0}-{W1}")
    print("Sources: Avia global forecast; Oxford Economics country GDP and population, "
          "31 July 2024;\nWorld Bank population for trips per capita; Boeing 2025 CMO "
          "regional RPK from the workbook.\n")
    print(f"{'region':<16}{'base O&D':>10}{'our O&D':>9}{'stage':>7}{'our RPK':>9}"
          f"{'Boeing':>8}{'diff':>8}{'GDP':>7}{'GDPpc':>7}{'pop':>7}{'bG':>6}"
          f"{'own fit':>9}{'trips/cap':>11}{'sat':>6}")
    for r in out:
        pc = lambda v, d=1: (f"{v * 100:.{d}f}%" if v is not None else "n/a")
        print(f"{r['region']:<16}{r['base_od_m']:>9.0f}m{pc(r['od_cagr']):>9}"
              f"{pc(r['stage_growth'], 2):>7}{pc(r['rpk_cagr']):>9}"
              f"{pc(r['boeing_rpk_cagr']):>8}"
              f"{((r['rpk_cagr'] - r['boeing_rpk_cagr']) * 100 if r['boeing_rpk_cagr'] else 0):>7.1f}pp"
              f"{pc(r['gdp_cagr']):>7}{pc(r['gdp_pc_cagr']):>7}{pc(r['pop_cagr']):>7}"
              f"{r['applied_bG']:>6.2f}{r['own_fit_share'] * 100:>8.0f}%"
              f"{(r['trips_pc'] if r['trips_pc'] else 0):>11.2f}"
              f"{(r['saturation'] if r['saturation'] else 0):>6.2f}")

    print("\nIMPLIED INCOME ELASTICITY, growth divided by the region's own real GDP growth.")
    print(f"{'region':<16}{'Avia':>8}{'Boeing':>8}{'gap':>8}   reading")
    for r in sorted(out, key=lambda r: -((r['implied_elasticity_boeing'] or 0)
                                         - (r['implied_elasticity_avia'] or 0))):
        ea, eb = r["implied_elasticity_avia"], r["implied_elasticity_boeing"]
        if ea is None or eb is None:
            continue
        d = eb - ea
        if abs(d) < 0.15:
            reading = "same view of demand; any difference is a base or a conversion"
        elif d > 0:
            reading = "Boeing assume a stronger income response than we apply"
        else:
            reading = "we assume a stronger income response than Boeing"
        print(f"{r['region']:<16}{ea:>8.2f}{eb:>8.2f}{d:>8.2f}   {reading}")

    print("\nAGAINST THE OTHER HOUSES, because Boeing is not the only comparator and is "
          "not\nthe closest one on drivers.")
    cfg = yaml.safe_load(open(os.path.join(REPO, "config", "comparators.yaml"),
                             encoding="utf-8"))["comparators"]
    world_rpk = None
    rj = os.path.join(paths.DATA, "regions_boeing.json")
    if os.path.isfile(rj):
        world_rpk = json.load(open(rj)).get("world_avia")
    for key in ("boeing_cmo", "airbus_gmf", "iata_ltf", "aci_watf"):
        c = cfg.get(key) or {}
        pe = c.get("prior_edition") or {}
        for label, rec in ((c.get("label", key) + " " + str(c.get("window")), c),
                           (c.get("label", key) + " prior " + str(pe.get("window")), pe)):
            if not rec.get("cagr"):
                continue
            basis = c.get("basis")
            ours = world_rpk if basis == "rpk" else None
            d = (f"{(ours - rec['cagr']) * 100:+.1f}pp" if ours else "not like for like")
            print(f"  {label:<32}{basis:>5}{rec['cagr'] * 100:>7.1f}%   Avia "
                  f"{(f'{ours * 100:.1f}%' if ours else 'n/a'):>6}   {d}")
    print("  IATA is produced with Oxford Economics, which is also our GDP source, so it "
          "is the\n  closest comparator on drivers. ACI counts terminal passengers, a "
          "connecting passenger\n  at each airport, so it sits above an O&D count and "
          "below an RPK growth rate.")

    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
        print(f"\nwritten: {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

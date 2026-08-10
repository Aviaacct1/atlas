r"""Candidate stage length paths for the RPK conversion, and what each does to the gap
against Boeing. Author: Avia Solutions.

Atlas forecasts passengers and converts to RPK on a stage length held constant, so our
RPK CAGR equals our passenger CAGR to the decimal place while Boeing's carries their
stage length growth inside it. `scripts/gap_decomposition.py` sizes that by applying the
measured historic rate flat, and a flat rate over-corrects: Oceania grew 1.26% a year
over 2015-2025 and holding that for twenty years puts an average Oceania sector at
3,390 km by 2044, which is a claim about network shape, not a conversion.

This produces a stated path instead, and shows the implied average sector length at the
end of it, because that is the number a client will query.

Nothing in the forecast is changed. This measures, so the decision on the path is taken
against evidence and the path itself can be signed off rather than the result.

The paths:

  flat        the measured 2015-2025 rate, held. What gap_decomposition.py applies.
  decay       the measured 2025 rate decaying to zero. The half-life is not chosen: it
              is read from the world series, which decelerated from 0.75% a year over
              2015-2019 to 0.52% over 2019-2025, five years apart on the window
              midpoints, which is a half-life of 9.5 years.
  converge    every region converging on one common long-run rate with the same
              half-life, on the reading that the spread between regions is where each
              sits in its own long-haul build-out rather than a permanent difference.
              Regions below the common rate rise towards it.

Usage:
    py -3.12 scripts\stage_length_path.py
    py -3.12 scripts\stage_length_path.py --path decay --terminal 0.0
    py -3.12 scripts\stage_length_path.py --path converge --terminal 0.003 --json out.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from avia_forecast import paths  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

W_EARLY, W_LATE, W_FULL = "2015-2019", "2019-2025", "2015-2025"


def midpoint(window):
    a, b = (int(x) for x in window.split("-"))
    return (a + b) / 2.0


def fitted_half_life(sl):
    """Read the decay from the world series rather than choosing it. Two measured
    windows, their rates at their own midpoints, one exponential through both."""
    c = sl["World"]["cagr"]
    g0, g1 = c[W_EARLY], c[W_LATE]
    dt = midpoint(W_LATE) - midpoint(W_EARLY)
    if g0 <= 0 or g1 <= 0 or g1 >= g0:
        return None, None, (g0, g1, dt)
    lam = -math.log(g1 / g0) / dt
    return math.log(2.0) / lam, lam, (g0, g1, dt)


def rate_at(g_full, lam, year, ref=2020.0):
    """The instantaneous rate implied at `year` by a window average centred on `ref`.
    A window CAGR is an average over its span, so it is dated at its midpoint and not at
    its end. 2015-2025 has a midpoint of 2020."""
    return g_full * math.exp(-lam * (year - ref))


def path_rates(kind, g_full, lam, terminal, y0, y1):
    """Annual stage length growth for each year of the window."""
    if kind == "flat":
        return {y: g_full for y in range(y0, y1 + 1)}
    g_start = rate_at(g_full, lam, y0)
    return {y: (g_start - terminal) * math.exp(-lam * (y - y0)) + terminal
            for y in range(y0, y1 + 1)}


def mean_rate(rates, y0, y1):
    """The compound average over the window, which is what the RPK CAGR carries."""
    prod = 1.0
    for y in range(y0 + 1, y1 + 1):
        prod *= (1.0 + rates[y])
    return prod ** (1.0 / (y1 - y0)) - 1.0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", default="all",
                    choices=["all", "flat", "decay", "converge", "trend"])
    ap.add_argument("--journey-json",
                    default=os.path.join(paths.DATA, "journey_length_history.json"),
                    help="output of scripts/journey_length_history.py, which carries the "
                         "estimated and shrunk regional trend the trend path applies")
    ap.add_argument("--terminal", type=float, default=None,
                    help="long-run annual stage length growth. Default 0 for decay, the "
                         "world 2015-2025 rate halved for converge")
    ap.add_argument("--half-life", type=float, default=None,
                    help="override the half-life read from the world series, in years")
    ap.add_argument("--wedge-json", default=os.path.join(paths.DATA, "fleet_wedge.json"))
    ap.add_argument("--regions-json", default=os.path.join(paths.DATA, "regions_boeing.json"))
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)

    wedge = json.load(open(a.wedge_json, encoding="utf-8"))
    reg = json.load(open(a.regions_json, encoding="utf-8"))
    sl = wedge["stage_length_by_boeing_region"]

    hl, lam, (g0, g1, dt) = fitted_half_life(sl)
    if a.half_life:
        hl = a.half_life
        lam = math.log(2.0) / hl
    y0, y1 = reg["boeing_window"]

    print("Stage length paths for the RPK conversion, measured against the OAG schedule")
    print(f"Basis: {wedge['source']}")
    print(f"Window {y0}-{y1}, Boeing edition {reg.get('boeing_edition')}\n")
    print(f"World stage length growth measured at {g0 * 100:.2f}% a year over {W_EARLY} "
          f"and {g1 * 100:.2f}% over {W_LATE}, {dt:.0f} years apart on the window "
          f"midpoints.")
    print(f"That deceleration is a half-life of {hl:.1f} years, which is what the decay "
          f"and converge paths use. It is measured, not chosen.\n")

    journey = None
    if os.path.isfile(a.journey_json):
        journey = json.load(open(a.journey_json, encoding="utf-8")).get("region_trends")
    if a.path in ("trend",) and not journey:
        raise SystemExit(f"{a.journey_json} carries no region_trends. Run "
                         f"scripts/journey_length_history.py first.")

    kinds = ["flat", "decay", "converge"] if a.path == "all" else [a.path]
    if a.path == "all" and journey:
        kinds.append("trend")
    world_full = sl["World"]["cagr"][W_FULL]
    out = {"window": [y0, y1], "half_life_years": hl, "basis": wedge["source"],
           "boeing_edition": reg.get("boeing_edition"), "paths": {}}

    for kind in kinds:
        term_default = 0.0 if kind == "decay" else world_full / 2.0
        terminal = a.terminal if a.terminal is not None else term_default
        label = {"flat": "the measured 2015-2025 rate held constant",
                 "decay": f"decaying to {terminal * 100:.2f}% a year, half-life {hl:.1f} years",
                 "converge": (f"converging on a common {terminal * 100:.2f}% a year, "
                              f"half-life {hl:.1f} years"),
                 "trend": ("the regional trend estimated on Sabre O&D journey length "
                           "2013-2025, shrunk towards the common rate at a weight of "
                           f"{(journey or {}).get('shrink_weight', 0):.2f}, held")}[kind]
        print(f"PATH: {kind}, {label}")
        print(f"{'region':<16}{'measured':>10}{'applied':>9}{'km/seat 2025':>14}"
              f"{'km/seat ' + str(y1):>14}{'Avia':>7}{'Avia +':>8}{'Boeing':>8}"
              f"{'gap now':>9}{'gap after':>11}")
        rows = []
        for r in reg["rows"] + [{"region": "World", "avia": reg.get("world_avia"),
                                 "boeing": reg.get("world_boeing"),
                                 "diff_pp": ((reg.get("world_avia") or 0)
                                             - (reg.get("world_boeing") or 0)) * 100}]:
            name = r["region"]
            rec = sl.get(name)
            if not rec or r.get("avia") is None or r.get("boeing") is None:
                continue
            g_full = rec["cagr"][W_FULL]
            if kind == "trend":
                if name == "World":
                    g_applied = journey["common"]
                else:
                    t = journey["regions"].get(name)
                    if not t:
                        continue
                    g_applied = t["shrunk"]
                rates = None
            elif kind == "converge":
                g_start = rate_at(g_full, lam, y0)
                rates = {y: (g_start - terminal) * math.exp(-lam * (y - y0)) + terminal
                         for y in range(y0, y1 + 1)}
            else:
                rates = path_rates(kind, g_full, lam, terminal, y0, y1)
            if rates is not None:
                g_applied = mean_rate(rates, y0, y1)
            km25 = rec["km_per_seat"]["2025"]
            km_end = km25 * (1.0 + g_applied) ** (y1 - 2025)
            adj = (1 + r["avia"]) * (1 + g_applied) - 1
            after = (adj - r["boeing"]) * 100
            rows.append({"region": name, "measured_cagr": g_full, "applied_cagr": g_applied,
                         "km_per_seat_2025": km25, f"km_per_seat_{y1}": km_end,
                         "avia": r["avia"], "avia_with_stage": adj, "boeing": r["boeing"],
                         "gap_pp_now": r["diff_pp"], "gap_pp_after": after})
            print(f"{name:<16}{g_full * 100:>9.2f}%{g_applied * 100:>8.2f}%"
                  f"{km25:>14,.0f}{km_end:>14,.0f}{r['avia'] * 100:>6.1f}%"
                  f"{adj * 100:>7.1f}%{r['boeing'] * 100:>7.1f}%"
                  f"{r['diff_pp']:>8.1f}pp{after:>10.1f}pp")
        out["paths"][kind] = {"terminal": terminal, "rows": rows}
        print()

    print("The applied column is the compound average over the window, which is what an "
          "RPK CAGR carries. The km per seat column is the claim the path makes about "
          "network shape, and it is the one a client will query.")

    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
        print(f"\nwritten: {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

r"""Split the Avia against Boeing growth gap into the part that is a convention and the
part that is a difference of view. Author: Avia Solutions.

The reconciliation in scripts/compare_regions_boeing.py says the world is 0.9 points
behind Boeing and five emerging regions are 1.4 to 1.9 points behind. It does not say
why, and one of the reasons is arithmetic rather than judgement.

Boeing publishes RPK. Atlas forecasts passengers and converts to RPK by multiplying by
a stage length that is a fixed per-region constant, so our RPK CAGR equals our passenger
CAGR to the decimal place. Boeing's RPK CAGR carries their stage length growth inside
it. Comparing the two therefore compares a number with stage length growth against a
number without it, and the difference is not a difference of view about demand.

compare_regions_boeing.py says in its own header that "a constant stage length cancels
in a CAGR". It cancels between our RPK and our passengers. It does not cancel against a
counterparty whose RPK contains a growing stage length, which is the only comparison the
script is for.

This script sizes that. It takes the measured stage length growth from the OAG schedule
produced by scripts/build_fleet_wedge.py and asks what our RPK CAGR would be if stage
length continued at its measured historic rate rather than being held flat. Nothing in
the forecast is changed. The output is a measurement, so the decision to change the
conversion is taken against evidence.

Usage:  py -3.12 scripts\gap_decomposition.py [--window 2015-2025]
        Run scripts\compare_regions_boeing.py --json and scripts\build_fleet_wedge.py
        first; both write the inputs this reads.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from avia_forecast import paths  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_regions(path):
    if not os.path.exists(path):
        print(f"regenerating {path}")
        subprocess.run([sys.executable,
                        os.path.join(REPO, "scripts", "compare_regions_boeing.py"),
                        "--json", path], check=True)
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--window", default="2015-2025",
                    help="the measured stage length window to apply")
    ap.add_argument("--regions-json",
                    default=os.path.join(paths.DATA, "regions_boeing.json"))
    ap.add_argument("--wedge-json",
                    default=os.path.join(paths.DATA, "fleet_wedge.json"))
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    reg = load_regions(args.regions_json)
    with open(args.wedge_json, "r", encoding="utf-8") as fh:
        wedge = json.load(fh)
    sl = wedge["stage_length_by_boeing_region"]
    if args.window not in sl.get("World", {}).get("cagr", {}):
        raise SystemExit(f"the wedge JSON holds no {args.window} window. Rebuild with "
                         f"scripts/build_fleet_wedge.py --windows "
                         f"{args.window.replace('-', ':')}")

    print(f"Avia against Boeing, RPK CAGR {reg['avia_window'][0]}-{reg['avia_window'][1]}, "
          f"Baseline case")
    print(f"Measured stage length growth from the OAG schedule, {args.window}, applied "
          "as a test only. Nothing in the forecast is changed.\n")
    print(f"{'region':<16}{'Avia':>7}{'stage':>8}{'Avia +':>9}{'Boeing':>8}"
          f"{'gap now':>9}{'gap after':>11}")
    rows, world = [], None
    for r in reg["rows"]:
        name = r["region"]
        g = sl.get(name, {}).get("cagr", {}).get(args.window)
        if g is None:
            print(f"{name:<16}{r['avia'] * 100:6.1f}%{'n/a':>8}"
                  f"{'n/a':>9}{r['boeing'] * 100:7.1f}%{r['diff_pp']:8.1f}pp{'n/a':>11}")
            continue
        adj = (1 + r["avia"]) * (1 + g) - 1
        after = (adj - r["boeing"]) * 100
        rows.append({"region": name, "avia": r["avia"], "stage_cagr": g,
                     "avia_with_stage": adj, "boeing": r["boeing"],
                     "gap_pp_now": r["diff_pp"], "gap_pp_after": after})
        print(f"{name:<16}{r['avia'] * 100:6.1f}%{g * 100:7.1f}%{adj * 100:8.1f}%"
              f"{r['boeing'] * 100:7.1f}%{r['diff_pp']:8.1f}pp{after:10.1f}pp")
    w = None
    if reg.get("world_avia") is not None:
        w = {"avia": reg["world_avia"], "boeing": reg["world_boeing"],
             "diff_pp": (reg["world_avia"] - reg["world_boeing"]) * 100}
    if w:
        g = sl["World"]["cagr"][args.window]
        adj = (1 + w["avia"]) * (1 + g) - 1
        after = (adj - w["boeing"]) * 100
        world = {"region": "World", "avia": w["avia"], "stage_cagr": g,
                 "avia_with_stage": adj, "boeing": w["boeing"],
                 "gap_pp_now": w["diff_pp"], "gap_pp_after": after}
        print(f"{'WORLD':<16}{w['avia'] * 100:6.1f}%{g * 100:7.1f}%{adj * 100:8.1f}%"
              f"{w['boeing'] * 100:7.1f}%{w['diff_pp']:8.1f}pp{after:10.1f}pp")

    print("\nRead this as two different findings sitting in one column. Where the gap "
          "closes, we were comparing a passenger CAGR with an RPK CAGR and the "
          "difference was a conversion. Where it does not close, we hold a different "
          "view of demand, and that view has to be argued rather than corrected.")

    out = {"window": args.window, "basis": wedge["source"],
           "boeing": reg.get("boeing_edition"), "rows": rows, "world": world,
           "note": ("A test of the measured historic stage length growth against the "
                    "current constant. No forecast number is changed by this script.")}
    dest = args.json or os.path.join(paths.DATA, "gap_decomposition.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"\nwritten to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

r"""The bridge between a passenger CAGR and an RPK CAGR, and what is left after it.
Author: Avia Solutions.

Boeing publishes RPK. Atlas forecasts passengers. Until 9 August 2026 the conversion
multiplied by a per-region constant, so our RPK CAGR equalled our passenger CAGR to the
decimal place while Boeing's carried their stage length growth inside it. Comparing the
two compared a number with stage length growth against a number without it, and that is
not a difference of view about demand.

`scripts/compare_regions_boeing.py` said in its own header that a constant stage length
cancels in a CAGR. It cancels between our RPK and our own passengers. It does not cancel
against a counterparty whose RPK contains a growing stage length, which is the only
comparison the script exists for.

That is now fixed. The conversion carries a per-region stage length growth rate estimated
from Sabre O&D journey length over 2013-2025, in config/stage_length.yaml. This script no
longer applies a test: it reads both columns `compare_regions_boeing.py` already writes,
the constant-stage basis and the published one, and reports the bridge between them, so
the slide and the reconciliation are built from the same run rather than from a second
one that could drift.

What is left after the bridge is the part that has to be argued: China, the Middle East
and Southeast Asia, where affordability is the mechanism Boeing use and we do not model.

Usage:  py -3.12 scripts\gap_decomposition.py
        Run scripts\compare_regions_boeing.py --json first; this reads its output.
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
    ap.add_argument("--regions-json",
                    default=os.path.join(paths.DATA, "regions_boeing.json"))
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    reg = load_regions(args.regions_json)
    if reg.get("world_avia_constant_stage") is None:
        raise SystemExit(f"{args.regions_json} predates the stage length change and "
                         f"carries no constant-stage column. Re-run "
                         f"scripts/compare_regions_boeing.py --json {args.regions_json}.")

    print(f"Avia against Boeing, RPK CAGR {reg['avia_window'][0]}-{reg['avia_window'][1]}, "
          f"Baseline case")
    print(f"Basis: {reg.get('stage_length_basis')}\n")
    print(f"{'region':<16}{'constant':>10}{'stage':>8}{'published':>11}{'Boeing':>8}"
          f"{'gap on constant':>17}{'gap now':>10}")
    rows, world = [], None
    for r in reg["rows"] + [{"region": "World", "avia": reg.get("world_avia"),
                             "avia_constant_stage": reg.get("world_avia_constant_stage"),
                             "stage_growth": reg.get("world_stage_growth"),
                             "boeing": reg.get("world_boeing")}]:
        name = r["region"]
        flat, ours, theirs = r.get("avia_constant_stage"), r.get("avia"), r.get("boeing")
        if flat is None or ours is None or theirs is None:
            continue
        row = {"region": name, "avia_constant_stage": flat, "stage_cagr": r.get("stage_growth"),
               "avia": flat, "avia_with_stage": ours, "boeing": theirs,
               "gap_pp_now": (flat - theirs) * 100, "gap_pp_after": (ours - theirs) * 100}
        if name == "World":
            world = row
        else:
            rows.append(row)
        sg = f"{r['stage_growth'] * 100:.2f}%" if r.get("stage_growth") is not None else "n/a"
        print(f"{name:<16}{flat * 100:>9.1f}%{sg:>8}{ours * 100:>10.1f}%"
              f"{theirs * 100:>7.1f}%{(flat - theirs) * 100:>15.1f}pp"
              f"{(ours - theirs) * 100:>9.1f}pp")

    closed = [r for r in rows if abs(r["gap_pp_after"]) < abs(r["gap_pp_now"]) - 0.5]
    left = sorted((r for r in rows if r["gap_pp_after"] < -1.0),
                  key=lambda r: r["gap_pp_after"])
    print(f"\nThe bridge closes the world gap from "
          f"{world['gap_pp_now']:.1f}pp to {world['gap_pp_after']:.1f}pp"
          if world else "")
    if left:
        print("What is left, and it has to be argued rather than converted: "
              + ", ".join(f"{r['region']} {r['gap_pp_after']:.1f}pp" for r in left) + ".")
        print("Affordability is the mechanism Boeing use in those regions and we do not "
              "model it. Our fare series is an index with no level, so real fare against "
              "income cannot be drawn.")
    print(f"{len(closed)} of {len(rows)} regions move by more than half a point on the "
          f"conversion alone.")

    out = {"basis": reg.get("stage_length_basis"),
           "boeing": reg.get("boeing_edition"), "rows": rows, "world": world,
           "note": ("The bridge from the constant stage length the conversion used before "
                    "9 August 2026 to the estimated per-region path it uses now. Both "
                    "columns come from one run of scripts/compare_regions_boeing.py.")}
    dest = args.json or os.path.join(paths.DATA, "gap_decomposition.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"\nwritten to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

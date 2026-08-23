"""What the connecting-split disagreement is worth in published totals.

The publication watchpoint flags airports where the Sabre leg-measured and the
ACI-residual connecting shares disagree by more than 30 points; on the tree of
23 August 2026 that is 314 airports with 10.9% of world terminal traffic, and the
band in the assumptions book was raised to 12% as a recorded interim pending this
measurement. The terminal LEVEL of a flagged airport is ACI-anchored either way;
what the disagreement moves is the split between the O&D-driven and the
connecting-driven growth paths. This script bounds that effect: it re-runs the
terminal forecast in memory three times, with every flagged airport's share set to
its Sabre value, its residual value, and the shipped blend, and reports the spread
on the world and regional 2050 totals and the largest airport-level spreads.

Measurement only: nothing on disk changes. Run where E: is local:

    py -3.12 scripts\\measure_connecting_divergence.py

Author: Avia Solutions.
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from avia_forecast import global_terminal as gt
from avia_forecast.config import assumptions


def run_with_method(method):
    book = assumptions()
    gd = book["global_drivers"]
    prev = gd.get("connecting_share_method", "blend")
    gd["connecting_share_method"] = method
    try:
        return gt.run_terminal(scenario="Baseline")
    finally:
        gd["connecting_share_method"] = prev


def main():
    cases = {}
    for method in ("blend", "sabre", "residual"):
        r = run_with_method(method)
        y0, y1 = r.years[0], r.years[-1]
        cases[method] = r
        print(f"{method:9s} world {y1}: {r.world[y1]:,.0f}m   CAGR {100*r.world_cagr:.3f}%")

    blend, sab, res = cases["blend"], cases["sabre"], cases["residual"]
    y1 = blend.years[-1]
    lo = min(sab.world[y1], res.world[y1])
    hi = max(sab.world[y1], res.world[y1])
    print(f"\nworld {y1} spread across the two sources: {hi - lo:,.0f}m "
          f"({100 * (hi - lo) / blend.world[y1]:.2f}% of the blended figure)")

    flagged = {d["iata"] for d in blend.meta.get("connecting_discrepancies", [])}
    print(f"(the served sample lists {len(flagged)} of the flagged airports; "
          f"airport-level spreads below are over ALL airports)")
    rows = []
    for iata, b in blend.by_airport.items():
        s, r_ = sab.by_airport.get(iata), res.by_airport.get(iata)
        if not (s and r_):
            continue
        d = abs(s["series"][-1] - r_["series"][-1])
        if d > 0:
            rows.append((d, iata, b["series"][-1]))
    rows.sort(reverse=True)
    print(f"\nlargest airport-level {y1} spreads (m, source-to-source):")
    for d, iata, lvl in rows[:15]:
        print(f"  {iata}  spread {d:8.2f}  blended level {lvl:8.2f}")

    print("\nReading: if the world spread is a fraction of a percent, the split "
          "uncertainty does not move published totals and the band note in the "
          "assumptions book stands; the airport-level spreads name where the caveat "
          "earns its place. If the world spread is material, the flagged set needs "
          "reconciling airport by airport before the band tightens.")


if __name__ == "__main__":
    main()

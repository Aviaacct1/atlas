"""The architecture package, measured before any book edit.

The pooled panel fit of 23 August 2026 (scripts/estimate_pooled_panel.py) resolved the
maturity architecture on the pre-stated rules: the mature/emerging split fails its
fifth test (not significant, wrong order) and collapses to a single elasticity; the
fare term is identified at -0.292 (t 2.95), so the book's prior bF set (traffic-
weighted -0.66) re-anchors to the measurement; and the propensity slope re-fit
(1.422, control-validated) applies under the better-founded-parameter rule. Two
honest level candidates exist for the single elasticity: the unweighted pooled 1.544
(the median country's response) and the traffic-weighted 1.161 (dominated by the
largest series). The choice is made on measured forecasts with John's eyes on them,
never on coefficients alone, and the comparator band position is reported, not
selected for.

Cases, all in memory, nothing written:
  A  shipped: saturation split, slope 1.30, prior bF
  B  package at 1.544: single bG (segment relativities preserved), slope 1.422, measured bF
  C  package at 1.161: as B at the traffic-weighted level
  D  single bG at 1.544 alone (isolates the split collapse from slope and fare)

Runs where E: is local:    py -3.12 scripts\\measure_architecture_package.py
Author: Avia Solutions. 23 August 2026.
"""
from __future__ import annotations
import copy
import json
import os
import sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from avia_forecast import config
from avia_forecast import global_demand as gd

STAGE_WORLD = 0.0071   # config/stage_length.yaml common rate, for the RPK proxy line

# Segment values scaled so the traffic-weighted world aggregate hits the target,
# relativities preserved (computed 23 August 2026 from the base O&D segment weights
# 0.607 / 0.203 / 0.191 and the book's emerging relativities 1.5 / 1.7 / 1.8).
SINGLE = {
    1.544: {"Domestic": 1.45, "International Short Haul": 1.643, "Long Haul": 1.739},
    1.161: {"Domestic": 1.09, "International Short Haul": 1.235, "Long Haul": 1.308},
}
BF_MEASURED = {"Domestic": -0.309, "International Short Haul": -0.309, "Long Haul": -0.221}


def run_case(tag, single=None, slope=None, bf=None):
    book = config.assumptions()
    l3 = book["level3_defaults"]
    keep = copy.deepcopy(l3)
    keep_slope = book["propensity"]["income_elasticity_tpc"]
    try:
        if single:
            for s in l3:
                l3[s]["bG_mature"] = l3[s]["bG_emerging"] = SINGLE[single][s]
        if bf:
            for s in l3:
                l3[s]["bF"] = BF_MEASURED[s]
        if slope:
            book["propensity"]["income_elasticity_tpc"] = slope
        r = gd.run_global("Baseline")
    finally:
        for s in l3:
            l3[s].update(keep[s])
        book["propensity"]["income_elasticity_tpc"] = keep_slope

    base = gd._load("global_base_od_2025.json")
    meta = gd._load("global_airport_meta_2025.json")
    y0, y1 = r.years[0], r.years[-1]
    i45 = r.years.index(2045)
    cagr = lambda a, b, n: (b / a) ** (1 / n) - 1
    w_full = cagr(r.world[y0], r.world[y1], y1 - y0)
    w_45 = cagr(r.world[y0], r.world[r.years[i45]], 2045 - y0)
    cn = [a for a in base if meta[a]["country"] == "CN"]
    cn0 = sum(sum(base[a].values()) for a in cn)
    cn1 = sum(r.by_airport_last[a] for a in cn)
    cn_c = cagr(cn0, cn1, y1 - y0)
    rpk_proxy = w_45 + STAGE_WORLD
    print(f"{tag:32s} world {y1} {r.world[y1]:8,.0f}m  CAGR25-60 {100*w_full:5.2f}%  "
          f"CAGR25-45 {100*w_45:5.2f}%  China {100*cn_c:5.2f}%  "
          f"RPK proxy 25-45 {100*rpk_proxy:5.2f}%")
    return r


def main():
    print("RPK proxy = O&D CAGR 2025-2045 + the 0.71% world stage rate; the exact "
          "comparison comes from the rebuilt bundle after a decision. Comparators on "
          "their own windows: Boeing CMO26 4.0%, Airbus GMF26 3.9%, IATA 3.6%.\n")
    A = run_case("A shipped (split, 1.30, prior bF)")
    D = run_case("D single bG @1.544 only", single=1.544)
    B = run_case("B package @1.544 (+1.422, bF)", single=1.544, slope=1.422, bf=True)
    C = run_case("C package @1.161 (+1.422, bF)", single=1.161, slope=1.422, bf=True)
    print("\nRegional O&D CAGR 2025-2045, A vs B vs C (destination-region basis):")
    y0 = A.years[0]
    i45 = A.years.index(2045)
    for reg in sorted(A.by_region):
        f = lambda r: 100 * ((r.by_region[reg][r.years[i45]] / r.by_region[reg][y0]) ** (1 / 20) - 1)
        print(f"  {reg:22s} A {f(A):5.2f}%   B {f(B):5.2f}%   C {f(C):5.2f}%")
    print("\nNothing written. John chooses on these numbers; the book edit cites the "
          "pooled fit and this run; the bundle rebuild and compare follow the edit.")


if __name__ == "__main__":
    main()

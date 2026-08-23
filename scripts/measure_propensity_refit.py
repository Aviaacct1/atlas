"""Re-fit the world propensity curve on every country the base holds.

`propensity.income_elasticity_tpc` is 1.30 and the book records it as the fitted
world-curve slope from 30 countries; since the World Bank ingest of 9 August 2026 the
country file holds circa 200, so a parameter estimated on 30 is applied to 199
(MEASUREMENTS 5, the noted consequence). This re-fits `fit_world_curve` on the full
set, with the original 30 as the control that must reproduce the shipped 1.30, and a
stated exclusion for visitor economies, where departing trips divided by resident
population is not a propensity (Aruba at 9.98 trips per resident is Aruba's tourists,
not Arubans flying).

Measurement only: nothing is written. Applying a new slope is a book edit with this
script's output recorded beside it. Author: Avia Solutions. 23 August 2026.
"""
from __future__ import annotations
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from avia_forecast.estimate.propensity import fit_world_curve

# The 30 countries of the original fit, as listed in MEASUREMENTS.md section 4.
ORIG30 = {"AE", "AU", "BR", "CH", "CN", "DE", "EG", "ES", "FR", "GB", "GR", "HK", "ID",
          "IE", "IN", "IT", "JP", "MA", "MX", "NG", "NL", "NO", "PL", "PT", "SA", "SG",
          "TH", "TR", "US", "ZA"}

# Visitor economies from MEASUREMENTS.md section 5: departing O&D against resident
# population starts at or above the regional ceiling, so the ratio is not a residents'
# propensity. Named, not thresholded, so the exclusion cannot silently grow.
VISITOR = {"AW", "MT", "IS", "MO", "CY", "MV", "PF", "BS", "SG", "BZ"}


def main():
    wb = json.load(open(os.path.join(REPO, "data", "worldbank_pop_gdppc.json")))["data"]
    base = json.load(open(os.path.join(REPO, "data", "global_base_od_2025.json")))
    meta = json.load(open(os.path.join(REPO, "data", "global_airport_meta_2025.json")))

    od = {}
    for iata, regs in base.items():
        c = meta.get(iata, {}).get("country")
        if c:
            od[c] = od.get(c, 0.0) + sum(regs.values())

    def sample(pred):
        g, t, used = [], [], []
        for c, rec in wb.items():
            pop, gpc = rec.get("pop"), rec.get("gdp_pc_ppp")
            if not (pop and gpc and od.get(c, 0.0) > 0):
                continue
            if not pred(c):
                continue
            g.append(gpc)
            t.append(od[c] * 1e6 / pop)
            used.append(c)
        return g, t, used

    for label, pred in (
        ("control: the original 30", lambda c: c in ORIG30),
        ("all countries with a record", lambda c: True),
        ("all, visitor economies excluded", lambda c: c not in VISITOR),
    ):
        g, t, used = sample(pred)
        a, b = fit_world_curve(g, t)
        print(f"{label:34s} n={len(used):3d}  slope b={b:.3f}  intercept a={a:.3f}")

    print("\nShipped propensity.income_elasticity_tpc: 1.30 (book). The control row must "
          "land near it or the sample reconstruction is wrong and nothing below it "
          "counts. The visitor-excluded slope on the full set is the candidate value; "
          "applying it is a book edit citing this run, and the effect on the forecast "
          "is then measured through run_global before anything ships.")


if __name__ == "__main__":
    main()

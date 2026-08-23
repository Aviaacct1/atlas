"""The composed backtest: the model in its operating configuration, honestly windowed.

The accuracy surface holds two families of exhibit and neither is the product as it
runs. The seats-anchor exhibit uses the OUTTURN schedule at every horizon, which is
knowable a year ahead and no further; the Method Spec 9 exhibit runs the demand model
from the base year with no schedule anchor at all, which understates the product,
whose first year IS schedule-anchored in live use. This composes the two the way the
product actually operates: year one on the published-schedule seats ratio, the demand
model on the GDP driver thereafter, scored against ACI outturn with the naive GDP
multiple as the control arm.

The store's history decides the honest windows: OAG holds 2015-2019 and 2023-2025 with
2020-2022 excluded by policy, so the one clean multi-year composed window is base 2015,
seats-anchored to 2016, model 2016-2019, scored at 2019; and the modern-era single-step
base 2023, seats-anchored to 2024, scored at 2024 (fully anchored, zero model years,
which is exactly what the product's first-year claim is). Anything longer would need a
schedule that was not knowable at forecast time, which is the flaw this exists to avoid.

Writes data/backtest_composed_exhibit.json (dump_atomic). Needs the OAG store and the
ACI panel, so it runs where E: is local:

    py -3.12 scripts\\backtest_composed.py

Author: Avia Solutions. 23 August 2026.
"""
from __future__ import annotations
import json
import os
import statistics
import sys

import duckdb

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

from avia_forecast.io_safe import dump_atomic
from avia_forecast.paths import DATA, OAG_DB
from avia_forecast.backtest.at_scale import fit_bG, _g

import backtest_seats_anchor as SA   # the guarded seat extraction: preferred tilings, home region

# (base year, anchor year, score year). The anchor uses the anchor year's published
# schedule, which a forecast made in the base year could hold; the model runs anchor
# year to score year on the GDP driver with the airport's own fitted elasticity.
WINDOWS = [(2015, 2016, 2019), (2023, 2024, 2024)]
NAIVE_MULT = 1.5   # the same control arm as the Method Spec 9 exhibit


def main():
    con = duckdb.connect(os.environ.get("AVIA_OAG_STORE") or OAG_DB, read_only=True)
    seats = SA.seats_by_basis(con)["annual"]          # {iata: {year: departing seats}}
    con.close()

    panel = json.load(open(os.path.join(DATA, "aci_panel_long.json")))
    pax, iso_of = {}, {}
    for r in panel:
        if r.get("terminal_pax") and r.get("iata"):
            pax.setdefault(r["iata"], {})[int(r["year"])] = float(r["terminal_pax"])
            iso_of[r["iata"]] = r.get("country_code")
    oef = json.load(open(os.path.join(DATA, "oef_gdp_pop_by_iso2.json")))["gdp"]

    exhibit = {"basis": ("year one on the published-schedule seats ratio (the product's "
                         "operating configuration); the demand model on the GDP driver "
                         "thereafter, own fitted elasticity, book-clamped; naive control "
                         "is the 1.5x GDP multiple throughout"),
               "windows": {}, "db": os.environ.get("AVIA_OAG_STORE") or OAG_DB}
    for base_y, anchor_y, score_y in WINDOWS:
        rows = []
        for iata, hist in pax.items():
            gdp = oef.get(iso_of.get(iata) or "", {})
            s = seats.get(iata, {})
            bp, act = hist.get(base_y), hist.get(score_y)
            s0, s1 = s.get(base_y), s.get(anchor_y)
            if not (bp and act and s0 and s1 and gdp):
                continue
            anchored = bp * (s1 / s0)                                  # year one: schedule
            bG, n = fit_bG(hist, gdp, base_y)
            g_a, g_s = _g(gdp, anchor_y), _g(gdp, score_y)
            if bG is None or not g_a or not g_s:
                continue
            model = anchored * (g_s / g_a) ** bG                       # thereafter: the model
            naive = bp
            for y in range(base_y + 1, score_y + 1):
                gy, gy1 = _g(gdp, y), _g(gdp, y - 1)
                gr = (gy / gy1 - 1.0) if (gy and gy1) else 0.0
                naive *= (1.0 + NAIVE_MULT * gr)
            rows.append({"iata": iata, "actual": act, "composed": model, "naive": naive,
                         "err": model / act - 1.0, "naive_err": naive / act - 1.0})
        if not rows:
            print(f"window {base_y}->{score_y}: no scorable airports (check store years)")
            continue
        w = sum(r["actual"] for r in rows)
        wmape = sum(abs(r["err"]) * r["actual"] for r in rows) / w
        wmape_n = sum(abs(r["naive_err"]) * r["actual"] for r in rows) / w
        summ = {"n": len(rows), "wmape_composed": round(wmape, 4),
                "wmape_naive": round(wmape_n, 4),
                "median_ape": round(statistics.median(abs(r["err"]) for r in rows), 4),
                "within_20pct": round(sum(abs(r["err"]) <= 0.20 for r in rows) / len(rows), 4),
                "within_10pct": round(sum(abs(r["err"]) <= 0.10 for r in rows) / len(rows), 4),
                "beats_naive_wmape": wmape < wmape_n}
        exhibit["windows"][f"{base_y}->{score_y} (anchor {anchor_y})"] = summ
        print(f"{base_y}->{score_y} (anchor {anchor_y}): n={summ['n']}  WMAPE composed "
              f"{100*wmape:.1f}% vs naive {100*wmape_n:.1f}%  within20 "
              f"{100*summ['within_20pct']:.1f}%  within10 {100*summ['within_10pct']:.1f}%  "
              f"beats naive {summ['beats_naive_wmape']}")

    out = os.path.join(REPO, "data", "backtest_composed_exhibit.json")
    dump_atomic(exhibit, out, indent=1)
    print("exhibit ->", out)
    print("\nReading: the 2015->2019 row is the honest multi-year claim for the product "
          "in its operating configuration; compare it with the pure-model 14.3% and the "
          "outturn-schedule 5.0% on the same window. If it beats the naive control, it "
          "belongs on the accuracy card through scripts/accuracy_block.py; if it does "
          "not, that is the finding and it is shown anyway.")


if __name__ == "__main__":
    main()

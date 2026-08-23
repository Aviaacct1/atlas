"""Country income elasticities re-estimated on O&D: the [P1] open since July.

Every elasticity architecture question in the book funnels into one missing
instrument. The shipped country fits are estimated on ACI TERMINAL traffic, so hub
development and network build masquerade as income response: a third of the reliable
set pins at the 2.2 clamp and MEASUREMENTS 1 disqualifies them from application. And
the measurements of 23 August 2026 show the fitted set discriminates on NEITHER
income (CHANGELOG 119: R2 0.057) NOR saturation (slope +0.06, t 0.4, R2 0.001), so
the mature/emerging split is a prior on both its candidate axes. Whether the split
survives, and what level a single elasticity would take if it does not, can only be
answered from fits that measure demand rather than airport development. This is that
estimation: Sabre od_p2p true origin and destination passengers summed to origin
country by year (2013-2019 and 2023 onward; 2020 absent from the store, 2021-2022
excluded by the store policy), against the Oxford Economics country GDP paths,
through the same restricted covid-dummy fit the book already uses (od_reest).

Writes data/estimated_bG_by_country_od.json as a CANDIDATE file. Nothing reads it:
`use_estimated_elasticities` stays off and the shipped terminal-based file is
untouched. It also re-runs both discriminator tests on the new fits and reports the
traffic-weighted mean of the clamped values, which is the level a single-elasticity
architecture would take. Decisions follow the numbers, in the book, with this run
cited. Runs where E: is local:

    py -3.12 scripts\\estimate_country_bG_od.py

Author: Avia Solutions. 23 August 2026.
"""
from __future__ import annotations
import csv
import json
import math
import os
import sys
from collections import defaultdict

import duckdb

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from avia_forecast.io_safe import dump_atomic
from avia_forecast.paths import DATA, PREAGG, QSI_APP
from avia_forecast.estimate.od_reest import estimate_od_bG
from avia_forecast.config import get

EXCLUDE_YEARS = (2020, 2021, 2022)


def main():
    ref = os.path.join(QSI_APP, "reference_tables", "airport_city_country.csv")
    iso = {r["airport_code"].strip(): r["country_code"].strip()
           for r in csv.DictReader(open(ref, encoding="utf-8-sig"))}

    con = duckdb.connect(PREAGG, read_only=True)
    rows = con.execute("SELECT year, o, sum(pax) FROM od_p2p GROUP BY 1, 2").fetchall()
    con.close()

    series, unmapped = defaultdict(lambda: defaultdict(float)), 0.0
    total = 0.0
    for year, o, pax in rows:
        if int(year) in EXCLUDE_YEARS:
            continue
        total += pax
        c = iso.get(o)
        if c:
            series[c][int(year)] += pax
        else:
            unmapped += pax
    print(f"origin-unmapped traffic: {100 * unmapped / total:.2f}% of {total / 1e6:,.0f}m "
          f"(the reference supplement of 9 August took this from 3.22%)")

    gdp = json.load(open(os.path.join(DATA, "oef_gdp_pop_by_iso2.json")))["gdp"]
    out, fitted = {}, 0
    for c, ys in series.items():
        g = gdp.get(c)
        if not g:
            continue
        est = estimate_od_bG({y: p for y, p in ys.items() if p > 0}, g)
        if est:
            est["basis"] = "Sabre od_p2p outbound O&D by origin country; OEF GDP; restricted covid-dummy fit"
            out[c] = est
            fitted += 1

    rel = {c: e for c, e in out.items() if e.get("reliable")}
    bounds = get("global_drivers.bG_applied_bounds", [0.6, 2.2])
    at_hi = [c for c, e in rel.items() if e["bG_raw"] >= bounds[1]]
    at_lo = [c for c, e in rel.items() if e["bG_raw"] <= bounds[0]]
    med = sorted(e["bG_raw"] for e in rel.values())[len(rel) // 2] if rel else None
    print(f"\nfitted {fitted} countries; reliable {len(rel)}; median reliable bG {med}")
    print(f"at or beyond the {bounds[1]} bound: {len(at_hi)} of {len(rel)} "
          f"({100 * len(at_hi) / max(len(rel), 1):.0f}%); at or below {bounds[0]}: {len(at_lo)}")
    print("terminal-based comparison (MEASUREMENTS 13): median 1.67, 45 of 137 (33%) at the bound")

    # The level a single-elasticity architecture would take: traffic-weighted clamped bG.
    w = {c: sum(series[c].values()) for c in rel}
    tw = sum(w[c] * rel[c]["bG_clamped"] for c in rel) / sum(w.values()) if rel else None
    print(f"traffic-weighted mean of clamped reliable bG: {tw:.3f}  "
          f"(the level question, if the split goes)")

    # Discriminator tests on the CLEAN fits: income and saturation.
    wb = json.load(open(os.path.join(REPO, "data", "worldbank_pop_gdppc.json")))["data"]
    base = json.load(open(os.path.join(REPO, "data", "global_base_od_2025.json")))
    meta = json.load(open(os.path.join(REPO, "data", "global_airport_meta_2025.json")))
    asym_tbl = get("propensity.region_asymptote_trips_pc")
    od25, regw = defaultdict(float), defaultdict(lambda: defaultdict(float))
    for iata, r in base.items():
        m = meta.get(iata, {})
        if m.get("country"):
            od25[m["country"]] += sum(r.values())
            regw[m["country"]][m.get("region")] += sum(r.values())

    def ols(pairs, label):
        n = len(pairs)
        if n < 20:
            print(f"  {label}: only {n} points, not fitted")
            return
        xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
        b = sxy / sxx
        resid = [ys[i] - (my + b * (xs[i] - mx)) for i in range(n)]
        se = math.sqrt(sum(r * r for r in resid) / (n - 2) / sxx)
        syy = sum((y - my) ** 2 for y in ys)
        print(f"  {label}: n={n}  slope {b:+.3f}  t {b / se:+.2f}  "
              f"R2 {1 - sum(r * r for r in resid) / syy:.3f}")

    inc, sat = [], []
    for c, e in rel.items():
        rec = wb.get(c)
        if not (rec and rec.get("pop") and rec.get("gdp_pc_ppp") and od25.get(c)):
            continue
        region = max(regw[c], key=regw[c].get)
        asym = asym_tbl.get(region, asym_tbl.get("default"))
        inc.append((math.log(rec["gdp_pc_ppp"]), e["bG_raw"]))
        sat.append(((od25[c] * 1e6 / rec["pop"]) / asym, e["bG_raw"]))
    print("\ndiscriminator tests on the O&D-based reliable fits:")
    ols(inc, "bG on ln(GDP per head)")
    ols(sat, "bG on saturation position")

    dump_atomic(out, os.path.join(REPO, "data", "estimated_bG_by_country_od.json"), indent=1)
    print("\ncandidate file -> data/estimated_bG_by_country_od.json (nothing reads it; "
          "applying anything is a book decision citing this run)")


if __name__ == "__main__":
    main()

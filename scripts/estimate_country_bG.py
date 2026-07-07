"""Per-country income elasticity of air travel from the ACI throughput panel and OEF GDP
(Phase 3 real elasticities). Author: Avia Solutions.

For each country: aggregate ACI terminal passengers over its airports, 2013-2024, regress
ln(traffic) on ln(GDP constant) with COVID (2020-22) and supply-anomaly (2023-24) dummies
(the book's dummy convention). The GDP slope is the income elasticity bG. Reliability-filter
on sign, plausible range, significance and fit; failing countries fall back to the model's
region/maturity default downstream. Writes data/estimated_bG_by_country.json.
"""
from __future__ import annotations
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from avia_forecast.paths import DATA, OEF_DIR, ACI_DIR, ACI_DECRYPT, SABRE_DB, OAG_DB, QSI_REF, PREAGG, QSI_APP, OEF_GDP_XLSX
import json, os
from collections import defaultdict
import numpy as np
import statsmodels.api as sm

DATA = DATA
COVID = {2020, 2021, 2022}
SUPPLY = {2023, 2024}
BG_MIN, BG_MAX, MIN_OBS, MIN_R2, MIN_T = 0.3, 3.5, 8, 0.5, 1.7


def run():
    panel = json.load(open(os.path.join(DATA, "aci_panel_long.json")))
    oef = json.load(open(os.path.join(DATA, "oef_gdp_pop_by_iso2.json")))["gdp"]

    traf = defaultdict(lambda: defaultdict(float))    # iso2 -> year -> terminal
    for r in panel:
        if r["country_code"] and r["terminal_pax"]:
            traf[r["country_code"]][r["year"]] += r["terminal_pax"]

    out = {}
    for iso, ty in traf.items():
        g = oef.get(iso)
        if not g:
            continue
        yrs = sorted(y for y in ty if str(y) in g and ty[y] > 0 and g[str(y)] > 0)
        if len(yrs) < MIN_OBS:
            continue
        lt = np.log([ty[y] for y in yrs])
        lg = np.log([g[str(y)] for y in yrs])
        X = np.column_stack([lg,
                             [1.0 if y in COVID else 0.0 for y in yrs],
                             [1.0 if y in SUPPLY else 0.0 for y in yrs]])
        X = sm.add_constant(X)
        m = sm.OLS(lt, X).fit()
        bG, t, r2 = m.params[1], (m.params[1] / m.bse[1] if m.bse[1] else 0.0), m.rsquared
        ok = (BG_MIN <= bG <= BG_MAX) and abs(t) >= MIN_T and r2 >= MIN_R2
        out[iso] = {"bG": round(float(bG), 3), "t": round(float(t), 2),
                    "r2": round(float(r2), 3), "n": len(yrs), "reliable": bool(ok)}

    json.dump(out, open(os.path.join(DATA, "estimated_bG_by_country.json"), "w"), indent=1)
    rel = {k: v for k, v in out.items() if v["reliable"]}
    print(f"countries estimated: {len(out)}   reliable: {len(rel)}")
    print("sample (major markets):")
    for iso in ["US", "CN", "IN", "GB", "DE", "JP", "BR", "AE", "TR", "ID", "ES", "MX", "SA"]:
        if iso in out:
            v = out[iso]
            print(f"  {iso}: bG {v['bG']:>5}  t {v['t']:>5}  R2 {v['r2']:.2f}  n {v['n']}  {'OK' if v['reliable'] else 'pool'}")
    return out


if __name__ == "__main__":
    run()

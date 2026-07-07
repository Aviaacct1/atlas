"""Persist the per-airport income-elasticity regression diagnostics the engine already computes.

The engine's estimate.level1.fit_cell_restricted already returns the full fit (bG, R2, t-stat,
n, residuals). We previously saved only the bG scalar (uk_estimated_bG.json). This runs that same,
tested fit over the airport ACI panel and writes the FULL diagnostics to data/airport_regress.json
so the cockpit's Econometrics tab shows real R2, t and the observed scatter, not placeholders.

    { IATA: { "bG_est", "r2", "t", "n", "window", "reliable", "points": [[lnG_c, y_partial], ...] } }

Inputs (resolved via avia_forecast.paths, so E: on John's machine): the long ACI panel
(aci_panel_long.json), per-country OEF GDP, the constructed fare index and the segment fare terms.
Runs on the long panel; the short 2015-2024 window inflates the elasticities and must not be used.

Self-test without the panel:  python scripts/estimate_airport_diagnostics.py --selftest
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from avia_forecast.io_safe import dump_atomic
from avia_forecast.paths import DATA
import json, os, argparse
import numpy as np
import pandas as pd

from avia_forecast.estimate.level1 import fit_cell_restricted

REPO_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OUT = os.path.join(REPO_DATA, "airport_regress.json")
BG_BOUND = (0.6, 2.2)


def _repo(fn):
    fp = os.path.join(REPO_DATA, fn)
    return json.load(open(fp)) if os.path.exists(fp) else {}


def _panel(fn):
    fp = os.path.join(DATA, fn)
    return json.load(open(fp)) if os.path.exists(fp) else {}


def _diag(df, bF_segment):
    """Run the engine's restricted fit and return the diagnostics + a GDP partial-regression scatter."""
    fit = fit_cell_restricted(df, bF_segment)
    lnG = np.log(df.sort_values("year")["G"].to_numpy(dtype=float))
    lnGc = lnG - lnG.mean()
    resid = np.asarray(fit.resid, dtype=float)
    y_partial = fit.bG * lnGc + resid          # GDP-explained part + residual (partial regression)
    pts = [[round(float(x), 4), round(float(y), 4)] for x, y in zip(lnGc, y_partial)]
    reliable = (BG_BOUND[0] <= fit.bG <= BG_BOUND[1]) and abs(fit.t_bG) >= 1.7 and fit.r2 >= 0.5
    return {"bG_est": round(float(fit.bG), 3), "r2": round(float(fit.r2), 3),
            "t": round(float(fit.t_bG), 2), "n": int(fit.n_obs),
            "window": f"{int(df['year'].min())}-{int(df['year'].max())}",
            "reliable": bool(reliable), "points": pts}


def selftest():
    """Prove the persistence path on a synthetic cell with a known elasticity (no panel needed)."""
    rng = np.random.default_rng(0)
    yrs = list(range(1991, 2025))
    g = np.cumprod(np.r_[1.0, rng.normal(1.02, 0.01, len(yrs) - 1)])
    f = np.cumprod(np.r_[1.0, rng.normal(1.00, 0.02, len(yrs) - 1)])
    true_bG = 1.25
    p = (g ** true_bG) * (f ** -0.3) * np.exp(rng.normal(0, 0.02, len(yrs)))
    p = p * np.where(np.isin(yrs, [2020, 2021, 2022]), 0.5, 1.0)   # covid dip the dummy will absorb
    df = pd.DataFrame({"year": yrs, "P": p, "G": g, "F": f})
    d = _diag(df, bF_segment=-0.3)
    print(f"selftest: true bG {true_bG}  ->  fitted {d['bG_est']}  R2 {d['r2']}  t {d['t']}  n {d['n']}  points {len(d['points'])}")
    assert abs(d["bG_est"] - true_bG) < 0.15, "fit did not recover the known elasticity"
    assert len(d["points"]) == d["n"]
    print("selftest PASS")


def run(airports=None):
    from collections import defaultdict
    panel = _panel("aci_panel_long.json")            # LIST of {<airport code>, country_code, year, terminal_pax}
    if not panel:
        raise SystemExit("aci_panel_long.json not found under the data root - the ACI panel (E:) is required to run.")
    oef = _panel("oef_gdp_pop_by_iso2.json")
    gdp_all = (oef.get("gdp") if isinstance(oef, dict) else None) or {}
    pop_all = (oef.get("pop") or oef.get("population") if isinstance(oef, dict) else None) or {}
    gdp_uk = _repo("uk_real_gdp_oef.json")
    fare = _repo("fare_index_constructed.json")
    bF = _repo("uk_estimated_bF.json")
    seg = "International Short Haul"
    fseries = fare.get(seg) or {}
    bF_seg = bF.get(seg, -0.3)

    sample = panel[0] if isinstance(panel, list) and panel else {}
    codekey = next((k for k in ("iata", "airport_code", "code", "airport", "apt") if k in sample), None)
    if not codekey:
        raise SystemExit("no airport-code field in aci_panel_long.json; keys=" + str(list(sample.keys())))

    traf, ctry = defaultdict(dict), {}
    for r in panel:
        c, tp, y = r.get(codekey), r.get("terminal_pax"), r.get("year")
        if c and tp and y:
            traf[c][int(y)] = traf[c].get(int(y), 0.0) + float(tp)
            ctry[c] = r.get("country_code")

    out = {}
    for code in (airports or list(traf)):
        hist, iso = traf.get(code) or {}, ctry.get(code)
        gdp = gdp_uk if iso == "GB" else (gdp_all.get(iso) if gdp_all else None)
        if not hist or not gdp:
            continue
        pop = pop_all.get(iso) if pop_all else None
        rows, rows_pc = [], []
        for y, p in hist.items():
            gy = gdp.get(str(y)); fy = float(fseries.get(str(y), 100.0) or 100.0)
            if p and gy:
                rows.append({"year": int(y), "P": float(p), "G": float(gy), "F": fy})
                pv = pop.get(str(y)) if pop else None
                if pv:
                    rows_pc.append({"year": int(y), "P": float(p) / float(pv),
                                    "G": float(gy) / float(pv), "F": fy})   # pax per capita vs GDP per capita
        if len(rows) < 12:
            continue
        try:
            rec = _diag(pd.DataFrame(rows), bF_seg)                          # GDP elasticity (total GDP)
            if len(rows_pc) >= 12:
                inc = _diag(pd.DataFrame(rows_pc), bF_seg)                   # income elasticity (GDP per capita)
                rec["income"] = {"bY": inc["bG_est"], "r2": inc["r2"], "t": inc["t"],
                                 "n": inc["n"], "points": inc["points"]}
            out[code] = rec
        except Exception as e:
            print(f"  {code}: fit failed ({type(e).__name__}: {e})")
    dump_atomic(out, OUT, indent=1)
    print(f"airport_regress.json: {len(out)} airports with full diagnostics -> {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--airports", default="")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    else:
        run([x.strip().upper() for x in a.airports.split(",") if x.strip()] or None)

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
from avia_forecast.estimate.reliability import run_tests
from avia_forecast.config import get

REPO_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OUT = os.path.join(REPO_DATA, "airport_regress.json")
BG_BOUND = (0.6, 2.2)


def _bF_prior(segment):
    """Level 3 literature fare elasticity for the segment (Method Spec 4.5).

    This is the correct prior for the restricted Level 1 fit. It must NOT be read from
    uk_estimated_bF.json: that file records the Level 2 pooled estimates which FAILED the
    reliability sign test on the short UK panel (ISH +0.293, LH +0.273), and the method's
    own answer to that failure is to fall back to the Level 3 literature value.
    """
    try:
        return float(get("level3_defaults")[segment]["bF"])
    except Exception:
        return {"Domestic": -0.7, "International Short Haul": -0.7, "Long Haul": -0.5}.get(segment, -0.7)


def _repo(fn):
    fp = os.path.join(REPO_DATA, fn)
    return json.load(open(fp)) if os.path.exists(fp) else {}


def _panel(fn):
    fp = os.path.join(DATA, fn)
    return json.load(open(fp)) if os.path.exists(fp) else {}


def _diag(df, bF_segment, avg_flow_mppa=None):
    """Run the engine's restricted fit and return the diagnostics + a GDP partial-regression scatter.

    Reliability is decided by the engine's own T1-T6 rule (estimate.reliability.run_tests,
    Method Spec 4.4), with thresholds from the assumptions book, so the forecast, the cockpit
    and the Method Specification all use ONE definition. The full test trail is recorded so any
    airport's verdict is auditable and the Econometrics tab can show which test failed.

    `avg_flow_mppa` is the airport's average annual traffic in millions, needed by T5. Where it is
    not supplied (the per-capita income fit, and the self-test) the T5 flow leg cannot be evaluated
    and the older three-condition heuristic is reported instead, flagged via `rule`.
    """
    fit = fit_cell_restricted(df, bF_segment)
    lnG = np.log(df.sort_values("year")["G"].to_numpy(dtype=float))
    lnGc = lnG - lnG.mean()
    resid = np.asarray(fit.resid, dtype=float)
    y_partial = fit.bG * lnGc + resid          # GDP-explained part + residual (partial regression)
    pts = [[round(float(x), 4), round(float(y), 4)] for x, y in zip(lnGc, y_partial)]

    # the pre-July-2026 heuristic, kept only so the change in the applied set is measurable
    legacy = (BG_BOUND[0] <= fit.bG <= BG_BOUND[1]) and abs(fit.t_bG) >= 1.7 and fit.r2 >= 0.5

    rec = {"bG_est": round(float(fit.bG), 3), "r2": round(float(fit.r2), 3),
           "t": round(float(fit.t_bG), 2), "n": int(fit.n_obs),
           "window": f"{int(df['year'].min())}-{int(df['year'].max())}",
           "reliable_legacy": bool(legacy), "bF_prior": round(float(bF_segment), 3),
           "points": pts}

    if avg_flow_mppa is None:
        rec["reliable"] = bool(legacy)
        rec["rule"] = "legacy_heuristic_no_flow_data"
        return rec

    trail = run_tests(fit, df, bF_prior=bF_segment, avg_flow_mppa=float(avg_flow_mppa))
    rec["reliable"] = bool(trail.all_pass)
    rec["rule"] = "T1-T6"
    rec["tests"] = {"T1_sign": bool(trail.T1), "T2_range": bool(trail.T2),
                    "T3_significance": bool(trail.T3), "T4_fit": bool(trail.T4),
                    "T5_history": bool(trail.T5), "T6_cagr_cross_check": bool(trail.T6),
                    "bG_implied": (None if trail.bG_implied != trail.bG_implied
                                   else round(float(trail.bG_implied), 3)),
                    "t6_window": list(trail.t6_window) if trail.t6_window else None,
                    "avg_flow_mppa": round(float(avg_flow_mppa), 2)}
    return rec


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
    seg = "International Short Haul"
    fseries = fare.get(seg) or {}
    # Level 3 literature prior, not the rejected Level 2 UK estimates (see _bF_prior)
    bF_seg = _bF_prior(seg)
    print(f"fare prior for the restricted fit: bF({seg}) = {bF_seg}")

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
            avg_flow_mppa = (sum(float(v) for v in hist.values()) / len(hist)) / 1e6
            rec = _diag(pd.DataFrame(rows), bF_seg, avg_flow_mppa)           # GDP elasticity (total GDP)
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

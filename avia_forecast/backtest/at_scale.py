"""backtest/at_scale - Method Spec 9 backtest at scale (O-22). Author: Avia Solutions.

Stand the method at a base year, fit each airport's income elasticity on ACI history up to that year
(log-log OLS, book-clamped), drive forward with ACTUAL GDP, and score against the actual ACI outturn
and the naive GDP-multiple benchmark, at a clean horizon and through COVID.
"""
from __future__ import annotations
import math
from collections import defaultdict
import statistics

BOUNDS = (0.6, 2.2)


def _g(gdp_iso, y):
    return gdp_iso.get(str(y)) if gdp_iso.get(str(y)) is not None else gdp_iso.get(y)


def fit_bG(years_pax: dict, gdp_iso: dict, base_year: int, min_obs: int = 8, bounds=BOUNDS):
    """Log-log OLS of pax on GDP over years <= base_year; slope clamped to the book bounds."""
    xs, ys = [], []
    for y, p in years_pax.items():
        if y <= base_year and p and p > 0:
            g = _g(gdp_iso, y)
            if g and g > 0:
                xs.append(math.log(g)); ys.append(math.log(p))
    if len(xs) < min_obs:
        return None, len(xs)
    n = len(xs); mx = sum(xs) / n; my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None, n
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    b = sxy / sxx
    return max(bounds[0], min(bounds[1], b)), n


def score_airport(years_pax: dict, gdp_iso: dict, base_year: int, score_years, naive_mult: float):
    if base_year not in years_pax:
        return []
    bG, n = fit_bG(years_pax, gdp_iso, base_year)
    bg = _g(gdp_iso, base_year); bp = years_pax.get(base_year)
    if bG is None or not bg or not bp:
        return []
    out = []
    for sy in score_years:
        act = years_pax.get(sy); gsy = _g(gdp_iso, sy)
        if not act or not gsy:
            continue
        model = bp * (gsy / bg) ** bG
        naive = bp
        for y in range(base_year + 1, sy + 1):
            gy, gy1 = _g(gdp_iso, y), _g(gdp_iso, y - 1)
            gr = (gy / gy1 - 1.0) if (gy and gy1) else 0.0
            naive *= (1.0 + naive_mult * gr)
        out.append({"score_year": sy, "bG": bG, "n_fit": n, "actual": act, "model": model,
                    "naive": naive, "model_err": model / act - 1.0, "naive_err": naive / act - 1.0})
    return out


def run_scale(panel, gdp, base_year=2014, score_years=(2019, 2024), naive_mult=1.5, min_obs=8):
    """Score every airport in the ACI panel. Returns (exhibit, rows)."""
    traf, iso = defaultdict(dict), {}
    for r in panel:
        c, y, p = r.get("iata"), r.get("year"), r.get("terminal_pax")
        if c and y and p:
            traf[c][int(y)] = float(p); iso[c] = r.get("country_code")
    rows = []
    for c, yp in traf.items():
        gi = gdp.get(iso.get(c))
        if not gi:
            continue
        for rec in score_airport(yp, gi, base_year, score_years, naive_mult):
            rec["iata"] = c
            rows.append(rec)
    summary = {}
    for sy in score_years:
        rr = [r for r in rows if r["score_year"] == sy]
        if not rr:
            continue
        den = sum(r["actual"] for r in rr) or 1.0            # traffic weight
        wmape_m = sum(abs(r["model"] - r["actual"]) for r in rr) / den
        wmape_n = sum(abs(r["naive"] - r["actual"]) for r in rr) / den
        summary[sy] = {
            "n": len(rr),
            "wmape_model": wmape_m, "wmape_naive": wmape_n,      # traffic-weighted (headline)
            "median_ape_model": statistics.median(abs(r["model_err"]) for r in rr),
            "median_ape_naive": statistics.median(abs(r["naive_err"]) for r in rr),
            "mean_mape_model": sum(abs(r["model_err"]) for r in rr) / len(rr),   # outlier-sensitive; not headline
            "wbias_model": sum(r["model"] - r["actual"] for r in rr) / den,
            "model_beats_naive_share": sum(1 for r in rr if abs(r["model_err"]) < abs(r["naive_err"])) / len(rr),
            "beats_naive_wmape": wmape_m < wmape_n}
    return {"base_year": base_year, "naive_mult": naive_mult, "summary": summary, "n_scored": len(rows)}, rows

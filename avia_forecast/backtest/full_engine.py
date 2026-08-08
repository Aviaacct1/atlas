"""backtest/full_engine - full-engine forward backtest at country scale (D1). Author: Avia Solutions.

Drives the engine's propensity demand mechanism (estimate.propensity.evolve) forward at country level
with actual GDP and population, and scores traffic-weighted WMAPE against actual ACI outturn and the
naive GDP-multiple benchmark. Country grain because propensity is defined on trips per capita.
"""
from __future__ import annotations
from collections import defaultdict

from ..estimate import propensity as pr
from ..geo.regions_iso2 import region_for_iso2


def run_full_engine(panel, gdp, pop, base_year=2014, score_years=(2019, 2024), naive_mult=1.5):
    ctry = defaultdict(lambda: defaultdict(float))
    for r in panel:
        c, y, p = r.get("country_code"), r.get("year"), r.get("terminal_pax")
        if c and y and p:
            ctry[c][int(y)] += float(p)
    rows = []
    hz = max(score_years)
    for c, yp in ctry.items():
        g, pp = gdp.get(c), pop.get(c)
        if not g or not pp or base_year not in yp:
            continue
        yrs = list(range(base_year, hz + 1))
        if not all(str(y) in g and str(y) in pp for y in yrs):
            continue
        region = region_for_iso2(c) or "default"
        asy = pr.asymptote_for(region)
        population = {y: float(pp[str(y)]) * 1000.0 for y in yrs}       # pop in thousands -> persons
        gdp_pc = {y: float(g[str(y)]) / population[y] for y in yrs}
        base_pax = yp[base_year]
        path = pr.evolve(base_pax, population, gdp_pc, asy, yrs)
        for sy in score_years:
            act = yp.get(sy)
            if not act:
                continue
            model = path.traffic[sy]
            naive = base_pax
            for y in range(base_year + 1, sy + 1):
                naive *= (1.0 + naive_mult * (float(g[str(y)]) / float(g[str(y - 1)]) - 1.0))
            rows.append({"iso": c, "score_year": sy, "region": region, "actual": act,
                         "model": model, "naive": naive,
                         "model_err": model / act - 1.0, "naive_err": naive / act - 1.0})
    summary = {}
    for sy in score_years:
        rr = [r for r in rows if r["score_year"] == sy]
        if not rr:
            continue
        den = sum(r["actual"] for r in rr) or 1.0
        wm = sum(abs(r["model"] - r["actual"]) for r in rr) / den
        wn = sum(abs(r["naive"] - r["actual"]) for r in rr) / den
        summary[sy] = {"n": len(rr), "wmape_model": wm, "wmape_naive": wn,
                       "wbias_model": sum(r["model"] - r["actual"] for r in rr) / den,
                       "beats_naive_wmape": wm < wn}
    return {"base_year": base_year, "summary": summary, "n": len(rows)}, rows

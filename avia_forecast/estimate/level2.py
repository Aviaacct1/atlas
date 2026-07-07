"""Level 2 country-segment pooled panel (Method Spec 4.3; Elasticity Design 3).

Fixed-effects (within) estimator via least-squares dummy variables: each cell
keeps its own intercept, the slopes bG and bF are common across the panel, the
pandemic and supply dummies are common, standard errors are clustered by airport,
and observations are weighted by cell base-year pax share, capped so no single
airport exceeds the assumptions-book share of panel weight. This is where the
fare elasticity is estimated (segment level, Fable Part B). Author: Avia Solutions.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
import statsmodels.api as sm

from ..config import get


@dataclass
class PanelFit:
    bG: float
    bF: float
    se_bG: float
    se_bF: float
    n_cells: int
    n_obs: int
    estimable: bool
    reason: str = ""


@dataclass
class Cell:
    cell_id: str
    airport: str
    base_pax: float           # base-year pax, for weighting
    df: pd.DataFrame          # columns year, P, G, F


def _capped_weights(cells) -> dict:
    """Base-year pax weights, capped so no single AIRPORT exceeds the configured
    share of panel weight (Elasticity Design 3). Water-filling: cap the offending
    airports and redistribute the excess to the rest, iterating to a stable point;
    when the cap is infeasible (too few airports) it converges to equal shares.
    Cells inherit their airport's weight in proportion to base-year pax."""
    cap = get("level2.weight_cap_share")
    by_airport = {}
    for c in cells:
        by_airport.setdefault(c.airport, 0.0)
        by_airport[c.airport] += c.base_pax
    total = sum(by_airport.values())
    ashare = {a: v / total for a, v in by_airport.items()}
    for _ in range(200):
        over = {a for a, sh in ashare.items() if sh > cap + 1e-12}
        if not over:
            break
        excess = sum(ashare[a] - cap for a in over)
        for a in over:
            ashare[a] = cap
        under = {a: ashare[a] for a in ashare if a not in over}
        if not under:                                  # cap infeasible: equal shares
            tot = sum(ashare.values())
            ashare = {a: sh / tot for a, sh in ashare.items()}
            break
        tot_under = sum(under.values())
        for a in under:
            ashare[a] += excess * under[a] / tot_under
    ap_pax = by_airport
    return {c.cell_id: ashare[c.airport] * (c.base_pax / ap_pax[c.airport]) for c in cells}


def fit_panel(cells, dummies=("covid", "supply")) -> PanelFit:
    """Estimate common bG, bF across a country-segment panel of cells."""
    min_cells = get("level2.min_cells")
    min_obs = get("level2.min_obs")
    n_obs = sum(len(c.df) for c in cells)
    if len(cells) < min_cells or n_obs < min_obs:
        return PanelFit(float("nan"), float("nan"), float("nan"), float("nan"),
                        len(cells), n_obs, estimable=False,
                        reason=f"panel below minimum ({len(cells)} cells, {n_obs} obs)")

    w = _capped_weights(cells)
    pan = set(get("estimation.pandemic_years")); sup = set(get("estimation.supply_anomaly_years"))
    frames = []
    for c in cells:
        d = c.df.sort_values("year").copy()
        d["lnP"] = np.log(d["P"] / d["P"].iloc[0] * get("estimation.index_base_value"))
        d["lnG"] = np.log(d["G"] / d["G"].iloc[0] * get("estimation.index_base_value"))
        d["lnF"] = np.log(d["F"] / d["F"].iloc[0] * get("estimation.index_base_value"))
        d["cell"] = c.cell_id; d["airport"] = c.airport; d["w"] = w[c.cell_id]
        if "covid" in dummies:
            d["D"] = d["year"].isin(pan).astype(float)
        if "supply" in dummies:
            d["DS"] = d["year"].isin(sup).astype(float)
        frames.append(d)
    P = pd.concat(frames, ignore_index=True)

    Xcols = ["lnG", "lnF"] + [k for k in ("D", "DS") if k in P.columns]
    X = P[Xcols].copy()
    cell_dum = pd.get_dummies(P["cell"], prefix="c", drop_first=True).astype(float)  # cell fixed effects
    X = pd.concat([X, cell_dum], axis=1)
    X = sm.add_constant(X)
    model = sm.WLS(P["lnP"], X, weights=P["w"]).fit(
        cov_type="cluster", cov_kwds={"groups": P["airport"]})
    return PanelFit(
        bG=float(model.params["lnG"]), bF=float(model.params["lnF"]),
        se_bG=float(model.bse["lnG"]), se_bF=float(model.bse["lnF"]),
        n_cells=len(cells), n_obs=n_obs, estimable=True)


def passes_level2(fit: PanelFit) -> bool:
    """Level 2 estimates are tested with T1 (signs) and T2 (ranges) only
    (Elasticity Design 3). A failure routes the cell to Level 3."""
    if not fit.estimable:
        return False
    bG_ok = fit.bG > get("reliability.T1_signs.bG_gt")
    bF_ok = fit.bF < get("reliability.T1_signs.bF_lt")
    bGr = get("reliability.T2_range.bG"); bFr = get("reliability.T2_range.bF")
    return bG_ok and bF_ok and (bGr[0] <= fit.bG <= bGr[1]) and (bFr[0] <= fit.bF <= bFr[1])

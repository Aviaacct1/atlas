"""demand/core - unconstrained O&D recursion and fare build-up (Method Spec 4.1-4.2).

Pure functions: tidy frame in, tidy frame out. No numeric assumption here; theta
and tau come from the assumptions book. Author: Avia Solutions.

    OD(a,r,d,t) = OD(t-1) * (G_t/G_{t-1})^bG * (F_t/F_{t-1})^bF * (1 + A_t)   (4.1)
    F(r,s,t)    = F(t-1) * (1 + theta*dUC_t) * (1 + tau)                     (4.2)

GDP driver mapping (4.1): outbound uses home-market GDP; inbound uses the
destination-region GDP; domestic uses home GDP for both directions.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from ..config import get


def fare_path(F0: float, dUC, theta: float | None = None, tau: float | None = None):
    """Real fare index from the base year by cost pass-through plus yield trend (4.2).

    dUC: sequence of year-on-year unit-cost changes, one per forecast step."""
    theta = get("fare_index.pass_through_theta") if theta is None else theta
    tau = get("fare_index.real_yield_trend_tau") if tau is None else tau
    out = [F0]
    for d in dUC:
        out.append(out[-1] * (1.0 + theta * d) * (1.0 + tau))
    return np.array(out)


def od_recursion(OD0: float, G, F, bG: float, bF: float, A=None):
    """Multiplicative year-on-year O&D recursion (4.1).

    G, F: level series including the base year (index 0 = base). A: per-year
    adjustment overlay (same length as G, base ignored). Multiplicative
    application is mandatory: adding the GDP and fare effects diverges from the
    log-log estimation by a compounding margin over the horizon."""
    G = np.asarray(G, float); F = np.asarray(F, float)
    n = len(G)
    A = np.zeros(n) if A is None else np.asarray(A, float)
    od = np.empty(n); od[0] = OD0
    for t in range(1, n):
        od[t] = od[t-1] * (G[t]/G[t-1])**bG * (F[t]/F[t-1])**bF * (1.0 + A[t])
    return od


def od_additive_reference(OD0: float, G, F, bG: float, bF: float):
    """The rejected additive form, kept only so tests can quantify the divergence
    it causes against the mandated multiplicative form (4.1)."""
    G = np.asarray(G, float); F = np.asarray(F, float)
    n = len(G); od = np.empty(n); od[0] = OD0
    for t in range(1, n):
        g = (G[t]-G[t-1])/G[t-1]; f = (F[t]-F[t-1])/F[t-1]
        od[t] = od[t-1] * (1.0 + bG*g + bF*f)
    return od


def forecast_cell(od0: float, drivers: pd.DataFrame, bG: float, bF: float) -> pd.DataFrame:
    """Tidy in, tidy out for one (airport, region, direction) cell.

    drivers: columns year, G, F, and optional A; ordered, base year first."""
    d = drivers.sort_values("year").reset_index(drop=True)
    A = d["A"].values if "A" in d.columns else None
    od = od_recursion(od0, d["G"].values, d["F"].values, bG, bF, A)
    return pd.DataFrame({"year": d["year"].values, "metric": "od_pax", "value": od})


def od_recursion_damped(OD0, G, F, bG, bF, headroom, terminal_log=0.0, A=None):
    """Propensity-damped O&D recursion (Fable review P1). Preserves the airport's
    own income elasticity bG and the GDP driver mapping, but scales the income
    growth in EXCESS of the mature terminal rate by the remaining saturation
    headroom (1-s) each year:

        ln OD(t)/OD(t-1) = terminal + (bG*ln(G_t/G_{t-1}) - terminal) * headroom_t
                           + bF*ln(F_t/F_{t-1}) + ln(1+A_t)

    headroom=1 reproduces the constant-elasticity recursion exactly. Author: Avia Solutions."""
    G = np.asarray(G, float); F = np.asarray(F, float)
    n = len(G)
    A = np.zeros(n) if A is None else np.asarray(A, float)
    h = np.asarray(headroom, float)
    od = np.empty(n); od[0] = OD0
    for t in range(1, n):
        income = bG * np.log(G[t] / G[t-1])
        damped = terminal_log + (income - terminal_log) * h[t]
        fare = bF * np.log(F[t] / F[t-1])
        od[t] = od[t-1] * np.exp(damped + fare) * (1.0 + A[t])
    return od

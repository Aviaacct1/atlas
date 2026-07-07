"""estimate/fare_construction - cost-driven real fare index (Method Spec 4.2; G1 recipe).

Fares evolve from cost pass-through plus a structural real-yield trend:
    F(s,t) = F(s,t-1) * (1 + theta*dUC(s,t)) * (1 + tau)
dUC is the year-on-year unit-cost change from fuel (segment-weighted, net of the
fleet-efficiency path). This is the cost-driven construction the fare strategy uses
for the estimation series (2020-24 handled as the counterfactual by construction,
since it is cost-driven not observed). DB1B/GDD absolute levels (F15) remain a
data-sourcing item. Fuel is real (EIA via Jess's workbook). Author: Avia Solutions.
"""
from __future__ import annotations
from ..config import get

FUEL_SHARE = {"Domestic": 0.20, "International Short Haul": 0.28, "Long Haul": 0.35}   # [P1] long-haul more fuel-intensive


def build_fare_index(fuel: dict, years, efficiency_gain=0.015, theta=None, tau=None,
                     fuel_share=None) -> dict:
    """Return {segment: {year: index}} (base year = 100). fuel: {year: jet fuel price}."""
    theta = get("fare_index.pass_through_theta") if theta is None else theta
    tau = get("fare_index.real_yield_trend_tau") if tau is None else tau
    fuel_share = fuel_share or FUEL_SHARE
    out = {}
    for seg, share in fuel_share.items():
        idx, lvl = {}, 100.0
        for prev, y in zip([None] + years[:-1], years):
            if prev is not None and fuel.get(prev) and fuel.get(y):
                d_fuel = fuel[y] / fuel[prev] - 1.0
                dUC = share * (d_fuel - efficiency_gain)        # efficiency reduces fuel burn (share-weighted)
                lvl *= (1.0 + theta * dUC) * (1.0 + tau)
            idx[y] = lvl
        out[seg] = idx
    return out

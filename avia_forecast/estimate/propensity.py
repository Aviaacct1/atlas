"""estimate/propensity - propensity-to-fly maturity (Cockpit build update B1).

Replaces the maturity-decay parameter of Method Spec 4.5. A catchment's saturation
share s = trips-per-capita / asymptote. Growth above the mature terminal rate is
scaled by the remaining propensity headroom (1 - s); as traffic climbs the world
curve toward the ceiling, s rises, headroom shrinks and growth decays endogenously.
A low-saturation market (Delhi-class) keeps most of its excess growth; a
near-mature one (Manchester-class) keeps little. The world log trips-per-capita vs
log GDP-per-capita curve is fitted from Sabre/OAG trips, UN population and OEF GDP
per head, and also feeds the propensity chart (F3). Author: Avia Solutions.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np

from ..config import get


def fit_world_curve(gdp_pc, trips_pc):
    """Fit ln(trips_pc) = a + b ln(gdp_pc). Returns (a, b); b is the income response
    of the propensity to fly. Cross-country, base-year snapshot."""
    x = np.log(np.asarray(gdp_pc, float)); y = np.log(np.asarray(trips_pc, float))
    b, a = np.polyfit(x, y, 1)
    return float(a), float(b)


def curve_trips_pc(gdp_pc, a, b):
    return float(np.exp(a + b * np.log(gdp_pc)))


def saturation_share(trips_pc, asymptote):
    return min(1.0, trips_pc / asymptote)


def asymptote_for(region):
    tbl = get("propensity.region_asymptote_trips_pc")
    return tbl.get(region, tbl["default"])


@dataclass
class PropensityPath:
    years: list
    trips_pc: dict
    saturation: dict
    traffic: dict
    retained_excess_fraction: dict = field(default_factory=dict)


def evolve(base_traffic, population, gdp_pc, asymptote, years,
           income_elasticity=None, terminal_growth=None) -> PropensityPath:
    """Evolve a catchment's traffic under propensity saturation.

    base_traffic: base-year traffic (m pax). population, gdp_pc: {year: value}.
    Raw trips-per-capita growth = income_elasticity x GDP-per-capita growth; the
    excess over the terminal rate is retained in proportion to headroom (1 - s)."""
    ie = get("propensity.income_elasticity_tpc") if income_elasticity is None else income_elasticity
    term = get("propensity.terminal_tpc_growth") if terminal_growth is None else terminal_growth
    y0 = years[0]
    tpc = {y0: base_traffic / population[y0]}
    s = {y0: tpc[y0] / asymptote}
    traffic = {y0: base_traffic}
    retained = {}
    for prev, y in zip(years[:-1], years[1:]):
        g_gdp_pc = gdp_pc[y] / gdp_pc[prev] - 1.0
        raw = ie * g_gdp_pc                                  # unconstrained tpc growth
        headroom = max(0.0, 1.0 - s[prev])                   # floored at 0; no negative damping past maturity
        retained[y] = headroom
        tpc_growth = term + (raw - term) * headroom          # decelerates to the mature floor `term`, never to zero
        tpc[y] = tpc[prev] * (1.0 + tpc_growth)              # no hard ceiling: keeps growing at the floor
        s[y] = tpc[y] / asymptote                            # saturation may exceed 1 (mature markets still grow)
        traffic[y] = tpc[y] * population[y]
    return PropensityPath(years, tpc, s, traffic, retained)


def period_cagrs(traffic, spot_years):
    out = []
    for a, b in zip(spot_years[:-1], spot_years[1:]):
        out.append((traffic[b] / traffic[a]) ** (1.0 / (b - a)) - 1.0)
    return out

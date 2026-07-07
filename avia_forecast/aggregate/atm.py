"""aggregate/atm - commercial/cargo/GA ATMs and the design-day schedule
(Cockpit build update E1/E2). Total ATMs = commercial (segment seats/LF) + cargo
freighter + GA; the design-day flight schedule consumes TOTAL ATMs, not
commercial-only. Belly cargo rides in passenger ATMs and adds no freighter ATMs.
Author: Avia Solutions.
"""
from __future__ import annotations
from ..config import get


def commercial_atm(pax_by_segment: dict, seats_by_segment: dict, lf_by_segment: dict) -> float:
    """Sum over segments of pax / (seats x load factor)."""
    total = 0.0
    for seg, pax in pax_by_segment.items():
        denom = seats_by_segment[seg] * lf_by_segment[seg]
        if denom > 0:
            total += pax / denom
    return total


def cargo_tonnage(base_tonnes: float, gdp_index: dict, years, elasticity=None) -> dict:
    """Cargo tonnage grows with GDP: t = t0 * (G/G0)^elasticity."""
    e = get("cargo.gdp_elasticity") if elasticity is None else elasticity
    g0 = gdp_index[years[0]]
    return {y: base_tonnes * (gdp_index[y] / g0) ** e for y in years}


def cargo_freighter_atm(tonnes: float, belly_share=None, tonnes_per_atm=None) -> float:
    """Freighter ATMs from the non-belly share of cargo; belly rides in pax ATMs."""
    belly = get("cargo.belly_share") if belly_share is None else belly_share
    per = get("cargo.tonnes_per_freighter_atm") if tonnes_per_atm is None else tonnes_per_atm
    return tonnes * (1.0 - belly) / per if per > 0 else 0.0


def ga_series(base: float, growth: float, years) -> dict:
    """GA pax or GA ATMs with their own growth rate."""
    out, lvl = {}, base
    y0 = years[0]
    for y in years:
        if y > y0:
            lvl *= (1.0 + growth)
        out[y] = lvl
    return out


def total_atm(commercial: float, cargo_freighter: float, ga: float) -> float:
    return commercial + cargo_freighter + ga


def design_day(total_atm_value: float, fraction=None) -> float:
    """Design-day flight schedule movements from TOTAL ATMs (E2)."""
    frac = get("design_day.fraction_of_annual_atm") if fraction is None else fraction
    return total_atm_value * frac

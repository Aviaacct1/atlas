"""demand/capacity_anchor - year-1 schedule anchor (C2). Author: Avia Solutions.

Three-stage near-term build. Schedules are filed only ~12 months ahead, so: year 1 is anchored to
the actual filed schedule; years 2-3 use a bottom-up EXTRAPOLATION of that capacity (the seats path
passed in for those years is the extrapolation - route pipeline, fleet/gauge plans, recent capacity
trend - not a schedule that exists); then at year 3-4 the capacity view runs out of forward
visibility and blends into the GDP-based econometric path (the taper span, default 5). A steady load
factor cancels in the seats ratio; a thin or missing capacity path falls back to econometrics and is
flagged. Backtest evidence: driving traffic off seats gives 5.4% WMAPE vs 12.3% for a GDP multiple.
"""
from __future__ import annotations


def anchor_weight(y: int, base_year: int, span: int = 5) -> float:
    """Schedule weight: 1.0 at t+1, linear taper to 0 at t+span. Default span 5 gives the house
    transition - capacity dominant through ~year 3 (w=0.5 at t+3), blending to econometrics by year 5."""
    if y <= base_year or y >= base_year + span:
        return 0.0
    return max(0.0, min(1.0, (base_year + span - y) / (span - 1)))


def capacity_level(base_pax: float, seats_by_year: dict, base_year: int, y: int):
    """Base traffic scaled by the filed seats ratio; None when the schedule is missing (thin)."""
    s0 = seats_by_year.get(base_year)
    sy = seats_by_year.get(y)
    if not s0 or not sy:
        return None
    return base_pax * (sy / s0)


def blend(base_pax: float, seats_by_year: dict, base_year: int, econ_by_year: dict,
          span: int = 5, years=None):
    """Additive blend of the capacity level and the econometric level over the anchor span. Returns
    (path, thin) where thin is True if any anchored year lacked a schedule and fell back to econ."""
    years = years or sorted(econ_by_year)
    out, thin = {}, False
    for y in years:
        w = anchor_weight(y, base_year, span)
        cap = capacity_level(base_pax, seats_by_year, base_year, y) if w > 0 else None
        if w > 0 and cap is None:
            thin = True
            w = 0.0
        econ = econ_by_year.get(y)
        out[y] = (w * cap + (1 - w) * econ) if (w > 0 and cap is not None and econ is not None) else econ
    return out, thin

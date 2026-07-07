"""Level 3 region-segment defaults and precision weighting (Method Spec 4.5;
Elasticity Design 4). The pooled estimate is reconciled with the published
literature by precision weighting; the result is clipped to the applied bounds and
becomes the segment default. Literature values enter only here; they anchor the
tails, not the centre. Author: Avia Solutions.
"""
from __future__ import annotations
from dataclasses import dataclass
from ..config import get


@dataclass
class SegmentDefault:
    bG: float
    bF: float
    clipped: bool


def precision_weight(est: float, se_est: float, lit: float, se_lit: float | None = None) -> float:
    """Inverse-variance combination of an estimate with the literature prior."""
    se_lit = get("level3.se_lit") if se_lit is None else se_lit
    we, wl = 1.0 / se_est ** 2, 1.0 / se_lit ** 2
    return (est * we + lit * wl) / (we + wl)


def _clip(v, lo, hi):
    return max(lo, min(hi, v)), (v < lo or v > hi)


def segment_default(segment: str, maturity: str = "mature",
                    bG_est: float | None = None, se_est: float | None = None) -> SegmentDefault:
    """Region-segment default. If a pooled estimate is supplied, precision-weight
    the GDP elasticity with the literature prior; otherwise use the literature
    value. The fare elasticity default comes from the literature table."""
    lit = get(f"level3_defaults.{segment}")
    bG_lit = lit["bG_mature" if maturity == "mature" else "bG_emerging"]
    bF_lit = lit["bF"]
    bG = precision_weight(bG_est, se_est, bG_lit) if (bG_est is not None and se_est) else bG_lit
    glo, ghi = get("applied_bounds.bG"); flo, fhi = get("applied_bounds.bF")
    bGc, cg = _clip(bG, glo, ghi)
    bFc, cf = _clip(bF_lit, flo, fhi)
    return SegmentDefault(bGc, bFc, cg or cf)

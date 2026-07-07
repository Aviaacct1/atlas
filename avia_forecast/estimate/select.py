"""Selection rule and applied-value clipping (Method Spec 4.4).

Binary selection, not blending (Elasticity Design 5): the airport's own Level 1
estimate is used only if all six tests pass; otherwise Level 2; if Level 2 fails
signs/ranges, Level 3 defaults. Applied values are then clipped to final bounds.
Author: Avia Solutions.
"""
from __future__ import annotations
from dataclasses import dataclass
from ..config import get


@dataclass
class Applied:
    bG: float
    bF: float
    level: int
    clipped: bool
    reason_code: str = ""


def _clip(v, lo, hi):
    return (max(lo, min(hi, v)), v < lo or v > hi)


def clip_applied(bG: float, bF: float, level: int, reason_code: str = "") -> Applied:
    glo, ghi = get("applied_bounds.bG")
    flo, fhi = get("applied_bounds.bF")
    bGc, cg = _clip(bG, glo, ghi)
    bFc, cf = _clip(bF, flo, fhi)
    return Applied(bG=bGc, bF=bFc, level=level, clipped=(cg or cf), reason_code=reason_code)


def select(level1_fit, level1_trail, level2=None, level3=None) -> Applied:
    """Pick the applied elasticity by the mechanical rule.

    level2: optional (bG, bF) tuple that has passed its T1-T2.
    level3: (bG, bF) segment default (always available as final fallback).
    """
    if level1_trail is not None and level1_trail.all_pass:
        return clip_applied(level1_fit.bG, level1_fit.bF, level=1)
    if level2 is not None:
        return clip_applied(level2[0], level2[1], level=2)
    if level3 is not None:
        return clip_applied(level3[0], level3[1], level=3)
    raise ValueError("No Level 3 default supplied; every cell must have a fallback.")

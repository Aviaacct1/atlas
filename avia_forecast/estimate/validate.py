"""estimate/validate - V-FARE two-method agreement (Fable Part B; Method Spec 9).

The US is the fare-method laboratory: estimate the segment fare elasticity twice,
once from DB1B observed transaction fares and once from the cost-driven
construction, and require agreement within tolerance. If the cost-driven method
reproduces the observed-fare answer where truth is knowable, it earns its global
use. Author: Avia Solutions.
"""
from __future__ import annotations
from dataclasses import dataclass
from ..config import get


@dataclass
class VFareResult:
    bF_observed: float
    bF_cost_driven: float
    gap: float
    ok: bool


def vfare_agreement(bF_observed: float, bF_cost_driven: float, tol: float | None = None) -> VFareResult:
    tol = get("fare_strategy.vfare_tolerance") if tol is None else tol
    gap = abs(bF_observed - bF_cost_driven)
    return VFareResult(bF_observed, bF_cost_driven, gap, gap <= tol)

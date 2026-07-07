"""Maturity decay of the applied GDP elasticity (Method Spec 4.5).

bG(t) = bG_inf + [bG(T0) - bG_inf] * exp(-lambda * (t - T0))

lambda, the long-run floors bG_inf by segment and the base year all come from
the assumptions book. Author: Avia Solutions.
"""
from __future__ import annotations
import numpy as np
from ..config import get


def decay_path(bG_T0: float, segment: str, years):
    lam = get("maturity.lambda")
    inf = get(f"maturity.bG_inf.{segment}")
    T0 = get("meta.base_year")
    years = np.asarray(list(years), dtype=float)
    return inf + (bG_T0 - inf) * np.exp(-lam * (years - T0))

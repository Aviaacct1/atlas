"""estimate/od_reest - O&D-based elasticity re-estimation (B1 / O-19). Author: Avia Solutions.

Re-estimates income elasticity on TRUE O&D (Sabre endpoints, transfers excluded) instead of ACI
terminal, via the restricted covid-dummy regression, to test whether removing hub contamination
returns the book clamp to a backstop.

FINDING (12 Jul 2026, real MAN data): it does NOT. At capacity-growing airports the local O&D still
grows far faster than GDP (MAN O&D +5.6%/yr vs UK GDP +2.2%/yr, 2013-19), so the GDP regression
over-attributes capacity-led growth to income and the elasticity stays above the clamp (MAN O&D
restricted ~3.5, terminal ~3.0). The clamp remains binding; the real separation is capacity (carrier
blocks / propensity) versus income, not terminal-vs-O&D.
"""
from __future__ import annotations
import pandas as pd

from .level1 import fit_cell_restricted

BOUNDS = (0.6, 2.2)


def estimate_od_bG(od_series: dict, gdp_series: dict, bF_segment: float = -0.3,
                   bounds=BOUNDS, min_obs: int = 8):
    """Restricted (covid-dummy) fit of O&D pax on GDP. Returns the raw and clamped bG, fit stats,
    whether the clamp binds and whether the estimate is reliable; None if too few points."""
    def g(y):
        return gdp_series.get(str(y), gdp_series.get(y))
    rows = [{"year": int(y), "P": float(od_series[y]), "G": float(g(y)), "F": 100.0}
            for y in od_series if g(y)]
    if len(rows) < min_obs:
        return None
    fit = fit_cell_restricted(pd.DataFrame(rows), bF_segment)
    raw = float(fit.bG)
    clamped = max(bounds[0], min(bounds[1], raw))
    reliable = (bounds[0] <= raw <= bounds[1]) and abs(fit.t_bG) >= 1.7 and fit.r2 >= 0.5
    return {"bG_raw": round(raw, 3), "bG_clamped": round(clamped, 3), "r2": round(float(fit.r2), 3),
            "t": round(float(fit.t_bG), 2), "n": int(fit.n_obs), "reliable": bool(reliable),
            "clamp_binds": abs(raw - clamped) > 1e-9}

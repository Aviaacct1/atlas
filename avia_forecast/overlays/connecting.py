"""overlays/connecting - connecting overlay and final-to-next mapping
(Method Spec 5.2, 5.4; Fable Q3 conventions). Author: Avia Solutions.

Final-to-next: ND(a, r') = sum_r OD(a, r) * M[r][r'], where M[final_region][
first_leg_region] is row-stochastic (each final-destination region's shares
across first-leg regions sum to 1), so total ND = total OD (identity T-A).
Default M is the identity (ND = OD) for non-hub airports; hubs carry a
schedule-derived M.

Connecting overlay (pass 1, unconstrained): CONX grows with the unconstrained
region-pair flow of the markets it connects, at constant hub share H (default 1).
"""
from __future__ import annotations
import numpy as np


def identity_matrix(regions) -> dict:
    """M = I: every final-destination region's first leg lands in that region."""
    return {r: {c: (1.0 if r == c else 0.0) for c in regions} for r in regions}


def is_row_stochastic(M: dict, tol: float = 1e-9) -> bool:
    return all(abs(sum(row.values()) - 1.0) <= tol for row in M.values())


def final_to_next(od_by_region: dict, M: dict) -> dict:
    """OD final-destination vector -> ND first-leg vector via M (5.4)."""
    if not is_row_stochastic(M):
        raise ValueError("Final-to-next matrix M is not row-stochastic (5.4).")
    regions = list(od_by_region.keys())
    nd = {c: 0.0 for c in regions}
    for r, od in od_by_region.items():
        for c, share in M[r].items():
            nd[c] += od * share
    return nd


def connecting_growth(conx_base: float, odflow_ratio: float, H: float = 1.0) -> float:
    """CONX(a,p,t) = CONX(a,p,T0) * (ODflow(p,t)/ODflow(p,T0)) * H(a,t)  (5.2).

    odflow_ratio is taken from the UNCONSTRAINED region-pair flow (pass 1)."""
    return conx_base * odflow_ratio * H


def terminal_unconstrained(od_by_region: dict, conx_total: float) -> float:
    """TERM = sum OD + CONX (identity T-B)."""
    return float(sum(od_by_region.values())) + conx_total


def final_to_next_nonstop(regions, home_region, nonstop_regions,
                          hub_firstleg_region, diagonal_share: float | None = None) -> dict:
    """Nonstop-service fallback matrix where Sabre GDD is thin (Fable Q4).

    For a final region r: identity for the home region and Domestic; where a has
    nonstop service to r, a diagonal (direct) share with the remainder routed via
    the designated hub's first-leg region; 100% via that hub where there is no
    nonstop service. hub_firstleg_region maps final region -> the region the
    designated hub sits in. Rows are stochastic by construction."""
    from ..config import get
    diagonal_share = get("final_to_next.nonstop_diagonal_share") if diagonal_share is None else diagonal_share
    nonstop = set(nonstop_regions)
    M = {}
    for r in regions:
        row = {c: 0.0 for c in regions}
        if r == "Domestic" or r == home_region:
            row[r] = 1.0
        else:
            hub_r = hub_firstleg_region.get(r)
            if hub_r is None:
                row[r] = 1.0                          # no hub mapping: treat as direct
            elif r in nonstop:
                row[r] = diagonal_share
                row[hub_r] += (1.0 - diagonal_share)
            else:
                row[hub_r] = 1.0                       # no nonstop: all via hub
        M[r] = row
    return M


def implied_connections(od_by_region: dict, M: dict) -> float:
    """Base-year one-connection journeys implied by M: for each final region r,
    the O&D share whose first leg lands in a different region (off-diagonal mass)."""
    total = 0.0
    for r, od in od_by_region.items():
        total += od * (1.0 - M[r].get(r, 0.0))
    return float(total)

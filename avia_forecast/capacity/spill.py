"""capacity/spill - progressive spill, catchment redistribution and the both-ends
composition (Method Spec 6; Fable Q1 refinement 2 and Q2). Author: Avia Solutions.

Spill curve, connecting-first allocation at 1.5x pro-rata, the airport retention
ratio, an order-free simultaneous catchment redistribution that fills receivers
to K without re-spilling, and the multiplicative both-ends flow composition with
sequential attribution (identity T-D).
"""
from __future__ import annotations
from dataclasses import dataclass

import numpy as np

from ..config import get


def spill_fraction(u: float) -> float:
    """Piecewise-linear spill curve sp(u) from the assumptions book (6.2)."""
    curve = get("capacity.spill_curve")
    us = [pt["u"] for pt in curve]
    sps = [pt["sp"] for pt in curve]
    if u <= us[0]:
        return sps[0]
    if u >= us[-1]:
        return sps[-1]
    return float(np.interp(u, us, sps))


@dataclass
class AirportSolve:
    U: float          # unconstrained terminal demand
    K: float          # capacity
    C: float          # constrained terminal (own solve)
    retention: float  # rho = C/U
    spill: float      # E = U - C
    headroom: float   # max(0, K - C)


def airport_solve(U: float, K: float) -> AirportSolve:
    """C(a) = min(U*(1 - sp(u)), K); rho = C/U (6.2). K <= 0 means no register
    entry, so the airport is treated as unconstrained."""
    if K <= 0:
        return AirportSolve(U, K, U, 1.0, 0.0, 0.0)
    u = U / K
    C = max(0.0, min(U * (1.0 - spill_fraction(u)), K))
    return AirportSolve(U, K, C, (C / U if U > 0 else 1.0), U - C, max(0.0, K - C))


def allocate_shortfall(od_total: float, conx_total: float, E: float):
    """Split the shortfall E across O&D and connecting, connecting first at 1.5x
    pro-rata (6.2). Returns (od_reduction, conx_reduction)."""
    if E <= 0:
        return 0.0, 0.0
    mult = get("capacity.conx_spill_multiple")
    denom = od_total + mult * conx_total
    if denom <= 0:
        return 0.0, 0.0
    x = E / denom                                  # base O&D reduction rate
    conx_red = min(conx_total, mult * x * conx_total)
    od_red = E - conx_red                          # <= od_total by construction (E <= U)
    return od_red, conx_red


def constrained_connecting(conx_u: float, conx_reduction: float) -> float:
    """Constrained connecting = unconstrained connecting minus its spill share,
    i.e. unconstrained * hub retention (Fable Q1). Not re-grown from constrained
    feed flows in v1."""
    return conx_u - conx_reduction


@dataclass
class Redistribution:
    redistributed: list      # per-airport traffic received (<= headroom)
    served: list             # per-airport constrained + received (<= K)
    suppressed_total: float
    redistributed_total: float


def _theta_headroom(s: "AirportSolve", theta: float) -> float:
    """Receiving headroom measured to the spill-start threshold theta*K, not K
    (Fable Q6, amends Part 1). No receiver is filled past the point at which its
    own spill curve activates, so no second-round spill can exist."""
    if s.K <= 0:
        return 0.0
    return max(0.0, theta * s.K - s.C)


def catchment_redistribute(solves, theta: float | None = None) -> Redistribution:
    """Order-free simultaneous redistribution within one catchment (Fable Q1 rule 2
    as amended by Q6).

    Pool every airport's spill and allocate pro-rata to receiving headroom, where
    headroom is measured to theta*K (the spill-start threshold), in one linear
    pass. The no-cascade property is exact: no receiver reaches its own spill
    threshold, so no re-spill occurs and iteration has nothing to converge on. The
    pool beyond total catchment headroom is suppressed. Order-free and deterministic."""
    theta = get("capacity_redistribution.spill_start_threshold") if theta is None else theta
    pool = float(sum(s.spill for s in solves))
    headrooms = [_theta_headroom(s, theta) for s in solves]
    H = float(sum(headrooms))
    if H <= 0:
        received = [0.0 for _ in solves]
        return Redistribution(received, [s.C for s in solves], pool, 0.0)
    frac = min(1.0, pool / H)
    received = [h * frac for h in headrooms]           # <= theta*K - C, never re-spills
    redistributed_total = min(pool, H)
    suppressed_total = max(0.0, pool - H)
    served = [s.C + r for s, r in zip(solves, received)]
    return Redistribution(received, served, suppressed_total, redistributed_total)


@dataclass
class BothEnds:
    flow_c: float
    origin_booking: float
    dest_booking: float


def both_ends(flow_u: float, rho_o: float, rho_d_bar: float) -> BothEnds:
    """Multiplicative both-ends composition with sequential attribution (Fable Q2,
    amends Method Spec 6.4).

        flow_c          = flow_u * rho_o * rho_d_bar
        origin booking  = flow_u * (1 - rho_o)
        dest booking    = flow_u * rho_o * (1 - rho_d_bar)

    The three sum to flow_u by construction (identity T-D). The cross-term is
    attributed to the destination because the origin's own solve fixed its
    retention before the destination constraint was consulted."""
    flow_c = flow_u * rho_o * rho_d_bar
    origin_booking = flow_u * (1.0 - rho_o)
    dest_booking = flow_u * rho_o * (1.0 - rho_d_bar)
    return BothEnds(flow_c, origin_booking, dest_booking)

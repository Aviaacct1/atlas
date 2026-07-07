"""aggregate/reconcile - build-stopping identity checks T-A..T-E and tolerances
(Method Spec 7.5; Fable Tier 1). A failure raises and stops the release.
Author: Avia Solutions.
"""
from __future__ import annotations
from dataclasses import dataclass

from ..config import get


class ReconciliationError(AssertionError):
    """Raised when a build-stopping identity is violated."""


def _fail(name, detail):
    raise ReconciliationError(f"{name} violated: {detail}")


def check_TA(od_out_total: float, nd_total: float, tol: float = 1e-9):
    """Sum ND = Sum OD(out) per airport-year (final-to-next is row-stochastic)."""
    if abs(od_out_total - nd_total) > tol * max(1.0, abs(od_out_total)):
        _fail("T-A", f"ND total {nd_total} != OD out total {od_out_total}")


def check_TB(term: float, od_total: float, conx_total: float, tol: float = 1e-9):
    """TERM = sum OD + CONX per airport-year (exact)."""
    if abs(term - (od_total + conx_total)) > tol * max(1.0, abs(term)):
        _fail("T-B", f"TERM {term} != OD {od_total} + CONX {conx_total}")


def check_TC(total_leg_pax: float, od_intl_out_total: float, od_domestic_total: float,
             conx_total: float, tol: float = 1e-6):
    """Total emitted leg-pax = [intl outbound OD + domestic OD/2] + CONX."""
    expected = od_intl_out_total + od_domestic_total / 2.0 + conx_total
    if abs(total_leg_pax - expected) > tol * max(1.0, abs(expected)):
        _fail("T-C", f"leg pax {total_leg_pax} != expected {expected}")


def check_TD(flow_u: float, be, tol: float = 1e-9):
    """flow_u = flow_c + origin booking + destination booking (every flow)."""
    total = be.flow_c + be.origin_booking + be.dest_booking
    if abs(flow_u - total) > tol * max(1.0, abs(flow_u)):
        _fail("T-D", f"flow_u {flow_u} != flow_c+origin+dest {total}")


@dataclass
class RegrowFlag:
    hub: str
    gap: float
    hub_terminal: float
    gap_share: float
    escalate: bool


def regrow_diagnostic(hub: str, conx_c_by_market: dict, conx_u_by_market: dict,
                      flow_c_by_market: dict, flow_u_by_market: dict,
                      hub_terminal: float) -> RegrowFlag:
    """T-E connecting re-grow diagnostic (Fable Q1 refinement 1).

    CONX'(p) = CONX_u(p) * flow_c(p)/flow_u(p); report sum|CONX_c - CONX'| for the
    hub and flag escalation to a damped iteration if the gap exceeds the
    assumptions-book share of the hub's terminal."""
    gap = 0.0
    for p, conx_u in conx_u_by_market.items():
        fu = flow_u_by_market.get(p, 0.0)
        ratio = (flow_c_by_market.get(p, 0.0) / fu) if fu > 0 else 0.0
        conx_prime = conx_u * ratio
        gap += abs(conx_c_by_market.get(p, 0.0) - conx_prime)
    share = gap / hub_terminal if hub_terminal > 0 else 0.0
    thr = get("pipeline.connecting_regrow_escalate_pct")
    return RegrowFlag(hub, gap, hub_terminal, share, share > thr)


def check_both_ends_vs_capreq(flow_suppression_total: float, airport_capreq_total: float,
                              tol: float | None = None) -> bool:
    """Flow-level suppression vs airport capacity requirement within tolerance
    (Fable Q2). Returns True if consistent; a wider gap flags an aggregation
    defect rather than raising, since it is a monitoring check."""
    tol = get("pipeline.both_ends_vs_capreq_tol") if tol is None else tol
    denom = max(1.0, abs(airport_capreq_total))
    return abs(flow_suppression_total - airport_capreq_total) / denom <= tol


@dataclass
class TFResult:
    ok: bool
    implied_connections: float
    base_conx: float
    conx_scale: float        # factor to scale base CONX to match M (applied when not ok)


def check_TF(implied_connections_total: float, base_conx_total: float,
             tol: float | None = None) -> TFResult:
    """T-F (base-year, build-stopping): the one-connection journeys implied by the
    final-to-next matrix must match the base-year connecting total within tolerance
    (Fable Q4). Outside tolerance, CONX is scaled pro-rata to M (the better-estimated
    object under GDD) and the exception report is flagged; this is returned, not
    raised, so the caller can apply the scale and record the flag."""
    tol = get("final_to_next.TF_offdiag_vs_conx_tol") if tol is None else tol
    if base_conx_total <= 0:
        return TFResult(implied_connections_total == 0, implied_connections_total, base_conx_total, 1.0)
    rel = abs(implied_connections_total - base_conx_total) / base_conx_total
    scale = implied_connections_total / base_conx_total
    return TFResult(rel <= tol, implied_connections_total, base_conx_total, scale)


@dataclass
class MirrorResult:
    country_pair: str
    home: float
    partner: float
    canonical_value: float
    signed_gap: float        # (partner - home)/home; sign preserved for bias detection
    flagged: bool


def reconcile_mirror(country_pair: str, home: float, partner: float,
                     tol: float | None = None) -> MirrorResult:
    """Mirror reconciliation, always-canonical (Fable Q5). The canonical side is
    home by default and flips per country pair only through versioned config, never
    a build-time branch. The signed gap is reported (not its magnitude) so a
    persistent partner-side bias shows as a pattern in the exception report."""
    from ..config import sources as load_sources
    tol = get("reconciliation.mirror_flow_tolerance") if tol is None else tol
    cfg = load_sources().get("mirror_canonicality", {"default": "home", "flips": []})
    side = "partner" if country_pair in (cfg.get("flips") or []) else cfg.get("default", "home")
    canonical = partner if side == "partner" else home
    signed_gap = (partner - home) / home if home != 0 else float("nan")
    flagged = abs(signed_gap) > tol if home != 0 else True
    return MirrorResult(country_pair, home, partner, canonical, signed_gap, flagged)


@dataclass
class ATFMFlag:
    iata: str
    grade: str               # register K_grade
    delay_per_arr: float     # Eurocontrol arrival ATFM delay, minutes/arrival
    flagged: bool            # unconstrained but chronically delayed -> wrong register entry


def check_atfm_validation(iata: str, k_grade: str, has_k: bool,
                          delay_per_arr: float | None,
                          tol: float | None = None) -> ATFMFlag:
    """ATFM-delay validation proxy (Capacity Register Design; wire into the exception
    report). An airport the register treats as unconstrained (grade C, or any grade
    with no derived K) that nonetheless shows chronic Eurocontrol arrival ATFM delay
    is almost certainly a wrong or missing register entry: real capacity is biting.
    Flagged, not raised, so the loader can surface it for Jol to correct the register."""
    tol = get("capacity_register.atfm_delay_flag_min_per_arr") if tol is None else tol
    unconstrained = (not has_k) or (k_grade or "").upper() == "C"
    d = delay_per_arr if delay_per_arr is not None else 0.0
    flagged = unconstrained and d > tol
    return ATFMFlag(iata, (k_grade or "C").upper(), d, flagged)

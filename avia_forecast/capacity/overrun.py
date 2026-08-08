"""capacity/overrun - the rated-terminal overrun disposition (steer doc, 7 Aug 2026).

John's ruling: a rated terminal level is a service-level line, not a wall. The model
carries a FOURTH knowledge state, constraint_overrun_observed, for airports whose
observed base-year throughput exceeds their rated capacity (NTE and BSL in the France
harvest). Behaviour, per the steer:

  1. K is NEVER floored at throughput; the register keeps the rated figure and its
     citation, and the overrun is reported as a finding.
  2. Spill applies only to growth ABOVE the observed base level: the base year itself
     proves that level squeezes through. Of demand above that level, a soft share
     (config capacity_overrun.soft_spill_share, PROVISIONAL pending the capacity
     workstream's parameters) spills; the remainder squeezes through at a service
     cost, which the service-quality exhibit prices.
  3. No hard cap is applied where none is held (config records this explicitly).

Base-year spill is zero by construction, so check C2 reads "base-year requirement
zero after overrun accounting" and passes on genuine data.
Author: Avia Solutions."""
from __future__ import annotations

from ..config import get

STATE = "constraint_overrun_observed"


def is_overrun(base_observed_m, rated_base_m) -> bool:
    return (base_observed_m is not None and rated_base_m is not None
            and base_observed_m > rated_base_m)


def soft_paths(unconstrained: dict, capacity: dict, base_year: int,
               share: float | None = None):
    """Recompute (spill, constrained, overrun_above_rated) under the soft rule.

    Threshold T(y) = max(rated K(y), observed base level B): above T, `share` of the
    excess spills; below T everything is served. Overrun above rated is reported per
    year as a finding, not a spill."""
    share = float(get("capacity_overrun.soft_spill_share")) if share is None else share
    B = unconstrained[base_year]
    kb = capacity.get(base_year)
    spill, constrained, over_rated = {}, {}, {}
    for y, U in unconstrained.items():
        K = capacity.get(y, kb)
        T = max(K, B) if K is not None else B
        excess = max(0.0, U - T)
        spill[y] = share * excess
        constrained[y] = U - spill[y]
        over_rated[y] = max(0.0, constrained[y] - K) if K is not None else 0.0
    return spill, constrained, over_rated


def finding(iata: str, observed_base_m: float, rated_base_m: float,
            share: float) -> str:
    over = observed_base_m - rated_base_m
    return (f"{iata} operates {over:.1f}m passengers a year above its rated terminal "
            f"capacity ({rated_base_m:.1f}m rated). The rated level is treated as a "
            f"service-level line, not a wall: growth above the observed level spills "
            f"at a provisional {share:.0%} share and the remainder squeezes through "
            f"at a service cost. Parameters provisional (steer 7 Aug 2026) pending "
            f"the capacity workstream; no hard cap held.")


def apply(results: dict, base_year: int) -> dict:
    """Post-pass over constrain_all results. Reclassifies overrun airports, replaces
    their hard-spill paths with the soft rule, appends the finding to the statement.
    Returns {iata: overrun_info}. Mutates in place; call before any check or extract."""
    share = float(get("capacity_overrun.soft_spill_share"))
    info = {}
    for iata, r in results.items():
        if r.resolution.state != "constrained_evidenced":
            continue
        B = r.unconstrained.get(base_year)
        Kb = r.capacity.get(base_year)
        if not is_overrun(B, Kb):
            continue
        sp, con, over = soft_paths(r.unconstrained, r.capacity, base_year, share)
        r.spill, r.constrained = sp, con
        r.resolution.state = STATE
        f = finding(iata, B, Kb, share)
        r.resolution.statement = (getattr(r.resolution, "statement", "") or "").strip()
        if hasattr(r.resolution, "statement"):
            r.resolution.statement = f + " Register record: " + r.resolution.statement
        info[iata] = {"observed_base_m": round(B, 2), "rated_m": round(Kb, 2),
                      "overrun_base_m": round(B - Kb, 2),
                      "soft_spill_share": share, "hard_cap": "none held",
                      "overrun_above_rated_m": {y: round(v, 2) for y, v in over.items()},
                      "finding": f}
    return info

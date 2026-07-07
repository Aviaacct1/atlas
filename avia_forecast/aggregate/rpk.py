"""aggregate/rpk - region-pair flows and the leg-based RPK ledger
(Method Spec 7.3-7.4; Fable Q3 conventions). Author: Avia Solutions.

Leg ledger conventions (normative, Fable Q3):
  1. Connecting is onward-only: each connecting passenger emits one leg, the
     onward leg, classified by the final-destination region. The arriving leg
     belongs to the origin's next-destination record.
  2. Outbound-only emission: legs are emitted from outbound records only; inbound
     records exist for airport reporting and the mirror check, and emit nothing.
  3. Domestic at half-weight from each end: domestic legs are emitted at weight
     0.5 from each recording airport's domestic cells (end-agnostic data).
"""
from __future__ import annotations
from dataclasses import dataclass


DOMESTIC = "Domestic"


def region_pair_flows(od_rows) -> dict:
    """Outbound region-pair flows (7.3). od_rows: iterable of dicts with
    home_region, dest_region, direction, value. Returns {(i, j): flow}."""
    flows: dict = {}
    for r in od_rows:
        if r["direction"] != "out":
            continue
        key = (r["home_region"], r["dest_region"])
        flows[key] = flows.get(key, 0.0) + r["value"]
    return flows


@dataclass
class Leg:
    source: str        # "ND" or "CONX"
    airport: str
    region: str        # leg destination region
    pax: float
    distance: float
    rpk: float


def build_leg_ledger(nd_records, conx_records, dist) -> dict:
    """Emit legs under the three conventions and compute RPK.

    nd_records: dicts with airport, region (first-leg region), value,
      is_domestic. Only outbound next-destination records should be passed
      (Convention 2); domestic records are weighted 0.5 here (Convention 3).
    conx_records: dicts with hub, region (onward final-destination region), value.
    dist: callable dist(airport, region) -> great-circle distance.
    """
    legs = []
    for r in nd_records:
        w = 0.5 if r.get("is_domestic") else 1.0
        pax = r["value"] * w
        d = dist(r["airport"], r["region"])
        legs.append(Leg("ND", r["airport"], r["region"], pax, d, pax * d))
    for r in conx_records:
        d = dist(r["hub"], r["region"])
        legs.append(Leg("CONX", r["hub"], r["region"], r["value"], d, r["value"] * d))
    return {
        "legs": legs,
        "total_leg_pax": float(sum(l.pax for l in legs)),
        "rpk_total": float(sum(l.rpk for l in legs)),
    }

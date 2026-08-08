"""capacity/catchment_join - one entry point for catchment-spill redistribution,
across both catchment topologies (7 Aug 2026). Author: Avia Solutions.

Sources, in preference order:
  1. data/catchments_qsi.json - the QSI tool's drive-time catchments (distance +
     drive time, water respected), one catchment PER AIRPORT. These OVERLAP, so
     redistribution uses the overlap-safe allocator below.
  2. data/global_catchments_2025.json - the 642-catchment partition (disjoint);
     falls back to spill.catchment_redistribute's pooled rule.

Overlap-safe allocation (order-free, one scaling round):
  each spiller's pool is offered pro-rata to the receiving headroom of ITS catchment
  (headroom to theta*K, per the no-cascade rule); where several spillers want the
  same receiver, the receiver's allocations scale down together to its headroom.
  Unplaced spill stays suppressed. Conservation per spiller and the no-cascade
  property per receiver both hold by construction; a second allocation round is a
  possible refinement, recorded, not silently added."""
from __future__ import annotations
import json, os

from ..config import get

QSI_FILE = "catchments_qsi.json"
PARTITION_FILE = "global_catchments_2025.json"


def _normalise(raw):
    """Normalise any accepted file shape to {iata: {"layers": [(share, members, weights)],
    "penalties": {...}}}. Layers: nested two-layer (surface at od_share, network at the
    remainder), flat single-layer, or bare member lists."""
    out = {}
    for i, v in raw.items():
        if i == "meta":
            continue
        if isinstance(v, dict) and ("surface" in v or "network" in v):
            od = float(v.get("od_share", 1.0))
            layers, pens = [], {}
            s = v.get("surface") or {}
            if s.get("members"):
                layers.append((od, list(s["members"]), s.get("weights") or None))
                pens["surface_access_penalty_min"] = s.get("access_penalty_min")
            n = v.get("network") or {}
            if n.get("members"):
                layers.append((1.0 - od, list(n["members"]), n.get("weights") or None))
                pens["network_journey_penalty_min"] = n.get("journey_penalty_min")
            out[i] = {"layers": layers, "penalties": pens, "flags": v.get("flags", [])}
        elif isinstance(v, dict):
            out[i] = {"layers": [(1.0, list(v.get("members", [])), v.get("weights") or None)],
                      "penalties": {}, "flags": []}
        else:
            out[i] = {"layers": [(1.0, list(v), None)], "penalties": {}, "flags": []}
    return out


def load_catchments(data_dir: str):
    """Returns (normalised catchments, meta, source_name). Accepts the QSI nested
    two-layer file (surface = drive-time access allocation at od_share; network =
    connecting-alternative allocation at the remainder), the flat single-layer shape,
    or the 2025 partition fallback. NAMING RULE (QSI thread, 7 Aug 2026): the surface
    weights are DRIVE-TIME ACCESS ALLOCATION, not QSI capture shares - the calibrated
    QSI configuration does not transfer to this file and extracts must not claim it."""
    q = os.path.join(data_dir, QSI_FILE)
    if os.path.exists(q):
        raw = json.load(open(q))
        return _normalise(raw), raw.get("meta", {}), "qsi_drive_time"
    p = json.load(open(os.path.join(data_dir, PARTITION_FILE)))
    flat = {a: list(members) for members in p.values() for a in members}
    return _normalise(flat), {}, "partition_2025"


def headroom_to_theta(K: float, C: float, theta: float) -> float:
    if not K or K <= 0:
        return 0.0
    return max(0.0, theta * K - C)


def redistribute_overlapping(spill: dict, K: dict, C: dict, catchments: dict,
                             theta: float | None = None, weights: dict | None = None):
    """Order-free overlap-safe allocation for ONE year. `catchments` is either the
    normalised structure from load_catchments or a bare {iata: [members]} (legacy,
    optionally with `weights` = {spiller: {receiver: w}}). Each spiller's pool splits
    across its layers (od_share to surface, remainder to network); within a layer the
    offer is weight x headroom pro-rata; where several offers want the same receiver
    they scale down together to its headroom (no-cascade). Unplaced spill is
    suppressed. Returns (received, redistributed_total, suppressed_total)."""
    theta = float(get("capacity_redistribution.spill_start_threshold")) if theta is None else theta
    head = {i: headroom_to_theta(K.get(i, 0.0), C.get(i, 0.0), theta) for i in C}
    # normalise legacy call shape
    if catchments and not isinstance(next(iter(catchments.values())), dict):
        catchments = {i: {"layers": [(1.0, list(m), (weights or {}).get(i))], "penalties": {}}
                      for i, m in catchments.items()}
    desired = {}
    for s, pool in spill.items():
        if pool <= 0:
            continue
        for share, members, w in (catchments.get(s) or {}).get("layers", []):
            lp = pool * share
            if lp <= 0:
                continue
            rs = [r for r in members if r != s and head.get(r, 0.0) > 0]
            basis = {r: head[r] * float((w or {}).get(r, 1.0) if not w else (w or {}).get(r, 0.0))
                     for r in rs}
            H = sum(basis.values())
            if H <= 0:
                continue
            for r in rs:
                if basis[r] > 0:
                    desired[(s, r)] = desired.get((s, r), 0.0) + lp * basis[r] / H
    demand_r = {}
    for (s, r), v in desired.items():
        demand_r[r] = demand_r.get(r, 0.0) + v
    scale = {r: min(1.0, head[r] / d) if d > 0 else 0.0 for r, d in demand_r.items()}
    received, redistributed_by = {}, {}
    for (s, r), v in desired.items():
        got = v * scale[r]
        if got > 0:
            received[r] = received.get(r, 0.0) + got
            redistributed_by[s] = redistributed_by.get(s, 0.0) + got
    red_total = sum(redistributed_by.values())
    sup_total = sum(max(0.0, p - redistributed_by.get(s, 0.0)) for s, p in spill.items() if p > 0)
    return received, red_total, sup_total

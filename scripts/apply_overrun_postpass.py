"""apply_overrun_postpass - apply the overrun disposition + catchment-spill join to the
EXISTING capacity_layer_extract.json (spot years), so the published data carries the
steer (7 Aug 2026) without a full workstation re-run. The next native run of
run_capacity_layer.py produces the identical result from source; this script is the
bridge, not the method. Idempotent. Author: Avia Solutions."""
from __future__ import annotations
import json, os, sys
from types import SimpleNamespace as NS

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from avia_forecast.io_safe import dump_atomic
from avia_forecast.capacity import overrun
from avia_forecast.capacity import spill as spill_mod
from avia_forecast.config import get

BASE = "2025"
p = os.path.join(REPO, "data", "capacity_layer_extract.json")
ext = json.load(open(p))
share = float(get("capacity_overrun.soft_spill_share"))
theta = float(get("capacity_redistribution.spill_start_threshold"))

# ---- overrun pass (spot years; JSON keys are strings) ----
info_all = {}
for iata, a in ext["airports"].items():
    if a["knowledge_state"] != "constrained_evidenced":
        continue
    U = {int(y): v for y, v in (a.get("unconstrained_m") or {}).items()}
    K = {int(y): v for y, v in (a.get("capacity_m") or {}).items()}
    if not overrun.is_overrun(U.get(2025), K.get(2025)):
        continue
    sp, con, over = overrun.soft_paths(U, K, 2025, share)
    f = overrun.finding(iata, U[2025], K[2025], share)
    a["knowledge_state"] = overrun.STATE
    a["spill_m"] = {str(y): round(v, 3) for y, v in sp.items()}
    a["constrained_m"] = {str(y): round(v, 2) for y, v in con.items()}
    a["statement"] = f + " Register record: " + (a.get("statement") or "")
    a["overrun"] = {"observed_base_m": round(U[2025], 2), "rated_m": round(K[2025], 2),
                    "overrun_base_m": round(U[2025] - K[2025], 2),
                    "soft_spill_share": share, "hard_cap": "none held",
                    "overrun_above_rated_m": {str(y): round(v, 2) for y, v in over.items()},
                    "finding": f}
    info_all[iata] = a["overrun"]

# ---- catchment-spill join at spot years ----
from avia_forecast.capacity import catchment_join as cj
catchments, cat_meta, cat_source = cj.load_catchments(os.path.join(REPO, "data"))
print(f"catchment source: {cat_source}")
spots = sorted({int(y) for a in ext["airports"].values() for y in (a.get("spill_m") or {})})
redist = {}
c6_bad, c7_bad = [], []
for y in spots:
    Kd, Cd, Ed = {}, {}, {}
    for i, a in ext["airports"].items():
        U = (a.get("unconstrained_m") or {}).get(str(y), 0.0) or 0.0
        Cd[i] = (a.get("constrained_m") or {}).get(str(y), U) or U
        Kd[i] = (a.get("capacity_m") or {}).get(str(y), 0.0) or 0.0
        Ed[i] = (a.get("spill_m") or {}).get(str(y), 0.0) or 0.0
    received_y, red_total, sup_total = cj.redistribute_overlapping(Ed, Kd, Cd, catchments, theta)
    for i, rec_v in received_y.items():
        ext["airports"][i].setdefault("received_m", {})[str(y)] = round(rec_v, 3)
        if rec_v > cj.headroom_to_theta(Kd[i], Cd[i], theta) + 1e-6:
            c7_bad.append((i, y))
    pool = sum(v for v in Ed.values() if v > 0)
    if abs(pool - (red_total + sup_total)) > 1e-6:
        c6_bad.append(("year", y))
    redist[str(y)] = {"spill_m": round(pool, 3), "redistributed_m": round(red_total, 3),
                      "suppressed_m": round(sup_total, 3)}

# ---- meta, requirement, checks ----
ext["redistribution_m"] = redist
ext["capacity_requirement_m"] = {str(y): round(sum(
    (a.get("spill_m") or {}).get(str(y), 0.0) or 0.0 for a in ext["airports"].values()), 2)
    for y in spots}
states = {}
for a in ext["airports"].values():
    states[a["knowledge_state"]] = states.get(a["knowledge_state"], 0) + 1
ext["meta"]["states"].update({"constrained_evidenced": states.get("constrained_evidenced", 0),
                              "constraint_overrun_observed": states.get(overrun.STATE, 0),
                              "constraint_known_not_quantified": states.get("constraint_known_not_quantified", 0),
                              "unconstrained": states.get("unconstrained", 0)})
ext["meta"]["overrun_rule"] = ("soft spill on growth above observed base "
                               "(config capacity_overrun, PROVISIONAL per steer 7 Aug 2026)")
req0 = ext["capacity_requirement_m"].get(BASE, 0.0)
new_checks = [
    {"check": "C2 base-year requirement zero after overrun accounting", "pass": req0 < 0.05,
     "detail": f"{req0:.2f}m"},
    {"check": "C6 spill conservation", "pass": not c6_bad,
     "detail": f"{len(c6_bad)} violations" if c6_bad else f"exact across {len(spots)} spot years"},
    {"check": "C7 no receiver past its spill-start threshold", "pass": not c7_bad,
     "detail": f"{len(c7_bad)} violations" if c7_bad else "exact"},
]
kept = [c for c in ext.get("checks", []) if not c["check"].startswith(("C2", "C6", "C7"))]
ext["checks"] = kept + new_checks

dump_atomic(ext, p, indent=1)
print(f"overrun reclassified: {sorted(info_all)} (share {share:.0%}, PROVISIONAL)")
print("capacity_requirement_m:", ext["capacity_requirement_m"])
print("redistribution:", {k: v for k, v in list(redist.items())[:3]}, "...")
for c in ext["checks"]:
    print(f"  {'PASS' if c['pass'] else 'FAIL'}  {c['check']}: {c['detail']}")
if all(c["pass"] for c in ext["checks"]):
    print("ALL CHECKS PASS - extract publishable")

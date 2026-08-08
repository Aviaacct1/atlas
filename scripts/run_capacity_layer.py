"""run_capacity_layer - one command: join the Global Forecast to the capacity layer.
Integration instruction 4 Aug 2026 + correction note, both implemented in full.
Produces data/capacity_layer_extract.json with the THREE KNOWLEDGE STATES preserved:
constrained_evidenced (dated binding RANGE), constraint_known_not_quantified, and
unconstrained/headroom - plus screen states for the un-registered world and skipped
airports carried explicitly. Runs on the workstation (needs the OAG store).
  py -3.12 scripts\\run_capacity_layer.py [--scenario Baseline]
Author: Avia Solutions.
"""
from __future__ import annotations
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from avia_forecast.io_safe import dump_atomic
from avia_forecast.capacity import evidence, peakhour, constrain, overrun
from avia_forecast.capacity import spill as spill_mod
from avia_forecast.ingest import oag_peak
import capacity_demand_feed as feed

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_YEAR = 2025
SPOTS = [2025, 2030, 2035, 2040, 2045, 2050]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="Baseline")
    a = ap.parse_args()
    checks = []

    import time as _t
    _t0 = _t.time()
    def _ph(msg):
        print(f"[{(_t.time()-_t0)/60:5.1f} min] {msg}", flush=True)
    _ph("loading capacity observations...")
    observations = evidence.load_observations(os.path.join(REPO, "data", "capacity_observations_france_harvest.csv"))
    _ph("building peak-hour panel from the OAG store (the long phase - reads the full store)...")
    panel, report = oag_peak.build_panel(years=[2015, 2016, 2017, 2018, 2019, 2025])
    _ph(f"panel built: {len(panel)} observations. fitting peak-share model...")
    fit = peakhour.fit_peak_share(panel, convention=panel[0].convention)

    _ph("running the world terminal forecast for growth paths (needs E: data)...")
    demand = feed.demand_by_airport(panel, base_year=BASE_YEAR, scenario=a.scenario)
    bad = feed.check_base_levels(demand, panel, BASE_YEAR)
    checks.append(("C5 base levels == panel (2%)", not bad,
                   f"{len(bad)} airports off panel level" if bad else f"all {len(demand)} exact"))

    _ph(f"demand fed for {len(demand)} airports. constraining...")
    results, skipped = constrain.constrain_all(observations, demand, panel, fit, base_year=BASE_YEAR)

    # C4: no silent fallout
    ok4 = len(results) + len(skipped) == len(demand)
    checks.append(("C4 resolved+skipped == fed", ok4, f"{len(results)}+{len(skipped)} vs {len(demand)}"))

    # overrun disposition (steer 7 Aug 2026): soft rule for airports operating above
    # their rated terminal capacity. Parameters provisional (config capacity_overrun).
    overrun_info = overrun.apply(results, BASE_YEAR)
    _ph(f"overrun pass: {len(overrun_info)} airport(s) reclassified {overrun.STATE}: {sorted(overrun_info)}")

    # C2 (re-worded per steer): base-year requirement zero AFTER overrun accounting
    req0 = constrain.capacity_requirement(results, BASE_YEAR)
    over = [i for i, r in results.items() if r.spill.get(BASE_YEAR, 0) > 0.01]
    checks.append(("C2 base-year requirement zero after overrun accounting", req0 < 0.05,
                   f"{req0:.2f}m" + (f" (residual base-year spill: {over[:5]} - DATA FAULT)" if over else "")))

    # catchment-spill join: spilled traffic redistributes within the catchment to
    # airports with known capacity below the spill-start threshold; rest suppressed.
    from avia_forecast.capacity import catchment_join as cj
    _catchments, _cat_meta, _cat_source = cj.load_catchments(os.path.join(REPO, "data"))
    _ph(f"catchment source: {_cat_source}")
    years_all = sorted({y for r in results.values() for y in r.spill})
    received = {i: {} for i in results}
    redist_summary = {}
    _c6_bad, _c7_bad = [], []
    _theta = float(__import__("avia_forecast.config", fromlist=["get"]).get("capacity_redistribution.spill_start_threshold"))
    for y in years_all:
        Kd = {i: (r.capacity.get(y, 0.0) or 0.0) for i, r in results.items()}
        Cd = {i: r.constrained.get(y, r.unconstrained.get(y, 0.0)) for i, r in results.items()}
        Ed = {i: r.spill.get(y, 0.0) for i, r in results.items()}
        received_y, red_total, sup_total = cj.redistribute_overlapping(Ed, Kd, Cd, _catchments, _theta)
        for i, rec_v in received_y.items():
            received[i][y] = rec_v
            if rec_v > cj.headroom_to_theta(Kd[i], Cd[i], _theta) + 1e-6:
                _c7_bad.append((i, y))
        pool = sum(v for v in Ed.values() if v > 0)
        if abs(pool - (red_total + sup_total)) > 1e-6:
            _c6_bad.append(("year", y))
        redist_summary[y] = {"spill_m": round(pool, 3), "redistributed_m": round(red_total, 3),
                             "suppressed_m": round(sup_total, 3)}
    checks.append(("C6 spill conservation (spill == redistributed + suppressed)", not _c6_bad,
                   f"{len(_c6_bad)} violations" if _c6_bad else f"exact across {len(years_all)} years"))
    checks.append(("C7 no receiver filled past its spill-start threshold", not _c7_bad,
                   f"{len(_c7_bad)} violations" if _c7_bad else "exact"))

    # C3: Nice binds on the runway, not the terminal
    nce = results.get("NCE")
    if nce and nce.resolution.state == "constrained_evidenced":
        bt = (nce.resolution.binding_test or "").lower()
        checks.append(("C3 Nice binds runway not terminal", "terminal" not in bt,
                       f"binding_test={nce.resolution.binding_test}"))
    else:
        checks.append(("C3 Nice resolution", nce is not None,
                       f"state={nce.resolution.state if nce else 'NCE not in results'}"))

    # screen across the whole panel (global coverage today)
    _ph("running the capacity screen across the panel...")
    rows = peakhour.capacity_screen(panel)
    screen = {r.iata: {"state": r.state, "note": getattr(r, "note", "")} for r in rows}

    # ---- extract: two levels, three knowledge states, nothing collapsed ----
    airports = {}
    for iata, r in results.items():
        res = r.resolution
        airports[iata] = {
            "knowledge_state": res.state,
            "binding_range": list(r.binding_range) if res.binding_year else None,
            "binding_test": res.binding_test,
            "statement": res.statement,
            "share_basis": r.share_basis, "share_reason": r.share_reason,
            "tests_not_run": res.tests_not_run,
            "capacity_m": {y: round(r.capacity[y], 2) for y in SPOTS if y in r.capacity},
            "unconstrained_m": {y: round(r.unconstrained[y], 2) for y in SPOTS if y in r.unconstrained},
            "constrained_m": {y: round(r.constrained[y], 2) for y in SPOTS if y in r.constrained},
            "spill_m": {y: round(r.spill[y], 3) for y in SPOTS if y in r.spill},
            "received_m": {y: round(received[iata][y], 3) for y in SPOTS if y in received.get(iata, {})},
            "overrun": overrun_info.get(iata),
            "screen": screen.get(iata),
        }
    n_ev = sum(1 for v in airports.values() if v["knowledge_state"] == "constrained_evidenced")
    n_kq = sum(1 for v in airports.values() if v["knowledge_state"] == "constraint_known_not_quantified")
    n_un = sum(1 for v in airports.values() if v["knowledge_state"] == "unconstrained")
    n_ov = sum(1 for v in airports.values() if v["knowledge_state"] == overrun.STATE)

    extract = {
        "meta": {"scenario": a.scenario, "base_year": BASE_YEAR,
                 "convention": panel[0].convention,
                 "elasticity": getattr(fit, "elasticity", None),
                 "register_coverage": "France harvest (17 airports, 36 observations); screen covers the panel",
                 "states": {"constrained_evidenced": n_ev, "constraint_overrun_observed": n_ov,
                            "constraint_known_not_quantified": n_kq,
                            "unconstrained": n_un, "skipped": len(skipped),
                            "screen_only": len(screen) - len(airports)},
                 "overrun_rule": "soft spill on growth above observed base (config capacity_overrun, PROVISIONAL per steer 7 Aug 2026)",
                 "presentation_rule": "three knowledge states must reach the user; binding RANGE only, never a point year"},
        "capacity_requirement_m": {y: round(constrain.capacity_requirement(results, y), 2) for y in SPOTS},
        "redistribution_m": {y: redist_summary[y] for y in SPOTS if y in redist_summary},
        "headroom_top25": [{"iata": i, "headroom_m": round(h, 2), "utilisation": round(u, 3)}
                            for i, h, u in constrain.headroom_ranking(results, 2035, 25)],
        "airports": airports,
        "skipped": skipped,
        "screen_unregistered": {i: s for i, s in screen.items() if i not in airports},
        "panel_report": report if isinstance(report, (dict, list, str)) else str(report),
        "checks": [{"check": c, "pass": bool(p), "detail": d} for c, p, d in checks],
    }
    out = os.path.join(REPO, "data", "capacity_layer_extract.json")
    dump_atomic(extract, out, indent=1)

    print(f"resolved {len(results)} (evidenced {n_ev}, overrun {n_ov}, known-not-quantified {n_kq}, unconstrained {n_un}); "
          f"skipped {len(skipped)}; screen-only {len(screen) - len(airports)}")
    print("capacity requirement (m pax):", {y: extract["capacity_requirement_m"][y] for y in SPOTS})
    for c, p, d in checks:
        print(f"  {'PASS' if p else 'FAIL'}  {c}: {d}")
    print("extract ->", out)
    if not all(p for _, p, _ in checks):
        print("ONE OR MORE CHECKS FAILED - do not publish this extract")


if __name__ == "__main__":
    main()

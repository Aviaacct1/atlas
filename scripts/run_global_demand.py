"""Run the Phase 3a global unconstrained demand forecast and write the extract +
a coherence read against an external OEM reference. Author: Avia Solutions."""
from __future__ import annotations
from avia_forecast.io_safe import dump_atomic
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from avia_forecast import global_demand as gd            # noqa: E402
from avia_forecast.coherence import coherence as co      # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
# External reference: Boeing CMO / Airbus GMF quote circa 3.6-4.0% RPK/yr to 2043; O&D
# passenger growth runs a little below RPK (stage-length mix). Reporting only [P1].
OEM_PAX_CAGR = 0.036


def run(scenario="Baseline"):
    r = gd.run_global(scenario=scenario)
    spots = [2025, 2030, 2035, 2040, 2045, 2050]
    extract = {
        "scenario": scenario, "base_year": r.years[0], "horizon": r.years[-1],
        "n_airports": r.meta["n_airports"], "propensity": r.meta["propensity"],
        "world_od_m": {str(y): round(r.world[y], 1) for y in spots},
        "world_cagr": round(r.world_cagr, 4),
        "by_region_m": {reg: {str(y): round(s[y], 1) for y in spots}
                        for reg, s in r.by_region.items()},
        "assumptions": "regional GDP growth [P1]; shared segment fare index [P1]; "
                       "propensity where population known; O&D only (no connecting/constraint)",
    }
    dump_atomic(extract, os.path.join(DATA, "global_forecast_2025_2050.json"), indent=2)

    div = co.external_divergence(r.world, OEM_PAX_CAGR, goal_band_pp=0.5)
    coh = co.check_rolling_cagr(r.world)
    print(f"WORLD O&D  2025 {r.world[2025]:,.0f}m -> 2050 {r.world[2050]:,.0f}m  CAGR {r.world_cagr*100:.2f}%")
    print(f"coherence: rolling-decade CAGR flags = {len(coh.flags)} (band ok = {coh.ok})")
    print(f"vs OEM pax reference {OEM_PAX_CAGR*100:.1f}%: gap {div.gap_pp:+.2f}pp "
          f"(within 0.5pp goal band = {div.within_goal}) [reporting only]")
    print("by region (2025 -> 2050, m):")
    for reg, s in sorted(r.by_region.items(), key=lambda kv: -kv[1][2050]):
        cg = (s[2050] / s[2025]) ** (1/25) - 1
        print(f"  {reg:<15} {s[2025]:>7,.0f} -> {s[2050]:>7,.0f}   {cg*100:.2f}%/yr")
    return extract


if __name__ == "__main__":
    run()

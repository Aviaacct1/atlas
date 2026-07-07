"""Run the Phase 3b global terminal-passenger forecast (with transfers) and write the
extract + a coherence read against the ACI World Airport Traffic Forecast. Author: Avia Solutions."""
from __future__ import annotations
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from avia_forecast.paths import DATA, OEF_DIR, ACI_DIR, ACI_DECRYPT, SABRE_DB, OAG_DB, QSI_REF, PREAGG, QSI_APP, OEF_GDP_XLSX
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from avia_forecast import global_terminal as gt          # noqa: E402
from avia_forecast.coherence import coherence as co       # noqa: E402

DATA = DATA
ACI_FORECAST_CAGR = 0.034     # ACI World Airport Traffic Forecasts 2025-2054, 3.4% [reporting]


def run(scenario="Baseline"):
    r = gt.run_terminal(scenario=scenario)
    spots = [y for y in (2025, 2030, 2035, 2040, 2045, 2050) if y in r.world]
    extract = {
        "scenario": scenario, "base_anchor": r.meta["base_anchor"], "n_airports": r.meta["n_airports"],
        "world_terminal_m": {str(y): round(r.world[y], 1) for y in spots},
        "world_cagr": round(r.world_cagr, 4),
        "by_region_terminal_m": {reg: {str(y): round(s[y], 1) for y in spots} for reg, s in r.by_region.items()},
        "note": "terminal pax incl transfers; connecting grown on ACI 2024 base split (terminal-vs-Sabre O&D); "
                "region-based connecting v1, per-hub M matrix is the next refinement",
    }
    json.dump(extract, open(os.path.join(DATA, "global_terminal_2024_2050.json"), "w"), indent=2)
    div = co.external_divergence(r.world, ACI_FORECAST_CAGR, goal_band_pp=0.5)
    print(f"WORLD TERMINAL  base {r.world[r.years[0]]:,.0f}m -> 2050 {r.world[2050]:,.0f}m  CAGR {r.world_cagr*100:.2f}%")
    print(f"vs ACI forecast {ACI_FORECAST_CAGR*100:.1f}%: gap {div.gap_pp:+.2f}pp (within goal band {div.within_goal})")
    return extract


if __name__ == "__main__":
    run()

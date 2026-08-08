"""One command: run the Method Spec 9 backtest at scale over the ACI panel + OEF GDP and write the
published error exhibit (data/backtest_exhibit.json). Author: Avia Solutions."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from avia_forecast.paths import DATA
from avia_forecast.io_safe import dump_atomic
from avia_forecast.backtest.at_scale import run_scale

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    panel = json.load(open(os.path.join(DATA, "aci_panel_long.json")))
    oef = json.load(open(os.path.join(DATA, "oef_gdp_pop_by_iso2.json")))
    gdp = (oef.get("gdp") if isinstance(oef, dict) else None) or {}
    exhibit, rows = run_scale(panel, gdp, base_year=2014, score_years=(2019, 2024))
    out = os.path.join(REPO, "data", "backtest_exhibit.json")
    dump_atomic(exhibit, out, indent=1)
    for sy, s in exhibit["summary"].items():
        print(f"{sy}: n={s['n']}  WMAPE model {s['wmape_model']*100:.1f}% vs naive {s['wmape_naive']*100:.1f}%"
              f"  | median|err| {s['median_ape_model']*100:.1f}%  | wbias {s['wbias_model']*100:+.1f}%"
              f"  | beats naive (WMAPE) {s['beats_naive_wmape']}")
    print("exhibit ->", out)


if __name__ == "__main__":
    main()

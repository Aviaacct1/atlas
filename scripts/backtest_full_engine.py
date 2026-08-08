"""One command: full-engine forward backtest at country scale over ACI + OEF GDP + population.
Writes data/backtest_full_engine_exhibit.json. Author: Avia Solutions."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from avia_forecast.paths import DATA
from avia_forecast.io_safe import dump_atomic
from avia_forecast.backtest.full_engine import run_full_engine

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    oef = json.load(open(os.path.join(DATA, "oef_gdp_pop_by_iso2.json")))
    panel = json.load(open(os.path.join(DATA, "aci_panel_long.json")))
    ex, rows = run_full_engine(panel, oef.get("gdp", {}), oef.get("pop", {}))
    dump_atomic(ex, os.path.join(REPO, "data", "backtest_full_engine_exhibit.json"), indent=1)
    for sy, s in ex["summary"].items():
        print(f"{sy}: n={s['n']}  WMAPE engine {s['wmape_model']*100:.1f}% vs naive {s['wmape_naive']*100:.1f}%"
              f"  | wbias {s['wbias_model']*100:+.1f}%  | beats naive {s['beats_naive_wmape']}")


if __name__ == "__main__":
    main()

r"""Which published files are older than what they are built from, and which have no
builder at all. Author: Avia Solutions.

Two failures this guards against, both of which have happened.

A STALE SERVED FILE. Every file in webapp/data is written by the build. One left behind
when the forecast moves is served to a client next to figures it disagrees with. Meridian
released early off exactly that on 8 August 2026.

A FILE NOTHING PRODUCES. `aci_hub_calibration_2024.json`, which the whole terminal
forecast is anchored to, had no builder in the tree until 9 August 2026. It could not be
rebuilt when its inputs moved, nobody could say how it had been made, and 189 airports
carrying 544.0m passengers stayed out of it for a year. A file with no builder is not a
data file, it is a fossil.

This is a report, not a gate: a file can legitimately be older than its input where the
input did not change anything it uses. Read it before a release, and be able to say why
each line is acceptable.

Usage:  py -3.12 scripts\check_freshness.py [--fail-on-stale]
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from avia_forecast import paths  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# what each published file is built from, and by what
CHAIN = [
    ("webapp/data/dashboard.json", "scripts/build_dashboard_data.py",
     ["E:aci_hub_calibration_2024.json", "E:aci_panel_long.json", "E:oef_gdp_pop_by_iso2.json",
      "data/global_base_od_2025.json", "data/worldbank_pop_gdppc.json",
      "data/airport_regress.json", "config/assumptions_book.yaml"]),
    ("webapp/data/cockpit.json", "scripts/build_cockpit_data.py",
     ["E:aci_hub_calibration_2024.json", "data/airport_regress.json",
      "config/assumptions_book.yaml"]),
    ("webapp/data/world.json", "scripts/build_webapp_data.py",
     ["E:aci_hub_calibration_2024.json", "config/assumptions_book.yaml"]),
    ("webapp/data/airports.json", "scripts/build_webapp_data.py",
     ["E:aci_hub_calibration_2024.json", "config/assumptions_book.yaml"]),
    ("webapp/data/meta.json", "scripts/build_webapp_data.py", ["config/assumptions_book.yaml"]),
    ("webapp/data/capacity.json", "scripts/build_capacity_webapp_data.py",
     ["webapp/data/dashboard.json", "config/assumptions_book.yaml"]),
    ("webapp/data/bum_candidates.json", "scripts/build_bum_candidates.py",
     ["webapp/data/dashboard.json"]),
    ("webapp/data/history.json", "webapp/build_history.py", []),
    ("data/global_forecast_2025_2050.json", "scripts/run_global_demand.py",
     ["data/global_base_od_2025.json", "data/worldbank_pop_gdppc.json",
      "config/assumptions_book.yaml"]),
    ("data/airport_regress.json", "scripts/estimate_airport_diagnostics.py",
     ["E:aci_panel_long.json", "E:oef_gdp_pop_by_iso2.json"]),
    ("E:aci_hub_calibration_2024.json", "scripts/build_aci_hub_calibration.py",
     ["E:aci_panel_2013_2024.json"]),
    ("E:aci_panel_long.json", "scripts/build_aci_long_panel.py", ["E:aci_panel_2013_2024.json"]),
    ("E:aci_panel_2013_2024.json", "scripts/ingest_aci.py", []),
    ("E:regions_boeing.json", "scripts/compare_regions_boeing.py",
     ["webapp/data/dashboard.json", "config/stage_length.yaml", "config/comparators.yaml"]),
    ("E:gap_decomposition.json", "scripts/gap_decomposition.py", ["E:regions_boeing.json"]),
    ("E:journey_length_history.json", "scripts/journey_length_history.py", []),
    ("E:fleet_wedge.json", "scripts/build_fleet_wedge.py", []),
    ("E:regional_defence.json", "scripts/regional_defence.py",
     ["data/global_base_od_2025.json", "config/assumptions_book.yaml"]),
    ("E:ogf_deck_data.json", "scripts/build_ogf_deck_data.py", []),
    ("E:oag_final_to_next_M.json", "scripts/build_oag_final_to_next_M.py", []),
    ("E:oef_gdp_pop_by_iso2.json", "scripts/ingest_oef_gdp.py", []),
    ("E:estimated_bG_by_country.json", "scripts/estimate_country_bG.py",
     ["E:aci_panel_long.json"]),
    ("data/worldbank_pop_gdppc.json", "scripts/ingest_worldbank.py", []),
    ("data/fare_index_constructed.json", "scripts/build_fare_index.py", []),
]


def resolve(name):
    return os.path.join(paths.DATA, name[2:]) if name.startswith("E:") \
        else os.path.join(REPO, name)


def mtime(path):
    return os.path.getmtime(path) if os.path.exists(path) else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fail-on-stale", action="store_true")
    a = ap.parse_args(argv)

    print("Freshness of every published and staged file, against what it is built from")
    print(f"Data root: {paths.DATA}\n")
    print(f"{'file':<44}{'written':<18}{'builder':<44}state")
    stale, orphan, missing = [], [], []
    for name, builder, inputs in CHAIN:
        p = resolve(name)
        t = mtime(p)
        if t is None:
            missing.append(name)
            print(f"{name:<44}{'ABSENT':<18}{str(builder or 'none'):<44}missing")
            continue
        older = []
        for i in inputs:
            ti = mtime(resolve(i))
            if ti and ti > t + 1:
                older.append(i)
        if builder is None:
            orphan.append(name)
            state = "NO BUILDER"
        elif older:
            stale.append((name, older))
            state = "older than " + ", ".join(os.path.basename(x) for x in older[:3])
        else:
            state = "ok"
        print(f"{name:<44}{datetime.fromtimestamp(t).strftime('%d %b %H:%M'):<18}"
              f"{str(builder or 'none'):<44}{state}")

    print()
    if orphan:
        print(f"NO BUILDER, {len(orphan)}: " + ", ".join(orphan))
        print("  A file the engine reads and nothing produces cannot be rebuilt when its "
              "inputs move.")
    if stale:
        print(f"OLDER THAN AN INPUT, {len(stale)}:")
        for name, older in stale:
            print(f"  {name} is older than {', '.join(older)}")
        print("  Re-run the builder, or be able to say why the input did not change "
              "anything this file uses.")
    if missing:
        print(f"ABSENT, {len(missing)}: " + ", ".join(missing))
    if not (orphan or stale or missing):
        print("Everything is at least as new as what it is built from.")
    return 1 if (a.fail_on_stale and stale) else 0


if __name__ == "__main__":
    raise SystemExit(main())

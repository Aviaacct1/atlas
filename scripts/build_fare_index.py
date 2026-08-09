r"""Regenerate data/fare_index_constructed.json from the jet fuel series.

Why this exists. The fare index the forecast reads was a static file dated 6 July 2026
that nothing in the tree regenerated. estimate/fare_construction.py held the routine that
builds it and was imported by nothing, and data/jet_fuel_eia.json held the fuel series and
was read by nothing. So fare_index.pass_through_theta and fare_index.real_yield_trend_tau
sat in the assumptions book, were read in two places that nothing called, and changing
either changed no number the product reported. Found 8 August 2026, wired 9 August 2026.

    python scripts/build_fare_index.py --check     report what would change, write nothing
    python scripts/build_fare_index.py --write     regenerate the index

--check is the default, deliberately. Regenerating the index moves the forecast, so it is
an act, not a side effect of running a script.

Method (Method Spec 4.2, G1 recipe). Real fares evolve by cost pass-through plus a
structural real-yield trend:

    F(s,t) = F(s,t-1) x (1 + theta x dUC(s,t)) x (1 + tau)

dUC is the year-on-year unit-cost change from fuel, weighted by each segment's fuel share
and net of the fleet-efficiency path. Fuel is real, EIA via Jess Rowden's workbook.
Absolute levels (F15) remain a data-sourcing item; this builds an index, base year = 100.

Author: Avia Solutions.
"""
from __future__ import annotations
import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from avia_forecast.config import get
from avia_forecast.estimate.fare_construction import build_fare_index, FUEL_SHARE
from avia_forecast.io_safe import dump_atomic

REPO_DATA = os.path.join(REPO, "data")
FUEL = os.path.join(REPO_DATA, "jet_fuel_eia.json")
OUT = os.path.join(REPO_DATA, "fare_index_constructed.json")


def load_fuel() -> dict:
    if not os.path.isfile(FUEL):
        raise FileNotFoundError(
            f"jet fuel series not found at {FUEL}. Without it the fare index cannot be "
            f"rebuilt and the shipped index stands. It is EIA jet fuel, real, by year.")
    raw = json.load(open(FUEL))
    fuel = {int(k): float(v) for k, v in raw.items() if str(k).isdigit() and v}
    if not fuel:
        raise ValueError(f"{FUEL} parsed to no usable year and price pairs.")
    return fuel


def build(years, efficiency_gain: float) -> dict:
    fuel = load_fuel()
    idx = build_fare_index(fuel, years, efficiency_gain=efficiency_gain)
    # rebase every segment to the first year = 100, which is the contract the readers
    # (fixtures.fare_index and global_demand._fare_index) expect
    out = {}
    for seg, s in idx.items():
        b = s[years[0]]
        out[seg] = {str(y): round(s[y] / b * 100.0, 3) for y in years}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="write the index. Default is a check that writes nothing.")
    ap.add_argument("--efficiency-gain", type=float, default=0.015,
                    help="annual fleet fuel-efficiency gain, netted off the fuel change")
    a = ap.parse_args()

    theta = get("fare_index.pass_through_theta")
    tau = get("fare_index.real_yield_trend_tau")
    if theta is None or tau is None:
        raise SystemExit("fare_index.pass_through_theta or real_yield_trend_tau is absent "
                         "from config/assumptions_book.yaml.")

    fuel = load_fuel()
    fy = sorted(fuel)
    old = json.load(open(OUT)) if os.path.isfile(OUT) else {}
    years = sorted(int(y) for y in next(iter(old.values()))) if old else list(range(fy[0], fy[-1] + 1))

    print(f"fuel series : {FUEL}")
    print(f"              {fy[0]} to {fy[-1]}, {len(fy)} years")
    print(f"assumptions : theta {theta}, tau {tau}, efficiency gain {a.efficiency_gain}")
    print(f"horizon     : {years[0]} to {years[-1]}, from the shipped index" if old else
          f"horizon     : {years[0]} to {years[-1]}, from the fuel series")

    new = build(years, a.efficiency_gain)

    if old:
        print("\nchange against the shipped index, by segment:")
        print(f"  {'segment':<28}{'shipped end':>13}{'rebuilt end':>13}{'change':>10}")
        for seg in sorted(new):
            if seg not in old:
                print(f"  {seg:<28}{'absent':>13}{new[seg][str(years[-1])]:>13.1f}{'new':>10}")
                continue
            o = float(old[seg].get(str(years[-1]), 0) or 0)
            n = float(new[seg][str(years[-1])])
            print(f"  {seg:<28}{o:>13.1f}{n:>13.1f}{(n/o-1) if o else 0:>+9.1%}")
        gaps = [y for y in years if y not in fuel]
        if gaps:
            print(f"\n  NOTE: {len(gaps)} horizon years have no fuel price "
                  f"({gaps[0]} to {gaps[-1]}); the index holds flat across those, so the "
                  f"forward path is the real-yield trend alone. Stage a jet fuel outlook "
                  f"to give the forward years a cost signal.")

    if not a.write:
        print("\nNothing written. Add --write to regenerate. Regenerating moves the forecast: "
              "re-run scripts/build_dashboard_data.py and the other webapp builders after.")
        return

    dump_atomic(new, OUT, indent=1)
    print(f"\nwritten: {OUT}")
    print("Now re-run the webapp builders, and record the move in CHANGELOG.md.")


if __name__ == "__main__":
    main()

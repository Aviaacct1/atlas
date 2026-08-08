"""capacity_demand_feed - the forecast side of the capacity-layer join.
CORRECTED per the capacity thread's note (4 Aug): LEVEL from the panel (schedule-basis
throughput, mppa), GROWTH from the forecast. Feeding forecast levels directly, whether
O&D or ACI-anchored terminal, breaks share_path silently because the projection anchors
on the panel's own annual_pax_m and works from the demand/base RATIO; the base-year
ratio must be exactly 1.0. Author: Avia Solutions.
"""
from __future__ import annotations
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def demand_by_airport(panel, base_year: int = 2025, scenario: str = "Baseline"):
    """{iata: {year: m pax}} - panel throughput level x forecast growth index.

    Growth comes from run_terminal's per-airport series (throughput-shaped growth,
    connecting included); the level is discarded in favour of the panel's, by design:
    the capacity comparison is peak-vs-declared-rate and both sides must be on the
    schedule basis. Airports in the panel but absent from the forecast keep base level
    flat is NOT done - they are simply absent, and constrain_all's skipped accounting
    plus the driver's no-silent-fallout check own the difference."""
    from avia_forecast.global_terminal import run_terminal
    base = {o.iata: o.annual_pax_m for o in panel if o.year == base_year}
    t = run_terminal(scenario=scenario)
    out = {}
    for iata, rec in t.by_airport.items():
        if iata not in base:
            continue
        series = dict(zip(t.years, rec["series"]))
        b = series.get(base_year)
        if not b or b <= 0:
            continue
        out[iata] = {y: base[iata] * (v / b) for y, v in series.items()}
    return out


def check_base_levels(demand, panel, base_year: int = 2025, tol: float = 0.02):
    """The fifth executable check: every base-year demand within tol of the panel's
    annual_pax_m. Catches the entire unit/basis error class. Returns list of failures."""
    base = {o.iata: o.annual_pax_m for o in panel if o.year == base_year}
    bad = []
    for iata, path in demand.items():
        want = base.get(iata)
        got = path.get(base_year)
        if want and got and abs(got - want) / want > tol:
            bad.append((iata, got, want))
    return bad

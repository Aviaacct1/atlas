"""outputs/impact - the impact table (Cockpit build update F1).

Every run/edit produces the impact table: the passenger, ATM, cargo and capacity
rows at six spot years (BY .. BY+25 step 5), three period CAGRs, and a signed
vs-engine-baseline row per metric. Author: Avia Solutions.
"""
from __future__ import annotations

ROWS = ["total_pax", "int_pax", "dom_pax", "transfer_pax", "od_pax", "departing_pax",
        "ga_pax", "commercial_atm", "cargo_tonnage", "cargo_atm", "ga_atm", "total_atm",
        "unconstrained", "cap_requirement", "ddfs"]


def spot_years(base_year, step=5, n=6):
    return [base_year + step * i for i in range(n)]


def default_cagr_periods(base_year):
    return [(base_year, base_year + 5), (base_year + 5, base_year + 15), (base_year + 15, base_year + 25)]


def _cagr(series, a, b):
    va, vb = series.get(a), series.get(b)
    if not va or vb is None or b == a:
        return None
    return (vb / va) ** (1.0 / (b - a)) - 1.0


def build_impact_table(run: dict, base_year: int, baseline: dict | None = None,
                       rows=None, step=5) -> dict:
    """run/baseline: {metric: {year: value}}. Returns per-metric spot values, the
    three period CAGRs, and the signed vs-baseline row (run - baseline)."""
    rows = rows or ROWS
    sy = spot_years(base_year, step)
    periods = default_cagr_periods(base_year)
    table = {"base_year": base_year, "spot_years": sy, "cagr_periods": periods, "metrics": {}}
    for m in rows:
        s = run.get(m, {})
        entry = {"spot": {y: s.get(y) for y in sy},
                 "cagr": {f"{a}-{b}": _cagr(s, a, b) for a, b in periods}}
        if baseline is not None:
            bl = baseline.get(m, {})
            entry["vs_baseline"] = {y: (s.get(y, 0.0) - bl.get(y, 0.0)) for y in sy}
        table["metrics"][m] = entry
    return table

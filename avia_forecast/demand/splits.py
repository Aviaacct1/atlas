"""demand/splits - segment output splits (Cockpit build update B2).

Total demand is split into domestic and international so that domestic takes a
lower share of the excess growth (the amount above a common floor): domestic's
excess = domestic_excess_factor x international's excess. The split preserves
domestic + international = total exactly. The transfer/O&D split follows the hub
overlay, and transfer + O&D = total. Both adding-up identities are build-stopping.
Author: Avia Solutions.
"""
from __future__ import annotations
import numpy as np

from ..config import get
from ..aggregate.reconcile import ReconciliationError


def split_domestic_international(total: dict, base_domestic: float, base_international: float,
                                years, floor_rate=None, dom_factor=None):
    """Split a total-demand path into domestic and international paths.

    international grows at floor + e; domestic at floor + factor*e, with e solved so
    that domestic + international equals the target total every year (exact)."""
    floor = get("segment_splits.floor_rate") if floor_rate is None else floor_rate
    factor = get("segment_splits.domestic_excess_factor") if dom_factor is None else dom_factor
    y0 = years[0]
    dom = {y0: base_domestic}
    intl = {y0: base_international}
    for prev, y in zip(years[:-1], years[1:]):
        prev_total = dom[prev] + intl[prev]
        # target_total = prev_total*(1+floor) + e*(factor*dom_prev + intl_prev)
        denom = factor * dom[prev] + intl[prev]
        e = ((total[y] - prev_total * (1.0 + floor)) / denom) if denom else 0.0
        dom[y] = dom[prev] * (1.0 + floor + factor * e)
        intl[y] = intl[prev] * (1.0 + floor + e)
    return dom, intl


def check_adding_up(part_a: dict, part_b: dict, total: dict, name: str, tol=1e-6):
    """Build-stopping: part_a + part_b == total for every year (B2)."""
    for y in total:
        s = part_a.get(y, 0.0) + part_b.get(y, 0.0)
        if abs(s - total[y]) > tol * max(1.0, abs(total[y])):
            raise ReconciliationError(f"{name}: {part_a.get(y)}+{part_b.get(y)} != total {total[y]} at {y}")


def excess_growth(series: dict, years, floor_rate=None) -> dict:
    """Growth above the floor per year (for verifying the domestic/international ratio)."""
    floor = get("segment_splits.floor_rate") if floor_rate is None else floor_rate
    return {y: (series[y] / series[p] - 1.0) - floor for p, y in zip(years[:-1], years[1:])}

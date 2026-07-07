"""cockpit/scenarios - the per-project scenario register (Cockpit build update D).

High/Low from a client-set growth delta, plus one-off client scenarios: a demand
shock (year, depth, recovery years, pandemic-shaped), a level event (carrier
failure with a partial backfill fraction over a period), and a capacity timing
slip. Each is a transform applied before a whole-chain re-run (constrained pass,
ATMs, DDFS, capacity requirement); active scenarios become their own Excel sheet
sets and chart lines. Author: Avia Solutions.
"""
from __future__ import annotations
from dataclasses import dataclass


def apply_delta(path: dict, delta_per_year: float, base_year: int) -> dict:
    """High/Low: a compounding growth delta from the base year (client-set)."""
    return {y: v * (1.0 + delta_per_year) ** max(0, y - base_year) for y, v in path.items()}


def apply_demand_shock(path: dict, year: int, depth: float, recovery_years: int) -> dict:
    """Pandemic-shaped demand shock: a drop of `depth` (fraction) at `year`, then a
    linear recovery to the baseline over `recovery_years`. Depth is exact at the
    shock year; the baseline is regained exactly at year + recovery_years."""
    out = {}
    for y, v in path.items():
        if y < year:
            out[y] = v
        elif y >= year + recovery_years:
            out[y] = v
        else:
            k = y - year
            mult = (1.0 - depth) + depth * (k / recovery_years) if recovery_years else 1.0
            out[y] = v * mult
    return out


def apply_level_event(path: dict, year: int, failure_fraction: float,
                      backfill_fraction: float, period: int) -> dict:
    """Carrier failure: remove `failure_fraction` at `year`, backfilled by
    `backfill_fraction` over `period` years; the permanent loss is
    failure_fraction x (1 - backfill_fraction)."""
    out = {}
    for y, v in path.items():
        if y < year:
            out[y] = v
        else:
            k = min(period, y - year)
            recovered = backfill_fraction * (k / period) if period else backfill_fraction
            mult = 1.0 - failure_fraction * (1.0 - recovered)
            out[y] = v * mult
    return out


def build_capacity(base: float, steps, years) -> dict:
    """Capacity path from a base level plus committed step increments [(year, inc)]."""
    out = {}
    for y in years:
        out[y] = base + sum(inc for (sy, inc) in steps if sy <= y)
    return out


def apply_capacity_slip(steps, slip_years: int):
    """Delay every committed capacity step by `slip_years`. With no steps there is
    nothing to slip, so the capacity path is unchanged (the slip only bites where a
    step exists)."""
    return [(sy + slip_years, inc) for (sy, inc) in steps]


@dataclass
class Scenario:
    name: str
    kind: str            # delta | demand_shock | level_event | capacity_slip
    params: dict

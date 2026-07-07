"""backtest - hold-out validation of the demand method (Method Spec 9) and the
V-FARE two-method fare-elasticity check (Fable Part B). Author: Avia Solutions.

Fit on the fit window, forecast the forecast window with drivers known ex post,
and score per region against a naive GDP-multiple benchmark. Acceptance is by
count of regions within a bias tolerance, not a single global number, so a good
global figure cannot hide offsetting regional errors. Nothing here raises; a
backtest failure is evidence for the review, reported through the exception layer.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from ..config import get


def _window(name):
    lo, hi = get(f"backtest.{name}")
    return list(range(lo, hi + 1))


def region_bias(actual: dict, forecast: dict, window=None) -> float:
    """Mean relative forecast error over the forecast window: positive = the model
    ran hot (over-forecast). Years missing from either series are skipped."""
    yrs = window or _window("forecast_window")
    errs = [(forecast[y] - actual[y]) / actual[y]
            for y in yrs if y in actual and y in forecast and actual[y]]
    return sum(errs) / len(errs) if errs else float("nan")


def naive_forecast(base_value: float, gdp_growth: dict, window=None,
                   multiple: float | None = None) -> dict:
    """The benchmark the method must beat: traffic grows at GDP growth x a fixed
    multiple (Method Spec 9). gdp_growth is {year: growth rate}."""
    mult = get("backtest.naive_gdp_multiple") if multiple is None else multiple
    yrs = window or _window("forecast_window")
    out, lvl = {}, base_value
    for y in yrs:
        lvl *= (1.0 + mult * gdp_growth.get(y, 0.0))
        out[y] = lvl
    return out


def rmse(actual: dict, forecast: dict, window=None) -> float:
    yrs = window or _window("forecast_window")
    es = [(forecast[y] - actual[y]) / actual[y]
          for y in yrs if y in actual and y in forecast and actual[y]]
    return (sum(e * e for e in es) / len(es)) ** 0.5 if es else float("nan")


@dataclass
class BacktestResult:
    region_bias: dict                # region -> mean relative error
    regions_passing: int
    regions_total: int
    accepted: bool                   # count within tolerance meets the minimum
    beats_naive: dict = field(default_factory=dict)   # region -> model RMSE < naive RMSE
    exceptions: list = field(default_factory=list)


def run_backtest(actual_by_region: dict, model_by_region: dict,
                 naive_by_region: dict | None = None,
                 bias_tol: float | None = None, min_regions: int | None = None) -> BacktestResult:
    """Score the method region by region (Method Spec 9). Accept overall when at
    least `min_regions` of the regions sit within the bias tolerance."""
    bias_tol = get("backtest.acceptance_bias_abs") if bias_tol is None else bias_tol
    min_regions = get("backtest.acceptance_regions_min") if min_regions is None else min_regions

    biases, passing, beats, exc = {}, 0, {}, []
    for r, actual in actual_by_region.items():
        b = region_bias(actual, model_by_region.get(r, {}))
        biases[r] = b
        ok = (b == b) and abs(b) <= bias_tol             # b==b screens NaN
        passing += 1 if ok else 0
        if not ok:
            exc.append(f"backtest {r}: bias {b:+.3f} outside +/-{bias_tol}")
        if naive_by_region and r in naive_by_region:
            m = rmse(actual, model_by_region.get(r, {}))
            n = rmse(actual, naive_by_region[r])
            beats[r] = (m == m) and (n == n) and m < n
            if not beats[r]:
                exc.append(f"backtest {r}: model RMSE {m:.3f} not better than naive {n:.3f}")

    total = len(actual_by_region)
    return BacktestResult(biases, passing, total, passing >= min_regions, beats, exc)


@dataclass
class VFareResult:
    bf_observed: float
    bf_cost_driven: float
    gap: float
    agree: bool


def vfare_check(bf_observed: float, bf_cost_driven: float, tol: float | None = None) -> VFareResult:
    """V-FARE (Fable Part B): the US segment fare elasticity estimated two ways,
    from observed DB1B fares and from the cost-driven counterfactual, must agree
    within tolerance. Disagreement means the cost model or the fare data is wrong
    and the segment bF should not be trusted; reported, not raised."""
    tol = get("fare_strategy.vfare_tolerance") if tol is None else tol
    gap = abs(bf_observed - bf_cost_driven)
    return VFareResult(bf_observed, bf_cost_driven, gap, gap <= tol)

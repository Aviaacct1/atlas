"""Backtest (Method Spec 9) and V-FARE two-method check. Author: Avia Solutions."""
import pytest

from avia_forecast.backtest import backtest as bt
from avia_forecast.config import get

WIN = list(range(*[get("backtest.forecast_window")[0], get("backtest.forecast_window")[1] + 1]))


def _flat(v):
    return {y: v for y in WIN}


def test_region_bias_sign_and_magnitude():
    actual = _flat(100.0)
    hot = {y: 105.0 for y in WIN}      # over-forecast by 5%
    assert bt.region_bias(actual, hot) == pytest.approx(0.05)
    cold = {y: 98.0 for y in WIN}
    assert bt.region_bias(actual, cold) == pytest.approx(-0.02)


def test_naive_uses_gdp_multiple():
    g = {y: 0.02 for y in WIN}
    nf = bt.naive_forecast(100.0, g, multiple=1.5)
    # first year grows by 1.5 x 2% = 3%
    assert nf[WIN[0]] == pytest.approx(103.0)


def test_acceptance_needs_minimum_regions_within_tolerance():
    tol = get("backtest.acceptance_bias_abs")          # 0.02
    minr = get("backtest.acceptance_regions_min")      # 6 of 8
    regions = [f"R{i}" for i in range(8)]
    actual = {r: _flat(100.0) for r in regions}
    # 6 regions spot-on, 2 regions badly off -> exactly meets the minimum
    model = {}
    for i, r in enumerate(regions):
        model[r] = _flat(100.0) if i < minr else _flat(120.0)
    res = bt.run_backtest(actual, model)
    assert res.regions_passing == minr
    assert res.accepted is True
    # drop one more region below tolerance -> rejected
    model[regions[minr - 1]] = _flat(120.0)
    res2 = bt.run_backtest(actual, model)
    assert res2.regions_passing == minr - 1 and res2.accepted is False


def test_beats_naive_flagged_per_region():
    actual = {"NA": {y: 100.0 * (1.03 ** i) for i, y in enumerate(WIN)}}   # true ~3%/yr
    model = {"NA": {y: 100.0 * (1.031 ** i) for i, y in enumerate(WIN)}}   # close
    naive = {"NA": {y: 100.0 * (1.06 ** i) for i, y in enumerate(WIN)}}    # GDP x multiple overshoots
    res = bt.run_backtest(actual, model, naive_by_region=naive)
    assert res.beats_naive["NA"] is True


def test_vfare_agreement_within_tolerance():
    ok = bt.vfare_check(-0.60, -0.68)      # gap 0.08 <= 0.15
    assert ok.agree and ok.gap == pytest.approx(0.08)
    bad = bt.vfare_check(-0.60, -0.85)     # gap 0.25 > 0.15
    assert not bad.agree

"""Coherence tests (Method Spec 8.2): rolling-decade CAGR band + external divergence
(reporting only, per John's 'goal not constraint'). Author: Avia Solutions."""
import pytest

from avia_forecast.coherence import coherence as co
from avia_forecast.config import get


def test_cagr_basic():
    assert co.cagr(100.0, 200.0, 10) == pytest.approx(2 ** 0.1 - 1)


def test_plausible_series_passes_band():
    # steady 3.5%/yr sits inside the default band (-3% .. 12%)
    s = {y: 100.0 * (1.035 ** (y - 2025)) for y in range(2025, 2051)}
    res = co.check_rolling_cagr(s)
    assert res.ok and res.flags == []


def test_implausible_decade_is_flagged_not_raised():
    hi = get("coherence.rolling_decade_cagr_max")     # 0.12
    # a decade compounding at 15%/yr breaches the ceiling
    s = {y: 100.0 * (1.15 ** (y - 2025)) for y in range(2025, 2051)}
    res = co.check_rolling_cagr(s)
    assert not res.ok and len(res.flags) > 0
    assert all(w[2] > hi for w in res.flags)          # flagged windows are above the ceiling


def test_external_divergence_reports_gap_only():
    # model ~3.0%/yr vs a Boeing-style 3.6%/yr reference
    s = {y: 100.0 * (1.03 ** (y - 2025)) for y in range(2025, 2051)}
    d = co.external_divergence(s, external_cagr=0.036)
    assert d.gap_pp == pytest.approx((0.03 - 0.036) * 100.0, abs=1e-6)
    assert d.within_goal is False                     # 0.6pp gap exceeds the 0.5pp soft band, but nothing acts on it

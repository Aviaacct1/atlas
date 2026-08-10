"""The maturity basis and the elasticity interpolation. Author: Avia Solutions.

Until 9 August 2026 maturity was a cliff at 25,000 international dollars per head: at or
above it a country took the mature income elasticity, below it the emerging one, with
nothing in between. China sat at 29,333 with 0.4 trips per capita and took the mature
domestic elasticity of 1.0 on half its traffic. These assert that the cliff is gone, that
the interpolation is continuous, and that the income basis still reproduces the old
behaviour exactly, because a switch whose old setting no longer reproduces the old numbers
is not a switch.
"""
import pytest

from avia_forecast import global_demand as gd
from avia_forecast.config import _load as cfg_load


def _book():
    return cfg_load("assumptions_book.yaml")


def test_the_book_states_the_basis():
    assert _book()["global_drivers"]["maturity_basis"] in ("income_threshold", "saturation")


def test_bG_interpolates_between_emerging_and_mature():
    d = cfg_load("assumptions_book.yaml")["level3_defaults"]["Domestic"]
    assert gd._bG("Domestic", 0.0) == pytest.approx(d["bG_emerging"])
    assert gd._bG("Domestic", 1.0) == pytest.approx(d["bG_mature"])
    mid = gd._bG("Domestic", 0.5)
    assert mid == pytest.approx((d["bG_emerging"] + d["bG_mature"]) / 2)
    # monotone, and no jump anywhere in between
    prev = gd._bG("Domestic", 0.0)
    for i in range(1, 21):
        v = gd._bG("Domestic", i / 20)
        assert abs(v - prev) < 0.1, "a step this large is a cliff, not an interpolation"
        prev = v


def test_the_label_form_still_works():
    d = cfg_load("assumptions_book.yaml")["level3_defaults"]["Long Haul"]
    assert gd._bG("Long Haul", "mature") == d["bG_mature"]
    assert gd._bG("Long Haul", "emerging") == d["bG_emerging"]


def test_income_threshold_reproduces_the_cliff():
    book = _book()
    keep = book["global_drivers"]["maturity_basis"]
    book["global_drivers"]["maturity_basis"] = "income_threshold"
    try:
        thr = book["global_drivers"]["maturity_gdppc_threshold_usd"]
        wb = {"XX": {"gdp_pc_ppp": thr, "pop": 1e6}, "YY": {"gdp_pc_ppp": thr - 1, "pop": 1e6}}
        assert gd._maturity_weight("XX", "Asia Pacific", wb, 0.1) == 1.0
        assert gd._maturity_weight("YY", "Asia Pacific", wb, 0.1) == 0.0
    finally:
        book["global_drivers"]["maturity_basis"] = keep


def test_saturation_reads_maturity_off_behaviour_not_income():
    book = _book()
    keep = book["global_drivers"]["maturity_basis"]
    book["global_drivers"]["maturity_basis"] = "saturation"
    try:
        rich = {"CN": {"gdp_pc_ppp": 29333, "pop": 1.4e9}}
        # A rich country flying very little is not mature on this basis, which is the
        # whole point: China at 0.4 trips per capita against an Asia Pacific ceiling of
        # 2.6 is a mature market on the income measure and on no other.
        w = gd._maturity_weight("CN", "Asia Pacific", rich, 0.4)
        assert 0.0 < w < 0.25
        # and a country already at its ceiling is fully mature whatever its income
        assert gd._maturity_weight("CN", "Asia Pacific", rich, 5.0) == 1.0
    finally:
        book["global_drivers"]["maturity_basis"] = keep


def test_saturation_falls_back_when_trips_per_capita_is_unknown():
    """A country with no population record has no trips per capita, so the saturation
    basis cannot be applied to it and it must fall back to the stated income rule rather
    than silently taking a weight of zero, which would be the emerging elasticity for
    every country the World Bank does not publish."""
    book = _book()
    keep = book["global_drivers"]["maturity_basis"]
    book["global_drivers"]["maturity_basis"] = "saturation"
    try:
        assert gd._maturity_weight("ZZ", "North America", {}, None) == 1.0
        assert gd._maturity_weight("ZZ", "Africa", {}, None) == 0.0
    finally:
        book["global_drivers"]["maturity_basis"] = keep

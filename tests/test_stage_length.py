"""The stage length conversion. Author: Avia Solutions.

The point of these is the last one. A constant stage length cancels inside our own CAGR,
which is why the RPK CAGR equalled the passenger CAGR to the decimal place for as long as
the conversion held it constant, and why two thirds of the headline gap against Boeing was
a convention rather than a difference of view. If the growth term ever stops reaching the
conversion, that equality comes back and nothing else fails.
"""
import math

import pytest

from avia_forecast import stage_length as sl
from avia_forecast.config import _load as cfg_load


def test_base_km_covers_every_engine_region():
    tbl = cfg_load("stage_length.yaml")["base_km_per_passenger"]
    for region in ("Europe", "Asia Pacific", "North America", "South America",
                   "Middle East", "Africa"):
        assert region in tbl, f"{region} has no base stage length"
    assert "_G" in tbl, "no fallback for a region the table does not name"


def test_growth_covers_every_boeing_region():
    scheme = cfg_load("region_schemes.yaml")["schemes"]["boeing_cmo"]["regions"]
    tbl = cfg_load("stage_length.yaml")["growth_by_boeing_region"]
    for region in scheme:
        assert region in tbl, f"{region} has no stage length growth rate"
    assert "World" in tbl, "no common rate to fall back to"


def test_unknown_region_takes_the_common_rate_not_zero():
    """Zero would be a claim that a region's network shape is frozen. It is not the
    neutral choice it looks like, so the fallback is the measured common rate."""
    assert sl.growth("Nowhere") == sl.growth("World")
    assert sl.growth("Nowhere") > 0


def test_factor_is_one_in_the_base_year():
    assert sl.factor("China", sl.base_year()) == pytest.approx(1.0)


def test_factor_compounds_at_the_stated_rate():
    g = sl.growth("Oceania")
    n = 19
    assert sl.factor("Oceania", sl.base_year() + n) == pytest.approx((1 + g) ** n)


def test_growth_rates_are_inside_a_plausible_band():
    """A stage length growing faster than 2% a year doubles an average sector in 35 years,
    which is a claim about aircraft and network shape, not a conversion."""
    tbl = cfg_load("stage_length.yaml")["growth_by_boeing_region"]
    for region, g in tbl.items():
        assert -0.005 <= g <= 0.02, f"{region} at {g:.3%} is outside the plausible band"


def test_a_growing_stage_length_does_not_cancel_in_a_cagr():
    """The defect this module exists to fix. With growth, the RPK CAGR exceeds the
    passenger CAGR by the stage length growth. Without it, the two are equal."""
    pax0, pax1, n = 100.0, 200.0, 20
    pax_cagr = (pax1 / pax0) ** (1 / n) - 1

    y0 = sl.base_year()
    y1 = y0 + n
    rpk0 = sl.rpk(pax0, "Asia Pacific", "Southeast Asia", y0)
    rpk1 = sl.rpk(pax1, "Asia Pacific", "Southeast Asia", y1)
    rpk_cagr = (rpk1 / rpk0) ** (1 / n) - 1

    assert rpk_cagr == pytest.approx(pax_cagr + sl.growth("Southeast Asia")
                                     + pax_cagr * sl.growth("Southeast Asia"), abs=1e-9)
    assert rpk_cagr > pax_cagr + 0.005

    flat0 = pax0 * sl.base_km("Asia Pacific")
    flat1 = pax1 * sl.base_km("Asia Pacific")
    assert (flat1 / flat0) ** (1 / n) - 1 == pytest.approx(pax_cagr)


def test_km_grows_from_the_base_level():
    y = sl.base_year() + 10
    assert sl.km("Middle East", "Middle East", y) == pytest.approx(
        sl.base_km("Middle East") * (1 + sl.growth("Middle East")) ** 10)
    assert math.isclose(sl.km("Middle East", "Middle East", sl.base_year()),
                        sl.base_km("Middle East"))

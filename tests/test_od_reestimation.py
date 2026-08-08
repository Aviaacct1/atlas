"""O-19 finding: on real MAN data the O&D-based elasticity stays above the book clamp (capacity-led
growth), so O&D re-estimation does NOT make the clamp a backstop. This test encodes the finding against
the real MAN O&D and UK GDP series. Author: Avia Solutions."""
from avia_forecast.estimate import od_reest

MAN_OD = {2013: 19.2e6, 2014: 20.38e6, 2015: 21.78e6, 2016: 23.94e6, 2017: 26.58e6, 2018: 26.05e6,
          2019: 26.65e6, 2020: 8.31e6, 2021: 6.27e6, 2022: 21.05e6, 2023: 25.77e6, 2024: 28.61e6,
          2025: 30.24e6}
GB_GDP = {"2013": 2776926.0, "2014": 2865671.0, "2015": 2929296.0, "2016": 2985570.0, "2017": 3064839.0,
          "2018": 3107863.0, "2019": 3158882.0, "2020": 2831625.0, "2021": 3077266.0, "2022": 3210980.0,
          "2023": 3214320.0, "2024": 3250025.0, "2025": 3315758.0}


def test_od_elasticity_still_inflated_and_clamp_binds():
    r = od_reest.estimate_od_bG(MAN_OD, GB_GDP)
    assert r["bG_raw"] > 2.2                    # O&D elasticity above the book clamp (capacity-led)
    assert r["clamp_binds"] and r["bG_clamped"] == 2.2
    assert not r["reliable"]                    # not a trustworthy income elasticity


def test_short_series_returns_none():
    assert od_reest.estimate_od_bG({2013: 1e6, 2014: 1.05e6}, GB_GDP) is None

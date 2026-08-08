"""O-22 acceptance: the Method Spec 9 backtest at scale recovers the elasticity from pre-base history,
drives forward with actual GDP, and beats the naive GDP-multiple benchmark. Tested on a synthetic
hold-out so the logic is checked without E:. Author: Avia Solutions."""
from avia_forecast.backtest import at_scale


def _panel_and_gdp():
    gdp = {"XX": {str(y): 100 * (1.03 ** (y - 2000)) for y in range(2000, 2025)}}
    panel = [{"iata": "AAA", "year": y, "terminal_pax": gdp["XX"][str(y)] ** 1.2, "country_code": "XX"}
             for y in range(2000, 2025)]
    return panel, gdp


def test_scale_recovers_elasticity_and_beats_naive():
    panel, gdp = _panel_and_gdp()
    ex, rows = at_scale.run_scale(panel, gdp, base_year=2014, score_years=(2019, 2024), naive_mult=1.5)
    r = next(x for x in rows if x["iata"] == "AAA" and x["score_year"] == 2019)
    assert abs(r["bG"] - 1.2) < 0.02                 # elasticity recovered from <= 2014 history
    assert abs(r["model_err"]) < 1e-6                # actual-GDP-driven -> exact on the synthetic
    assert abs(r["naive_err"]) > abs(r["model_err"])  # model beats naive
    assert ex["summary"][2019]["model_beats_naive_share"] == 1.0
    assert ex["summary"][2019]["n"] == 1

"""D1: the full-engine propensity mechanism and its country-scale backtest. Propensity damps a
near-mature market more than an emerging one; the backtest runs and reports vs naive. Author: Avia
Solutions."""
from avia_forecast.estimate import propensity as pr
from avia_forecast.backtest import full_engine


def test_propensity_damps_mature_more_than_emerging():
    yrs = list(range(2014, 2020))
    pop = {y: 1_000_000.0 for y in yrs}
    gdp_pc = {y: 1.03 ** (y - 2014) for y in yrs}
    mature = pr.evolve(3_100_000.0, pop, gdp_pc, 3.2, yrs)      # tpc 3.1 near asymptote 3.2
    emerging = pr.evolve(300_000.0, pop, gdp_pc, 3.2, yrs)      # tpc 0.3 far below
    gm = mature.traffic[2019] / mature.traffic[2014] - 1
    ge = emerging.traffic[2019] / emerging.traffic[2014] - 1
    assert ge > gm                                             # emerging retains more excess growth


def test_full_engine_backtest_runs_and_reports():
    gdp = {"XX": {str(y): 100 * (1.03 ** (y - 2010)) for y in range(2010, 2025)}}
    pop = {"XX": {str(y): 1000.0 for y in range(2010, 2025)}}
    panel = [{"country_code": "XX", "iata": "AAA", "year": y, "terminal_pax": 1e6 * (1.04 ** (y - 2010))}
             for y in range(2010, 2025)]
    ex, rows = full_engine.run_full_engine(panel, gdp, pop, base_year=2014, score_years=(2019,))
    assert ex["summary"][2019]["n"] == 1
    assert "wmape_model" in ex["summary"][2019] and "beats_naive_wmape" in ex["summary"][2019]

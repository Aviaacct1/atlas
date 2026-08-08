"""Backtest scaffolding (John's methodology): error rises with horizon, and with actual GDP the method
error is isolated while a wrong GDP input surfaces as GDP-provider error. Author: Avia Solutions."""
from avia_forecast.backtest import scaffold


def test_gdp_error_separates_and_rises_with_horizon():
    yrs = range(2015, 2026)
    pop = {str(y): 1000.0 for y in yrs}
    gdp_actual = {str(y): 100 * (1.03 ** (y - 2015)) for y in yrs}
    gdp_forecast = {str(y): 100 * (1.02 ** (y - 2015)) for y in yrs}   # provider under-forecasts GDP
    base_pax = 1_000_000.0
    # actual traffic = the engine driven on ACTUAL gdp (so method error is zero by construction)
    actual_pax = scaffold.econometric_path(base_pax, 2015, gdp_actual, pop, "EU+UK", 2025)
    d = scaffold.decompose(base_pax, 2015, {}, gdp_actual, gdp_forecast, pop, "EU+UK", actual_pax, 2025)
    assert all(abs(e) < 1e-9 for e in d["method_error"].values())        # actual GDP -> our error isolated to 0
    te = d["total_error"]
    assert abs(te[5]) > abs(te[1])                                       # error rises with horizon
    assert all(e < 0 for e in te.values())                              # under-forecast GDP -> under-forecast pax
    assert all(abs(d["gdp_provider_error"][h] - te[h]) < 1e-9 for h in te)  # all error is the GDP provider's


def test_capacity_anchor_binds_near_term_in_scaffold():
    yrs = range(2015, 2021)
    pop = {str(y): 1000.0 for y in yrs}
    gdp = {str(y): 100 * (1.02 ** (y - 2015)) for y in yrs}
    seats = {y: 100.0 * (1.06 ** (y - 2015)) for y in yrs}              # capacity grows 6%/yr
    out, thin = scaffold.blended_forecast(1_000_000.0, 2015, seats, gdp, pop, "EU+UK", 2020)
    assert not thin
    assert abs(out[2016] - 1_060_000.0) < 1.0                          # t+1 fully anchored to seats (+6%)

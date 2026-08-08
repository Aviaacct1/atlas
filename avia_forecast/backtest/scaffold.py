"""backtest/scaffold - our own forecast backtest scaffolding (John's methodology). Author: Avia Solutions.

Drives the blended capacity+econometric forecast from a base year to a horizon, scores error BY HORIZON
YEAR (low in years 1-3, rising out), and separates our method error from the GDP-forecast-provider error
by running with actual GDP (perfect foresight) versus the GDP forecast available at the base year.
"""
from __future__ import annotations

from ..estimate import propensity as pr
from ..demand import capacity_anchor as ca
from ..geo.regions_iso2 import region_for_iso2


def econometric_path(base_pax, base_year, gdp, pop, region, horizon):
    """Propensity-damped econometric path driven by the given GDP and population series."""
    yrs = list(range(base_year, horizon + 1))
    asy = pr.asymptote_for(region or "default")
    population = {y: float(pop[str(y)]) * 1000.0 for y in yrs}
    gdp_pc = {y: float(gdp[str(y)]) / population[y] for y in yrs}
    path = pr.evolve(base_pax, population, gdp_pc, asy, yrs)
    return {y: path.traffic[y] for y in yrs}


def blended_forecast(base_pax, base_year, seats, gdp, pop, region, horizon, span=5):
    """Capacity anchor (seats) blended into the econometric path over the house transition."""
    econ = econometric_path(base_pax, base_year, gdp, pop, region, horizon)
    return ca.blend(base_pax, seats, base_year, econ, span=span)


def error_by_horizon(actual, forecast, base_year):
    """{horizon_year: relative error} for horizons beyond the base year."""
    return {y - base_year: forecast[y] / actual[y] - 1.0
            for y in forecast if y in actual and actual[y] and y > base_year}


def decompose(base_pax, base_year, seats, gdp_actual, gdp_forecast, pop, region, actual_pax,
              horizon, span=5):
    """Total error (forecast GDP) vs method error (actual GDP); the difference is the GDP-provider
    contribution. Returns {method_error, total_error, gdp_provider_error, thin} keyed by horizon."""
    f_actual, _ = blended_forecast(base_pax, base_year, seats, gdp_actual, pop, region, horizon, span)
    f_fore, thin = blended_forecast(base_pax, base_year, seats, gdp_forecast, pop, region, horizon, span)
    method = error_by_horizon(actual_pax, f_actual, base_year)
    total = error_by_horizon(actual_pax, f_fore, base_year)
    gdp_err = {h: total[h] - method[h] for h in method if h in total}
    return {"method_error": method, "total_error": total, "gdp_provider_error": gdp_err, "thin": thin}

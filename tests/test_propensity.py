"""Propensity-to-fly maturity acceptance test (Cockpit build update B1). Author: Avia Solutions."""
import numpy as np
import pytest
from avia_forecast.estimate import propensity as pr

YEARS = list(range(2025, 2051))
SPOT = list(range(2025, 2051, 5))
A = 3.0                                        # saturation ceiling, trips per capita


def _paths(g_gdp=0.03, g_pop=0.005):
    gdp_pc = {}; pop_base = {}
    lg, lp = 100.0, 1.0
    for i, y in enumerate(YEARS):
        gdp_pc[y] = lg; pop_base[y] = lp
        lg *= (1 + g_gdp); lp *= (1 + g_pop)
    return gdp_pc, pop_base


def _catchment(s0, pop0):
    gdp_pc, popf = _paths()
    pop = {y: pop0 * popf[y] for y in YEARS}
    tpc0 = s0 * A
    return pr.evolve(tpc0 * pop[YEARS[0]], pop, gdp_pc, asymptote=A, years=YEARS)


def test_world_curve_fit_recovers_slope():
    gdp_pc = [2000, 5000, 12000, 30000, 55000]
    b_true, a_true = 0.9, -8.0
    trips_pc = [np.exp(a_true + b_true * np.log(g)) for g in gdp_pc]
    a, b = pr.fit_world_curve(gdp_pc, trips_pc)
    assert b == pytest.approx(0.9, abs=1e-6)


def test_B1_monotone_decline_and_ordering_by_saturation():
    manc = _catchment(s0=0.65, pop0=10.0)      # Manchester-class: near-mature
    delhi = _catchment(s0=0.05, pop0=30.0)     # Delhi-class: unsaturated

    c_manc = pr.period_cagrs(manc.traffic, SPOT)
    c_delhi = pr.period_cagrs(delhi.traffic, SPOT)

    # monotone declining period CAGRs for each catchment
    assert all(c_manc[i] <= c_manc[i - 1] + 1e-9 for i in range(1, len(c_manc)))
    assert all(c_delhi[i] <= c_delhi[i - 1] + 1e-9 for i in range(1, len(c_delhi)))

    # decay ordering follows saturation: the unsaturated market keeps more growth
    assert all(cd > cm for cd, cm in zip(c_delhi, c_manc))

    # expected behaviour: near-mature keeps ~1/3 of excess, unsaturated ~90%
    first = YEARS[1]
    assert manc.retained_excess_fraction[first] == pytest.approx(0.35, abs=0.03)
    assert delhi.retained_excess_fraction[first] == pytest.approx(0.95, abs=0.03)


def test_no_hard_ceiling_growth_slows_but_continues():
    manc = _catchment(s0=0.65, pop0=10.0)
    assert manc.saturation[YEARS[-1]] > manc.saturation[YEARS[0]]   # matures over time
    # no hard ceiling: a mature market keeps growing (to the terminal floor), not flat
    assert manc.trips_pc[YEARS[-1]] > manc.trips_pc[YEARS[0]]
    late = manc.trips_pc[YEARS[-1]] / manc.trips_pc[YEARS[-2]] - 1.0
    assert late > 0.0                                              # still positive at high saturation

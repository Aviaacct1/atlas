"""Cargo/GA/total-ATM and design-day acceptance tests (Cockpit build update E1/E2/E3).
Author: Avia Solutions."""
import pytest
from avia_forecast.aggregate import atm

YEARS = list(range(2025, 2036))
SEG = ["Domestic", "International Short Haul", "Long Haul"]


def _gdp(g=0.02):
    d, lvl = {}, 100.0
    for y in YEARS:
        d[y] = lvl; lvl *= (1 + g)
    return d


def test_E1_cargo_grows_with_gdp_and_belly_rides_in_pax():
    gdp = _gdp()
    t = atm.cargo_tonnage(500.0, gdp, YEARS, elasticity=1.0)
    for y in YEARS:                                   # elasticity 1 -> tracks GDP exactly
        assert t[y] / t[YEARS[0]] == pytest.approx(gdp[y] / gdp[YEARS[0]])
    # belly (50%) carries no freighter ATMs; only the non-belly share does
    fr = atm.cargo_freighter_atm(500.0, belly_share=0.5, tonnes_per_atm=80.0)
    assert fr == pytest.approx(500.0 * 0.5 / 80.0)
    # GA grows at its own rate
    ga = atm.ga_series(100.0, 0.03, YEARS)
    assert ga[YEARS[1]] == pytest.approx(103.0)


def test_E2_design_day_consumes_total_atms_not_commercial_only():
    pax = {"Domestic": 10.0, "International Short Haul": 20.0, "Long Haul": 30.0}
    seats = {"Domestic": 150, "International Short Haul": 180, "Long Haul": 280}
    lf = {"Domestic": 0.80, "International Short Haul": 0.82, "Long Haul": 0.84}
    comm = atm.commercial_atm(pax, seats, lf)
    cargo_fr = atm.cargo_freighter_atm(500.0)
    ga_atm = 5.0

    total = atm.total_atm(comm, cargo_fr, ga_atm)
    assert total == pytest.approx(comm + cargo_fr + ga_atm)
    # DDFS on total exceeds DDFS on commercial-only when cargo/GA are present
    assert atm.design_day(total) > atm.design_day(comm)
    # with no cargo/GA the two coincide
    assert atm.design_day(atm.total_atm(comm, 0.0, 0.0)) == pytest.approx(atm.design_day(comm))


def test_E3_no_static_values_ddfs_moves_with_inputs():
    pax = {"Domestic": 10.0, "International Short Haul": 20.0, "Long Haul": 30.0}
    seats = {"Domestic": 150, "International Short Haul": 180, "Long Haul": 280}
    lf = {"Domestic": 0.80, "International Short Haul": 0.82, "Long Haul": 0.84}
    comm = atm.commercial_atm(pax, seats, lf)
    low = atm.design_day(atm.total_atm(comm, atm.cargo_freighter_atm(500.0), 5.0))
    high = atm.design_day(atm.total_atm(comm, atm.cargo_freighter_atm(900.0), 5.0))
    assert high > low                                 # more cargo -> more total ATMs -> bigger design day

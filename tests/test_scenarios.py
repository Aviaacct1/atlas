"""Scenario register acceptance tests (Cockpit build update D). Author: Avia Solutions."""
import pytest
from avia_forecast.cockpit import scenarios as sc

YEARS = list(range(2025, 2041))
BY = 2025


def _base(g=0.02):
    b, lvl = {}, 100.0
    for y in YEARS:
        b[y] = lvl; lvl *= (1 + g)
    return b


def test_D_demand_shock_depth_and_recovery_exact():
    base = _base()
    s = sc.apply_demand_shock(base, year=2030, depth=0.5, recovery_years=3)
    assert s[2030] == pytest.approx(base[2030] * 0.5)         # depth exact at the shock year
    assert s[2033] == pytest.approx(base[2033])               # fully recovered at year+recovery
    assert base[2030] * 0.5 < s[2031] < base[2031]            # recovering in between
    assert s[2029] == base[2029]                              # untouched before


def test_D_high_base_low_ordering():
    base = _base()
    high = sc.apply_delta(base, +0.005, BY)
    low = sc.apply_delta(base, -0.005, BY)
    assert high[2040] > base[2040] > low[2040]


def test_D_level_event_permanent_loss_after_backfill():
    base = _base()
    e = sc.apply_level_event(base, year=2030, failure_fraction=0.2, backfill_fraction=0.5, period=4)
    assert e[2030] == pytest.approx(base[2030] * 0.8)         # -20% at failure
    assert e[2034] == pytest.approx(base[2034] * 0.9)         # permanent loss 0.2*(1-0.5)=0.1
    assert e[2038] == pytest.approx(base[2038] * 0.9)         # stays permanent


def test_D_capacity_slip_only_bites_where_a_step_exists():
    steps = [(2030, 10.0)]
    base_cap = sc.build_capacity(50.0, steps, YEARS)
    slipped = sc.build_capacity(50.0, sc.apply_capacity_slip(steps, 2), YEARS)
    assert base_cap[2030] == 60.0 and slipped[2030] == 50.0   # slip delays the step
    assert slipped[2032] == 60.0                              # step lands two years later
    # no step -> slip is a no-op (nothing to bite)
    flat = sc.build_capacity(50.0, [], YEARS)
    flat_slipped = sc.build_capacity(50.0, sc.apply_capacity_slip([], 2), YEARS)
    assert flat == flat_slipped

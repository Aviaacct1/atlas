"""Capacity tests: spill, redistribution and both-ends identity T-D
(Method Spec 6; Fable Q1 rule 2, Q2). Author: Avia Solutions."""
import pytest
from avia_forecast.capacity import spill as sp


def test_spill_curve_interpolates_and_saturates():
    assert sp.spill_fraction(0.80) == 0.0
    assert sp.spill_fraction(0.90) == pytest.approx(0.01)
    assert sp.spill_fraction(0.925) == pytest.approx(0.025)   # between 0.90 and 0.95
    assert sp.spill_fraction(1.50) == pytest.approx(0.10)     # saturates at last point


def test_airport_solve_below_threshold_is_unconstrained():
    s = sp.airport_solve(U=80.0, K=100.0)                     # u=0.8
    assert s.retention == 1.0 and s.spill == 0.0 and s.headroom == 20.0


def test_airport_solve_spills_above_threshold():
    s = sp.airport_solve(U=98.0, K=100.0)                     # u=0.98
    assert 0.0 < s.spill and s.C < s.U and s.C <= s.K
    assert s.retention == pytest.approx(s.C / s.U)


def test_connecting_spills_first_at_1_5x():
    od_red, conx_red = sp.allocate_shortfall(od_total=90.0, conx_total=10.0, E=10.0)
    # connecting reduced at 1.5x the O&D rate
    x = 10.0 / (90.0 + 1.5 * 10.0)
    assert conx_red == pytest.approx(1.5 * x * 10.0)
    assert od_red + conx_red == pytest.approx(10.0)           # shortfall fully allocated
    assert od_red <= 90.0 and conx_red <= 10.0


def test_redistribution_is_order_free_and_never_overfills():
    a = sp.airport_solve(U=98.0, K=100.0)     # spills, tiny headroom
    b = sp.airport_solve(U=40.0, K=100.0)     # lots of headroom
    r1 = sp.catchment_redistribute([a, b])
    r2 = sp.catchment_redistribute([b, a])    # reversed order
    assert sorted(r1.served) == pytest.approx(sorted(r2.served))   # order-free
    for s, served in zip([a, b], r1.served):
        assert served <= s.K + 1e-9                                # never overfills
    # conservation: sum U = sum served + suppressed
    total_U = a.U + b.U
    assert sum(r1.served) + r1.suppressed_total == pytest.approx(total_U)


def test_redistribution_fills_only_to_theta_K_no_cascade():
    theta = 0.85
    a = sp.airport_solve(U=150.0, K=100.0)    # capped at K; no theta-headroom
    b = sp.airport_solve(U=60.0, K=100.0)     # C=60, theta-headroom = 85 - 60 = 25
    r = sp.catchment_redistribute([a, b])
    # b filled to exactly theta*K, never to its own spill threshold
    assert r.served[1] == pytest.approx(theta * b.K)
    assert r.served[1] <= theta * b.K + 1e-9          # no-cascade: cannot start b spilling
    assert r.redistributed_total == pytest.approx(25.0)
    assert r.suppressed_total == pytest.approx(50.0 - 25.0)
    assert sum(r.served) + r.suppressed_total == pytest.approx(a.U + b.U)


def test_TD_both_ends_sequential_attribution_sums_to_flow():
    be = sp.both_ends(flow_u=1000.0, rho_o=0.90, rho_d_bar=0.85)
    assert be.flow_c == pytest.approx(1000.0 * 0.90 * 0.85)
    assert be.flow_c + be.origin_booking + be.dest_booking == pytest.approx(1000.0)   # T-D
    # double-constrained flow loses more than the tighter end alone (min would give 0.85)
    assert be.flow_c < 1000.0 * 0.85


def test_TD_holds_across_random_retentions():
    import random
    random.seed(0)
    for _ in range(200):
        f = random.uniform(1, 1e6); ro = random.uniform(0.3, 1.0); rd = random.uniform(0.3, 1.0)
        be = sp.both_ends(f, ro, rd)
        assert be.flow_c + be.origin_booking + be.dest_booking == pytest.approx(f, rel=1e-12)

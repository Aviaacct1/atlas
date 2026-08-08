"""C2 year-1 schedule anchor: the schedule weight tapers t+1 -> t+3, the blend anchors near-term to
capacity and reverts to econometrics, and a thin schedule falls back and is flagged. Author: Avia
Solutions."""
from avia_forecast.demand import capacity_anchor as ca


def test_anchor_weight_taper():
    assert ca.anchor_weight(2026, 2025, 3) == 1.0     # t+1 full schedule
    assert ca.anchor_weight(2027, 2025, 3) == 0.5     # t+2 half
    assert ca.anchor_weight(2028, 2025, 3) == 0.0     # t+3 econometrics
    assert ca.anchor_weight(2030, 2025, 3) == 0.0     # beyond
    assert ca.anchor_weight(2025, 2025, 3) == 0.0     # base year


def test_blend_anchors_near_term_and_reverts_to_econ():
    seats = {2025: 100.0, 2026: 120.0, 2027: 130.0, 2028: 140.0}
    econ = {2026: 1050.0, 2027: 1100.0, 2028: 1150.0, 2030: 1300.0}
    out, thin = ca.blend(1000.0, seats, 2025, econ, span=3)
    assert not thin
    assert abs(out[2026] - 1200.0) < 1e-6                       # t+1: base x seats ratio 120/100
    assert abs(out[2027] - (0.5 * 1300.0 + 0.5 * 1100.0)) < 1e-6  # t+2: half schedule half econ
    assert abs(out[2028] - 1150.0) < 1e-6                       # t+3: pure econ
    assert abs(out[2030] - 1300.0) < 1e-6                       # beyond: pure econ


def test_thin_schedule_falls_back_and_flags():
    out, thin = ca.blend(1000.0, {2025: 100.0}, 2025, {2026: 1050.0, 2027: 1100.0}, span=3)
    assert thin and abs(out[2026] - 1050.0) < 1e-6              # no 2026 seats -> econ, flagged

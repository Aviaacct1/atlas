"""Demand core tests (Method Spec 4.1-4.2, build decision D8). Author: Avia Solutions."""
import numpy as np
import pandas as pd
from avia_forecast.demand import core
from avia_forecast.config import get


def test_recursion_matches_constant_elasticity_closed_form():
    G = [100, 103, 108, 112]; F = [100, 98, 101, 99]
    bG, bF = 1.3, -0.6
    od = core.od_recursion(1_000_000, G, F, bG, bF)
    closed = 1_000_000 * (np.array(G)/G[0])**bG * (np.array(F)/F[0])**bF
    assert np.allclose(od, closed, rtol=1e-12)


def test_multiplicative_diverges_from_additive_over_horizon():
    # The failure 4.1 warns about: an emerging market compounding a high GDP
    # elasticity. Additive drifts below the mandated multiplicative form, and
    # the gap compounds year on year.
    G = 100 * 1.06 ** np.arange(26)      # 6%/yr GDP
    F = 100 * 0.995 ** np.arange(26)
    mult = core.od_recursion(1_000_000, G, F, 1.8, -0.6)
    add = core.od_additive_reference(1_000_000, G, F, 1.8, -0.6)
    div25 = (mult[-1] - add[-1]) / mult[-1]
    div10 = (mult[10] - add[10]) / mult[10]
    assert div25 > 0.03                  # material by the horizon
    assert div25 > div10 > 0             # compounding, not a one-off offset


def test_fare_build_up_matches_manual():
    theta = get("fare_index.pass_through_theta"); tau = get("fare_index.real_yield_trend_tau")
    F = core.fare_path(100.0, [0.10, 0.0])
    assert F[1] == 100.0 * (1 + theta*0.10) * (1 + tau)
    assert F[2] == F[1] * (1 + theta*0.0) * (1 + tau)


def test_overlay_applies_multiplicatively():
    G = [100, 110]; F = [100, 100]
    base = core.od_recursion(1_000_000, G, F, 1.0, -0.5)
    with_a = core.od_recursion(1_000_000, G, F, 1.0, -0.5, A=[0.0, 0.05])
    assert np.isclose(with_a[1], base[1] * 1.05)


def test_forecast_cell_tidy_roundtrip():
    drivers = pd.DataFrame({"year": [2025, 2026, 2027], "G": [100, 104, 108], "F": [100, 99, 98]})
    out = core.forecast_cell(4_000_000, drivers, 1.3, -0.6)
    assert list(out["year"]) == [2025, 2026, 2027]
    assert (out["metric"] == "od_pax").all()
    assert out.iloc[0]["value"] == 4_000_000

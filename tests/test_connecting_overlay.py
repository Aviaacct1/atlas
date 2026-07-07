"""Connecting overlay tests: identities T-A and T-B (Method Spec 5.2/5.4, Fable Q3).
Author: Avia Solutions."""
import numpy as np
import pytest
from avia_forecast.overlays import connecting as cx

REGIONS = ["Domestic", "EU+UK", "North America", "Asia Pacific"]


def test_TA_final_to_next_preserves_total_identity_default():
    od = {"Domestic": 5.0, "EU+UK": 3.0, "North America": 2.0, "Asia Pacific": 1.0}
    M = cx.identity_matrix(list(od.keys()))
    nd = cx.final_to_next(od, M)
    assert nd == od                                  # identity M => ND = OD
    assert sum(nd.values()) == pytest.approx(sum(od.values()))   # T-A


def test_TA_holds_for_a_hub_mixing_matrix():
    od = {"Domestic": 0.0, "EU+UK": 10.0, "North America": 6.0, "Asia Pacific": 4.0}
    # Long-haul finals route partly via a EU+UK first leg (a connecting hub)
    M = cx.identity_matrix(list(od.keys()))
    M["Asia Pacific"] = {"Domestic": 0.0, "EU+UK": 0.6, "North America": 0.0, "Asia Pacific": 0.4}
    M["North America"] = {"Domestic": 0.0, "EU+UK": 0.3, "North America": 0.7, "Asia Pacific": 0.0}
    nd = cx.final_to_next(od, M)
    assert sum(nd.values()) == pytest.approx(sum(od.values()))   # T-A holds under mixing
    assert nd["EU+UK"] == pytest.approx(10.0 + 0.3*6.0 + 0.6*4.0)


def test_non_row_stochastic_M_rejected():
    od = {"EU+UK": 1.0, "Asia Pacific": 1.0}
    bad = {"EU+UK": {"EU+UK": 0.9, "Asia Pacific": 0.0}, "Asia Pacific": {"EU+UK": 0.0, "Asia Pacific": 1.0}}
    with pytest.raises(ValueError):
        cx.final_to_next(od, bad)


def test_connecting_growth_tracks_unconstrained_flow():
    assert cx.connecting_growth(100.0, 1.20) == pytest.approx(120.0)
    assert cx.connecting_growth(100.0, 1.20, H=0.9) == pytest.approx(108.0)


def test_TB_terminal_identity():
    od = {"Domestic": 5.0, "EU+UK": 3.0}
    assert cx.terminal_unconstrained(od, conx_total=2.0) == pytest.approx(10.0)


# ---- Q4: nonstop-service fallback matrix and T-F ----

REGIONS4 = ["Domestic", "EU+UK", "Middle East", "Asia Pacific"]


def _uk_hub_M():
    # A UK secondary airport: nonstop to its own region and the Middle East,
    # no nonstop to Asia Pacific (routes via a Middle East hub, e.g. DXB).
    return cx.final_to_next_nonstop(
        REGIONS4, home_region="EU+UK",
        nonstop_regions={"EU+UK", "Middle East"},
        hub_firstleg_region={"Asia Pacific": "Middle East", "Middle East": "Middle East"},
    )


def test_nonstop_matrix_is_row_stochastic_and_routes_via_hub():
    M = _uk_hub_M()
    assert cx.is_row_stochastic(M)
    assert M["Asia Pacific"]["Middle East"] == pytest.approx(1.0)   # no nonstop: all via hub
    assert M["Domestic"]["Domestic"] == 1.0                          # identity for domestic


def test_TF_offdiagonal_mass_equals_connecting_base():
    from avia_forecast.aggregate import reconcile
    od = {"Domestic": 5.0, "EU+UK": 10.0, "Middle East": 3.0, "Asia Pacific": 4.0}
    M = _uk_hub_M()
    implied = cx.implied_connections(od, M)
    assert implied == pytest.approx(4.0)          # the 4m Asia Pacific pax all connect
    ok = reconcile.check_TF(implied, base_conx_total=4.2)
    assert ok.ok                                   # within 10%
    bad = reconcile.check_TF(implied, base_conx_total=3.0)
    assert not bad.ok and bad.conx_scale == pytest.approx(4.0 / 3.0)   # scale CONX to M

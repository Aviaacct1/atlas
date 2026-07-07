"""Aggregate + RPK + reconciliation tests: identities T-A, T-C, T-D, T-E
(Method Spec 7; Fable Q3). Author: Avia Solutions."""
import pytest
from avia_forecast.aggregate import rpk, reconcile
from avia_forecast.overlays import connecting as cx


def _dist(airport, region):
    table = {("LHR", "North America"): 5500, ("LHR", "EU+UK"): 800,
             ("LHR", "Domestic"): 400, ("DXB", "Asia Pacific"): 6800,
             ("LHR", "Middle East"): 5100}
    return table.get((airport, region), 3000)


def test_region_pair_flows_outbound_only():
    rows = [
        {"home_region": "EU+UK", "dest_region": "North America", "direction": "out", "value": 10.0},
        {"home_region": "EU+UK", "dest_region": "North America", "direction": "in", "value": 9.0},
        {"home_region": "EU+UK", "dest_region": "Asia Pacific", "direction": "out", "value": 4.0},
    ]
    flows = rpk.region_pair_flows(rows)
    assert flows[("EU+UK", "North America")] == 10.0     # inbound ignored
    assert flows[("EU+UK", "Asia Pacific")] == 4.0


def test_TC_leg_ledger_zero_stop_and_connection():
    # Origin LHR: intl outbound ND to North America and Middle East, plus domestic.
    nd = [
        {"airport": "LHR", "region": "North America", "value": 8.0, "is_domestic": False},
        {"airport": "LHR", "region": "Middle East", "value": 5.0, "is_domestic": False},
        {"airport": "LHR", "region": "Domestic", "value": 6.0, "is_domestic": True},
    ]
    # Connecting at DXB: onward leg to Asia Pacific (the LHR-DXB-SYD case).
    conx = [{"hub": "DXB", "region": "Asia Pacific", "value": 3.0}]
    led = rpk.build_leg_ledger(nd, conx, _dist)

    od_intl_out = 8.0 + 5.0          # equals ND intl outbound (T-A holds in totals)
    od_domestic = 6.0
    conx_total = 3.0
    reconcile.check_TC(led["total_leg_pax"], od_intl_out, od_domestic, conx_total)  # must not raise
    # domestic emitted at half weight
    assert led["total_leg_pax"] == pytest.approx(13.0 + 6.0 * 0.5 + 3.0)
    # rpk accumulates pax*distance
    assert led["rpk_total"] == pytest.approx(8*5500 + 5*5100 + 6.0*0.5*400 + 3*6800)


def test_TC_detects_double_count():
    nd = [{"airport": "LHR", "region": "Domestic", "value": 6.0, "is_domestic": True}]
    # bug: domestic counted at full weight -> T-C must catch it
    bugged = 6.0            # full weight instead of 3.0
    with pytest.raises(reconcile.ReconciliationError):
        reconcile.check_TC(bugged, od_intl_out_total=0.0, od_domestic_total=6.0, conx_total=0.0)


def test_TA_reconcile_passes_and_fails():
    od = {"EU+UK": 10.0, "Asia Pacific": 4.0, "Domestic": 6.0}
    M = cx.identity_matrix(list(od.keys()))
    nd = cx.final_to_next(od, M)
    reconcile.check_TA(sum(od.values()), sum(nd.values()))       # ok
    with pytest.raises(reconcile.ReconciliationError):
        reconcile.check_TA(sum(od.values()), sum(nd.values()) + 0.5)


def test_TE_regrow_diagnostic_flags_large_feed_suppression():
    # A hub whose feed market is heavily constrained: CONX_c overstated vs re-grow.
    conx_u = {("EU+UK", "Asia Pacific"): 100.0}
    conx_c = {("EU+UK", "Asia Pacific"): 95.0}     # kept 95 via own retention
    flow_u = {("EU+UK", "Asia Pacific"): 100.0}
    flow_c = {("EU+UK", "Asia Pacific"): 60.0}     # feed suppressed to 60
    flag = reconcile.regrow_diagnostic("HUB", conx_c, conx_u, flow_c, flow_u, hub_terminal=200.0)
    # CONX' = 100*0.6 = 60; gap = |95-60| = 35; share = 35/200 = 17.5% > 2%
    assert flag.gap == pytest.approx(35.0)
    assert flag.escalate is True


def test_both_ends_vs_capreq_within_tolerance():
    assert reconcile.check_both_ends_vs_capreq(100.0, 101.0)      # 1% <= 2%
    assert not reconcile.check_both_ends_vs_capreq(100.0, 130.0)  # 30% > 2%


# ---- Q5: mirror reconciliation (always-canonical, signed gap, config flip) ----

def test_mirror_default_home_canonical_and_flags_signed_gap():
    r = reconcile.reconcile_mirror("GB>US", home=100.0, partner=106.0)
    assert r.canonical_value == 100.0            # home canonical by default
    assert r.signed_gap == pytest.approx(0.06)   # signed, positive: partner runs high
    assert r.flagged                             # 6% > 5% tolerance


def test_mirror_within_tolerance_not_flagged():
    r = reconcile.reconcile_mirror("GB>FR", home=100.0, partner=103.0)
    assert not r.flagged and r.canonical_value == 100.0

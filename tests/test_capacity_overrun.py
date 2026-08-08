"""Overrun disposition (steer 7 Aug 2026) + catchment-spill wiring. Author: Avia Solutions."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from types import SimpleNamespace as NS

from avia_forecast.capacity import overrun
from avia_forecast.capacity import spill as spill_mod
from avia_forecast.config import get


def _fake(state, U, K):
    return NS(resolution=NS(state=state, statement="reg record"),
              unconstrained=dict(U), capacity=dict(K),
              spill={y: 0.0 for y in U}, constrained=dict(U))


def test_config_provisional_parameters_present():
    s = get("capacity_overrun.soft_spill_share")
    assert s is not None and 0.0 < float(s) < 1.0
    assert get("capacity_overrun.hard_cap_default") == "none_held"


def test_overrun_reclassified_base_spill_zero():
    # NTE-shaped: rated 4.1, observed base 6.97, growing demand
    U = {2025: 6.97, 2030: 7.8, 2050: 10.0}
    K = {2025: 4.09, 2030: 4.22, 2050: 4.73}
    r = _fake("constrained_evidenced", U, K)
    info = overrun.apply({"NTE": r}, 2025)
    assert "NTE" in info
    assert r.resolution.state == overrun.STATE
    assert r.spill[2025] == 0.0                       # base year squeezes through
    assert r.constrained[2025] == U[2025]             # C2 passes by construction
    s = float(get("capacity_overrun.soft_spill_share"))
    assert abs(r.spill[2030] - s * (7.8 - 6.97)) < 1e-9   # soft share on growth above observed base
    assert r.constrained[2050] == U[2050] - r.spill[2050]
    assert info["NTE"]["overrun_base_m"] == round(6.97 - 4.09, 2)
    assert "service-level line" in info["NTE"]["finding"]
    assert r.resolution.statement.startswith(info["NTE"]["finding"])   # register record kept


def test_k_never_floored_and_non_overrun_untouched():
    U = {2025: 3.0, 2030: 3.5}
    K = {2025: 4.0, 2030: 4.0}
    r = _fake("constrained_evidenced", U, K)
    info = overrun.apply({"AAA": r}, 2025)
    assert info == {}                                  # under rated capacity: not overrun
    assert r.resolution.state == "constrained_evidenced"
    # overrun airport keeps its rated K (never floored)
    U2 = {2025: 6.97, 2030: 7.8}; K2 = {2025: 4.09, 2030: 4.22}
    r2 = _fake("constrained_evidenced", U2, K2)
    overrun.apply({"NTE": r2}, 2025)
    assert r2.capacity == K2


def test_threshold_is_max_of_rated_and_observed():
    # rated grows past the observed base late in the horizon: threshold follows it
    sp, con, over = overrun.soft_paths({2025: 6.0, 2050: 6.5}, {2025: 5.0, 2050: 7.0},
                                       2025, share=0.5)
    assert sp[2025] == 0.0
    assert sp[2050] == 0.0                             # rated 7.0 > demand 6.5: nothing spills
    assert over[2050] == 0.0


def test_catchment_conservation_and_no_cascade():
    theta = float(get("capacity_redistribution.spill_start_threshold"))
    # one spiller, one receiver with room, one full receiver
    solves = [NS(U=10.0, K=8.0, C=7.0, spill=3.0),
              NS(U=4.0, K=10.0, C=4.0, spill=0.0),
              NS(U=9.5, K=10.0, C=9.5, spill=0.0)]
    red = spill_mod.catchment_redistribute(solves, theta)
    pool = sum(s.spill for s in solves)
    assert abs(pool - (red.redistributed_total + red.suppressed_total)) < 1e-9
    for s, rec in zip(solves, red.redistributed):
        assert rec <= max(0.0, theta * s.K - s.C) + 1e-9   # never past spill-start
    assert red.redistributed[0] == 0.0                 # the spiller receives nothing


def test_unregistered_receiver_gets_nothing():
    theta = float(get("capacity_redistribution.spill_start_threshold"))
    solves = [NS(U=10.0, K=8.0, C=7.0, spill=3.0),
              NS(U=4.0, K=0.0, C=4.0, spill=0.0)]      # K unknown: cannot receive
    red = spill_mod.catchment_redistribute(solves, theta)
    assert red.redistributed[1] == 0.0
    assert abs(red.suppressed_total - 3.0 + red.redistributed_total) < 1e-9


def test_overlapping_allocator_conservation_and_caps():
    from avia_forecast.capacity import catchment_join as cj
    theta = float(get("capacity_redistribution.spill_start_threshold"))
    spill = {"AAA": 2.0, "BBB": 1.0}
    K = {"AAA": 5.0, "BBB": 4.0, "CCC": 10.0, "DDD": 10.0}
    C = {"AAA": 5.0, "BBB": 4.0, "CCC": 6.0, "DDD": 8.6}
    cat = {"AAA": ["AAA", "CCC", "DDD"], "BBB": ["BBB", "CCC"]}
    rec, red, sup = cj.redistribute_overlapping(spill, K, C, cat, theta)
    assert abs((red + sup) - 3.0) < 1e-9                      # conservation
    for r, v in rec.items():
        assert v <= cj.headroom_to_theta(K[r], C[r], theta) + 1e-9   # no receiver past theta*K
    assert "AAA" not in rec and "BBB" not in rec               # spillers receive nothing


def test_catchment_loader_prefers_qsi(tmp_path):
    import json as j
    from avia_forecast.capacity import catchment_join as cj
    (tmp_path / cj.PARTITION_FILE).write_text(j.dumps({"X_Y": ["XXX", "YYY"]}))
    cat, meta, src = cj.load_catchments(str(tmp_path))
    assert src == "partition_2025" and cat["XXX"]["layers"][0][1] == ["XXX", "YYY"]
    (tmp_path / cj.QSI_FILE).write_text(j.dumps({"XXX": {"members": ["XXX", "ZZZ"]}}))
    cat, meta, src = cj.load_catchments(str(tmp_path))
    assert src == "qsi_drive_time" and cat["XXX"]["layers"][0][1] == ["XXX", "ZZZ"]


def test_weights_steer_allocation():
    from avia_forecast.capacity import catchment_join as cj
    theta = float(get("capacity_redistribution.spill_start_threshold"))
    spill = {"AAA": 1.0}
    K = {"AAA": 5.0, "NEAR": 100.0, "FAR": 100.0}
    C = {"AAA": 5.0, "NEAR": 10.0, "FAR": 10.0}      # equal huge headroom
    cat = {"AAA": ["AAA", "NEAR", "FAR"]}
    w = {"AAA": {"NEAR": 0.9, "FAR": 0.1}}
    rec, red, sup = cj.redistribute_overlapping(spill, K, C, cat, theta, w)
    assert abs(red - 1.0) < 1e-9 and sup < 1e-9
    assert abs(rec["NEAR"] - 0.9) < 1e-9 and abs(rec["FAR"] - 0.1) < 1e-9
    # a member with zero weight receives nothing even with headroom
    w2 = {"AAA": {"NEAR": 1.0}}
    rec2, _, _ = cj.redistribute_overlapping(spill, K, C, cat, theta, w2)
    assert "FAR" not in rec2


def test_loader_returns_weights(tmp_path):
    import json as j
    from avia_forecast.capacity import catchment_join as cj
    (tmp_path / cj.QSI_FILE).write_text(j.dumps(
        {"XXX": {"members": ["XXX", "YYY"], "weights": {"YYY": 0.7}}}))
    cat, meta, src = cj.load_catchments(str(tmp_path))
    assert src == "qsi_drive_time" and cat["XXX"]["layers"][0][2] == {"YYY": 0.7}


def test_two_layer_split_at_od_share():
    from avia_forecast.capacity import catchment_join as cj
    theta = float(get("capacity_redistribution.spill_start_threshold"))
    raw = {"LHR": {"od_share": 0.6,
                   "surface": {"members": ["LHR", "LGW"], "weights": {"LGW": 1.0}},
                   "network": {"members": ["CDG", "AMS"], "weights": {"CDG": 0.75, "AMS": 0.25}}}}
    cat = cj._normalise(raw)
    spill = {"LHR": 10.0}
    K = {"LHR": 80.0, "LGW": 100.0, "CDG": 200.0, "AMS": 200.0}
    C = {"LHR": 80.0, "LGW": 10.0, "CDG": 20.0, "AMS": 20.0}
    rec, red, sup = cj.redistribute_overlapping(spill, K, C, cat, theta)
    assert abs(rec["LGW"] - 6.0) < 1e-9          # od_share x pool via surface
    assert abs(rec["CDG"] - 3.0) < 1e-9          # 0.75 x network share of 4.0
    assert abs(rec["AMS"] - 1.0) < 1e-9
    assert abs(red - 10.0) < 1e-9 and sup < 1e-9


def test_nested_loader_and_meta(tmp_path):
    import json as j
    from avia_forecast.capacity import catchment_join as cj
    (tmp_path / cj.QSI_FILE).write_text(j.dumps({
        "meta": {"vintage": "QSI-CATCH-2026.1"},
        "NTE": {"od_share": 0.9,
                "surface": {"members": ["NTE", "RNS"], "weights": {"RNS": 1.0},
                            "access_penalty_min": {"RNS": 60}},
                "network": {"members": ["CDG"], "weights": {"CDG": 1.0}},
                "flags": ["road_network_ok"]}}))
    cat, meta, src = cj.load_catchments(str(tmp_path))
    assert src == "qsi_drive_time" and meta["vintage"] == "QSI-CATCH-2026.1"
    layers = cat["NTE"]["layers"]
    assert layers[0][0] == 0.9 and layers[1][0] == 0.1 - 0.0 or abs(layers[1][0] - 0.1) < 1e-9
    assert cat["NTE"]["penalties"]["surface_access_penalty_min"] == {"RNS": 60}

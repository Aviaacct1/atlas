"""Gated per-airport elasticity ladder (Fable review 4). Author: Avia Solutions.
Airport-own elasticity applies only when reliable AND connecting share is low (terminal ~ O&D);
hubs and unreliable fits fall back to the country value."""
from avia_forecast import global_demand as gd


def test_airport_elasticity_gate(monkeypatch):
    monkeypatch.setattr(gd, "_AIR_REG", {
        "AAA": {"bG_est": 1.3, "reliable": True},    # O&D-dominant, reliable -> use own
        "BBB": {"bG_est": 3.0, "reliable": True},    # reliable but a hub -> hold back
        "CCC": {"bG_est": 1.4, "reliable": False},   # unreliable -> country
    })
    monkeypatch.setattr(gd, "_AIR_CX", {"AAA": 0.10, "BBB": 0.46, "CCC": 0.10})
    assert gd._airport_applied_bG("AAA") == 1.3      # applied, within bound
    assert gd._airport_applied_bG("BBB") is None     # connecting share > 0.25 -> not applied
    assert gd._airport_applied_bG("CCC") is None     # fails reliability -> not applied
    assert gd._airport_applied_bG("ZZZ") is None     # not estimated


def test_gate_clamps_own_estimate(monkeypatch):
    monkeypatch.setattr(gd, "_AIR_REG", {"HUBLIKE": {"bG_est": 2.9, "reliable": True}})
    monkeypatch.setattr(gd, "_AIR_CX", {"HUBLIKE": 0.05})   # low cx so it IS applied...
    v = gd._airport_applied_bG("HUBLIKE")
    lo, hi = gd.get("global_drivers.bG_applied_bounds", [0.6, 2.2])
    assert v is not None and lo <= v <= hi           # ...but still clamped to the book bound

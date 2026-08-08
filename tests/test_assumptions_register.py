"""O-13 acceptance: the resolved assumptions register is a first-class export on both a Zagreb
deliverable and a dashboard airport page, and the licence filter passes for each (while blocking raw
licensed source data). Author: Avia Solutions."""
from avia_forecast.airports import instance
from avia_forecast.outputs import licence


def test_instance_register_exposes_inputs_reasons_and_passes_licence():
    cfg = instance.load("zagreb")
    reg = instance.assumptions_register(cfg, overrides={
        "domUplift": 0.005,
        "ytdTrim": {"trims": {"2026": 4000000}, "taper_years": 3, "reason": "YTD-JUN"}})
    groups = {r["group"] for r in reg["rows"]}
    assert {"base_composition", "market", "carrier_block", "category", "override"} <= groups
    assert all("source" in r and "reason" in r for r in reg["rows"])
    ov = next(r for r in reg["rows"] if r["group"] == "override" and r["input"] == "ytdTrim")
    assert ov["reason"] == "YTD-JUN"
    ok, findings = licence.licence_filter(reg)
    assert ok, findings


def test_dashboard_airport_register_exposes_and_passes_licence():
    meta = {"coverage_source": "ACI-based", "connecting_share_method": "blend",
            "both_ends_gdp": True, "base_year": 2025}
    reg = instance.dashboard_airport_register(meta, "LHR")
    assert reg["airport"] == "LHR" and reg["rows"]
    ok, _ = licence.licence_filter(reg)
    assert ok


def test_licence_filter_blocks_raw_source_data():
    bad = {"airport": "ZAG", "sabre_itineraries": [{"o": "ZAG", "d": "LHR", "pax": 123}]}
    ok, findings = licence.licence_filter(bad)
    assert not ok and findings


def test_output_rows_carries_register_and_passes_licence():
    o = instance.output_rows(instance.load("zagreb"))
    assert "assumptions_register" in o
    ok, _ = licence.licence_filter(o["assumptions_register"])
    assert ok

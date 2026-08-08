"""O-9 acceptance: client-model verification harness. Cross-checks headline series across engine,
client output tab, working sheets and published actuals, and flags the broken 007 output tab (circa
46% low by 2045 vs the working sheets) automatically, before calibration. Author: Avia Solutions."""
from avia_forecast.airports import instance


def test_harness_flags_broken_output_tab():
    # the 007 story: OUTPUT tab is ~46% low by 2045 vs the client's WORKING sheets (which are right)
    refs = {"total": {
        "working_sheets":    {2025: 4094081, 2035: 6000000, 2045: 8270412},
        "output_tab":        {2025: 4094081, 2035: 5400000, 2045: 4470000},
        "published_actuals": {2025: 4094081},
    }}
    flags = instance.verify(refs, tol=0.02)
    assert any(f["series"] == "total" and f["year"] == 2045 and f["source"] == "output_tab" and not f["ok"]
               for f in flags)
    f2045 = next(f for f in flags if f["year"] == 2045 and f["source"] == "output_tab")
    assert f2045["truth_source"] == "working_sheets" and f2045["delta"] < -0.4   # ~ -46%
    # near-year output tab agrees with actuals -> not flagged
    assert all(f["ok"] for f in flags if f["year"] == 2025)


def test_verify_instance_multi_series_and_gate():
    cfg = instance.load("zagreb")
    fc = instance.forecast(cfg)
    client = {"international": {"output_tab": {2040: fc[2040]["international"] * 0.5}}}
    flags, ok = instance.verify_instance(cfg, client, tol=0.02)
    assert not ok
    assert any(f["series"] == "international" and f["source"] == "output_tab" and not f["ok"] for f in flags)


def test_verify_instance_clean_when_client_agrees():
    cfg = instance.load("zagreb")
    fc = instance.forecast(cfg)
    client = {"total": {"working_sheets": {y: fc[y]["total"] for y in (2030, 2040)}}}
    flags, ok = instance.verify_instance(cfg, client, tol=0.02)
    assert ok

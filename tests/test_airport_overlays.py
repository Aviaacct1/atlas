"""O-8 acceptance (surface): headwind overlay type, first-class categories, landed tonnage, monthly
seasonality with winter uplift, and an auto-listed assumptions table, all in the generic instance
surface. Zagreb's totals are unchanged (its headwinds are embedded in the calibrated ramp).
Author: Avia Solutions."""
from avia_forecast.airports import instance


def test_headwind_compounds_from_start_with_part_year_weight():
    cfg = {"meta": {"base_year": 2025, "horizon": 2030},
           "markets": {"m": {"elasticity": 1.0, "base_weight": 1.0}},
           "gdp_index": {"m": {str(y): 1.0 for y in range(2025, 2031)}},   # flat GDP -> flat organic
           "base": {"total": 1000.0, "international": 1000.0, "domestic": 0, "transit": 0,
                    "non_lcc": 1000.0, "lcc": 0, "commercial_atm": 10.0},
           "headwinds": [{"name": "charge", "annual_drag": -0.01, "start_year": 2026,
                          "part_year_weight": 0.5, "reason": "HEADWIND"}]}
    fc = instance.forecast(cfg)
    assert fc[2025]["total"] == 1000.0                                   # base year unaffected
    assert abs(fc[2026]["total"] - 1000.0 * (0.99 ** 0.5)) < 1e-6        # first year at half weight
    assert fc[2030]["total"] < fc[2026]["total"]                        # compounds


def test_landed_tonnage_scales_with_atm():
    cfg = instance.load("zagreb"); fc = instance.forecast(cfg)
    bt = cfg["base"]["landed_tonnage"]; ba = cfg["base"]["commercial_atm"]
    for y in (2030, 2045):
        assert abs(fc[y]["landed_tonnage"] - bt * (fc[y]["commercial_atm"] / ba)) < 1.0


def test_monthly_winter_uplift_sums_to_one_and_shifts():
    cfg = instance.load("zagreb")
    base = instance.monthly_shares(cfg, 0.0); up = instance.monthly_shares(cfg, 0.20)
    assert abs(sum(up.values()) - 1.0) < 1e-9
    assert up[1] > base[1]        # January (winter) rises
    assert up[7] < base[7]        # July (summer) falls after renormalising


def test_assumptions_table_auto_lists():
    rows = instance.assumptions_table(instance.load("zagreb"))
    cats = {r["category"] for r in rows}
    assert {"base_composition", "market", "carrier_block", "category", "seasonality"} <= cats


def test_zagreb_007_unchanged_by_surface():
    assert all(r[-1] for r in instance.benchmark_check(instance.load("zagreb")))

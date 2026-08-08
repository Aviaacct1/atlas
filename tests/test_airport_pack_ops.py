"""O-7 acceptance: ACTUALS-REBASE and YTD-TRIM as reason-coded pack operations on instance.forecast.
A rebase anchors the base year to a published actual and regrows at model ratios; a YTD trim sets a
near year to its YTD value and tapers back to the model path; both compose and preserve adding-up,
all as pack entries with no script edit. Author: Avia Solutions."""
from avia_forecast.airports import instance


def test_actuals_rebase_scales_whole_series_preserving_growth():
    cfg = instance.load("zagreb")
    base = instance.forecast(cfg)
    actual = 4_200_000
    reb = instance.forecast(cfg, {"actualsRebase": {"base_actual": actual, "reason": "ACTUALS-REBASE"}})
    assert abs(reb[2025]["total"] - actual) < 1.0
    k = actual / base[2025]["total"]
    for y in (2030, 2040, 2048):
        assert abs(reb[y]["total"] - base[y]["total"] * k) < 1.0     # growth ratios preserved


def test_ytd_trim_hits_target_and_tapers_back():
    cfg = instance.load("zagreb")
    base = instance.forecast(cfg)
    target = base[2026]["total"] * 0.95
    tr = instance.forecast(cfg, {"ytdTrim": {"trims": {2026: target}, "taper_years": 3, "reason": "YTD-JUN"}})
    assert abs(tr[2026]["total"] - target) < 1.0                     # hits the YTD target
    assert abs(tr[2029]["total"] - base[2029]["total"]) < 1.0        # tapered fully back by +3
    assert tr[2027]["total"] < base[2027]["total"]                   # still trimmed in between


def test_rebase_and_trim_compose_and_add_up():
    cfg = instance.load("zagreb")
    base = instance.forecast(cfg)
    pack = {"actualsRebase": {"base_actual": base[2025]["total"] * 1.02, "reason": "ACTUALS-REBASE"},
            "ytdTrim": {"trims": {2026: base[2026]["total"] * 1.02 * 0.97}, "taper_years": 3, "reason": "YTD-JUN"}}
    out = instance.forecast(cfg, pack)
    assert abs(out[2025]["total"] - base[2025]["total"] * 1.02) < 2.0
    assert abs(out[2026]["total"] - base[2026]["total"] * 1.02 * 0.97) < 2.0
    for y in (2026, 2030):
        assert abs(out[y]["international"] + out[y]["domestic"] + out[y]["transit"] + out[y]["ga"] - out[y]["total"]) < 2.0


def test_no_pack_reproduces_007():
    assert all(r[-1] for r in instance.benchmark_check(instance.load("zagreb")))

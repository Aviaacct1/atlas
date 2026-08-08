"""O-14 acceptance (engine half): Benchmark mode exhibit. The independent engine view vs a subject
third-party forecast, gap by year with a base/growth attribution; fed the broken 007 output tab
(~46% below the independent view by 2045) it reproduces the Zagreb gap finding and passes the licence
filter. Author: Avia Solutions."""
from avia_forecast.airports import instance
from avia_forecast.outputs import licence


def test_benchmark_exhibit_reproduces_46pct_understatement():
    cfg = instance.load("zagreb")
    fc = instance.forecast(cfg)
    independent = {y: fc[y]["total"] for y in fc}
    hz = cfg["meta"]["horizon"]
    # broken output tab, ~46% below the independent view from 2045 to the horizon
    subject = {2025: independent[2025], 2045: independent[2045] * 0.54, hz: independent[hz] * 0.54}
    ex = instance.benchmark_exhibit(independent, subject)
    d2045 = next(r for r in ex["rows"] if r["year"] == 2045)
    assert abs(d2045["subject_vs_independent"] + 0.46) < 0.02          # the 46% understatement at 2045
    assert ex["headline"]["subject_vs_independent"] < -0.4            # worst-year understatement is large
    assert abs(ex["attribution"]["base_year_level"]) < 1e-6          # base years agree
    assert ex["attribution"]["growth"] > 0.5                         # whole gap attributes to growth
    ok, _ = licence.licence_filter(ex)
    assert ok


def test_benchmark_attribution_identity():
    ind = {2025: 100.0, 2045: 200.0}
    sub = {2025: 90.0, 2045: 150.0}
    a = instance.benchmark_exhibit(ind, sub)["attribution"]
    assert abs((a["base_year_level"] + a["growth"]) - a["total_log_gap"]) < 1e-9

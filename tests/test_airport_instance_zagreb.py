"""Zagreb as a configured engine instance reproduces Model 007 within tolerance,
and a cockpit override moves the forecast. Author: Avia Solutions."""
from avia_forecast.airports import instance


def test_zagreb_reproduces_007_within_2pct():
    cfg = instance.load("zagreb")
    rows = instance.benchmark_check(cfg, tol=0.02)
    assert rows, "no benchmark years in config"
    for y, mv, bv, d, ok in rows:
        assert ok, f"{y}: engine {mv:.0f} vs 007 {bv} = {d:+.2%} outside 2%"


def test_zagreb_override_moves_total():
    cfg = instance.load("zagreb")
    base = instance.forecast(cfg)[2045]["total"]
    hi = instance.forecast(cfg, overrides={"lccSpot": {"2026": 1797000, "2045": 6000000, "2048": 6500000}})[2045]["total"]
    assert hi > base * 1.05


def test_zagreb_identities():
    cfg = instance.load("zagreb")
    fc = instance.forecast(cfg)
    for y in (2030, 2040, 2048):
        r = fc[y]
        assert abs((r["international"] + r["domestic"] + r["transit"] + r["ga"]) - r["total"]) < 1.0

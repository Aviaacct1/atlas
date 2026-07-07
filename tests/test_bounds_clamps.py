"""Applied-elasticity and GDP-tail clamps (Fable review issues 1 and 7). Author: Avia Solutions."""
from avia_forecast import global_demand as gd


def test_applied_bG_never_exceeds_book_bound():
    lo, hi = gd.get("global_drivers.bG_applied_bounds", [0.6, 2.2])
    for raw in (3.48, 3.15, 2.9, hi + 1, lo - 1, -5, 10):
        v = gd._clamp_bG(raw)
        assert lo <= v <= hi, f"{raw} clamped to {v}, outside [{lo},{hi}]"
    # in-band values pass through unchanged
    assert gd._clamp_bG(1.3) == 1.3


def test_gdp_tail_growth_is_clamped(monkeypatch):
    # synthetic country with a plausible path then a spiky final OEF year
    oef = {}
    lvl = 100.0
    for y in range(2025, 2050):
        lvl *= 1.03
        oef[str(y)] = lvl
    oef["2050"] = oef["2049"] * 1.60          # 60% spike in the final OEF year
    monkeypatch.setattr(gd, "_oef_gdp", lambda: {"XX": oef})
    years = list(range(2025, 2061))
    idx = gd._gdp_index("Europe", years, country="XX")
    # beyond the OEF horizon (2051..2060) the year-on-year growth must be clamped to <= 4%
    tail = idx[years.index(2051):]
    for a, b in zip(tail, tail[1:]):
        assert (b / a - 1.0) <= 0.04 + 1e-9, "extension growth exceeded the 4% clamp"

"""Airport-set scope rule (Phase 1; John's >2m / top-80% / 500k-goal rule).
Author: Avia Solutions."""
import pytest

from avia_forecast.scope import selection as sc
from avia_forecast.config import get


def test_floor_includes_large_airport_below_coverage():
    # One 3m airport plus a long tail; the 3m clears the 2m floor regardless of coverage
    rows = [("BIG", "XX", 3_000_000)] + [(f"S{i}", "XX", 100_000) for i in range(40)]
    res = sc.select_country("XX", [(i, p) for i, c, p in rows])
    assert any(a.iata == "BIG" and a.reason == "floor" for a in res.modelled)


def test_coverage_set_is_smallest_top_set_reaching_target():
    # 60,30,10 (m). target 0.80: 60 -> .60, +30 -> .90 >= .80 stop. So {A,B} modelled, C residual.
    aps = [("A", 60), ("B", 30), ("C", 10)]
    # push pax below the 2m floor so only the coverage rule can act
    aps = [(i, p) for i, p in aps]  # values in 'm' units but floor default 2e6; use raw < floor
    res = sc.select_country("YY", aps, inclusion_floor=1e9, goal_floor=1e9)
    got = {a.iata for a in res.modelled}
    assert got == {"A", "B"}
    assert res.residual_iata == "YY_RES" and res.residual_count == 1
    assert res.residual_pax == 10


def test_residual_preserves_national_total():
    aps = [("A", 60), ("B", 30), ("C", 8), ("D", 2)]
    res = sc.select_country("ZZ", aps, inclusion_floor=1e9, goal_floor=1e9)
    modelled_pax = sum(a.pax for a in res.modelled)
    assert modelled_pax + res.residual_pax == pytest.approx(res.national_pax)


def test_goal_gap_flagged_when_excluded_airport_above_goal_floor():
    # coverage take the top; a 700k airport excluded but above the 500k goal floor -> gap
    rows = [("H", 20_000_000), ("M", 6_000_000), ("G", 700_000), ("T", 100_000)]
    res = sc.select_country("GB", rows)   # defaults: floor 2m, target .80, goal 500k
    # H alone is 20/26.8 = .746; +M -> .970 stop. G and T excluded. G(700k) > 500k -> gap
    assert res.goal_gap_count == 1
    assert res.residual_count == 2


def test_uk_shaped_multi_country_apply():
    rows = [
        ("LHR", "GB", 83_000_000), ("LGW", "GB", 46_000_000), ("MAN", "GB", 28_000_000),
        ("STN", "GB", 28_000_000), ("LTN", "GB", 16_000_000), ("EDI", "GB", 14_000_000),
        ("BHX", "GB", 11_000_000), ("BRS", "GB", 9_000_000), ("GLA", "GB", 7_000_000),
        ("EXT", "GB", 900_000), ("NQY", "GB", 400_000),
        ("CDG", "FR", 70_000_000), ("ORY", "FR", 33_000_000), ("NCE", "FR", 14_000_000),
        ("LIL", "FR", 2_200_000), ("RNS", "FR", 800_000),
    ]
    out = sc.select_airports(rows)
    assert set(out) == {"GB", "FR"}
    gb = out["GB"]
    # every UK airport at/above 2m is modelled by the floor
    modelled_gb = {a.iata for a in gb.modelled}
    for big in ("LHR", "LGW", "MAN", "STN", "LTN", "EDI", "BHX", "BRS", "GLA"):
        assert big in modelled_gb
    # sub-2m EXT/NQY fall to the residual; EXT(900k) > 500k goal -> gap
    assert gb.residual_iata == "GB_RES"
    assert "EXT" not in modelled_gb and "NQY" not in modelled_gb
    assert gb.goal_gap_count == 1
    assert gb.coverage > 0.98            # UK modelled set covers almost all pax

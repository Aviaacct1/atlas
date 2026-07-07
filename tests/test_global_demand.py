"""Phase 3a global demand run. Author: Avia Solutions."""
import json, os
import pytest

from avia_forecast import global_demand as gd

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _fixture():
    # tiny synthetic 2-country world so the test needs no external files
    base_od = {
        "AAA": {"Domestic": 10.0, "EU+UK": 4.0, "North America": 2.0},  # mature country
        "BBB": {"Domestic": 8.0, "Asia Pacific": 3.0},               # emerging country
    }
    meta = {
        "AAA": {"country": "GB", "region": "EU+UK", "term_out_m": 16.0},
        "BBB": {"country": "IN", "region": "Asia Pacific", "term_out_m": 11.0},
    }
    return base_od, meta


def test_base_year_world_equals_sum_of_base_od():
    base_od, meta = _fixture()
    r = gd.run_global(base_od=base_od, airport_meta=meta, use_propensity=False)
    total = sum(sum(v.values()) for v in base_od.values())
    assert r.world[r.years[0]] == pytest.approx(total, rel=1e-9)


def test_world_grows_over_horizon():
    base_od, meta = _fixture()
    r = gd.run_global(base_od=base_od, airport_meta=meta, use_propensity=False)
    assert r.world[r.years[-1]] > r.world[r.years[0]]
    assert r.world_cagr > 0


def test_emerging_region_outgrows_mature():
    base_od, meta = _fixture()
    r = gd.run_global(base_od=base_od, airport_meta=meta, use_propensity=False)
    def cagr(s): return (s[r.years[-1]] / s[r.years[0]]) ** (1 / (r.years[-1] - r.years[0])) - 1
    assert cagr(r.by_region["Asia Pacific"]) > cagr(r.by_region["EU+UK"])


def test_propensity_damps_growth():
    base_od, meta = _fixture()
    on = gd.run_global(base_od=base_od, airport_meta=meta, use_propensity=True)
    off = gd.run_global(base_od=base_od, airport_meta=meta, use_propensity=False)
    # damping cannot raise long-run demand; for the mature GB market it lowers it
    assert on.world[on.years[-1]] <= off.world[off.years[-1]] + 1e-6


def test_real_global_data_runs_and_is_plausible():
    if not os.path.exists(os.path.join(DATA, "global_base_od_2025.json")):
        pytest.skip("global base-year data not built")
    r = gd.run_global()
    assert 0.02 < r.world_cagr < 0.06                 # plausible world pax CAGR
    assert r.world[2025] > 2500 and r.world[2050] > r.world[2025]

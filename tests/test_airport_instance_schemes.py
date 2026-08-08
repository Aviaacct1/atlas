"""O-3 acceptance: instance.forecast runs an arbitrary market scheme through the SAME code path
as Zagreb's five named markets. A region-scheme airport, including a market whose GDP index is
composed from a recipe rather than precomputed, must forecast without any airport-specific branch.
Author: Avia Solutions."""
from avia_forecast.airports import instance


def _region_scheme_cfg():
    yrs = [str(y) for y in range(2025, 2031)]
    def idx(g):
        return {y: round(g ** i, 6) for i, y in enumerate(yrs)}
    return {
        "meta": {"base_year": 2025, "horizon": 2030},
        "domestic_market": "home_region",
        "markets": {
            "home_region": {"elasticity": 0.9, "base_weight": 1_000_000, "members": ["A", "B"]},
            "far_region": {"elasticity": 1.1, "base_weight": 500_000,
                           "gdp_recipe": {"members": {"C": 0.5, "D": 0.5}}},
        },
        "gdp_index": {
            "home_region": idx(1.02),
            "C": idx(1.03), "D": idx(1.05),      # far_region has NO precomputed series - must compose
        },
        "base": {"total": 1_500_000, "international": 900_000, "domestic": 600_000,
                 "transit": 0, "non_lcc": 1_500_000, "lcc": 0, "commercial_atm": 12_000},
        "demand": {"domestic_uplift_pa": 0.0},
        "conversions": {"upgauge_pa": 0.0},
    }


def test_region_scheme_runs_same_code_path():
    fc = instance.forecast(_region_scheme_cfg())
    assert set(fc) == set(range(2025, 2031))
    assert fc[2025]["total"] == 1_500_000
    assert fc[2030]["total"] > fc[2025]["total"]          # grows on the composed + direct markets
    # composite market actually contributed: far_region (recipe C,D) must resolve or organic KeyErrors
    assert fc[2030]["international"] > 0


def test_zagreb_still_reproduces_007():
    cfg = instance.load("zagreb")
    rows = instance.benchmark_check(cfg, tol=0.02)
    assert rows and all(ok for *_, ok in rows), [r for r in rows if not r[-1]]

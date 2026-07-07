"""Impact table + Avia chart format acceptance tests (Cockpit build update F). Author: Avia Solutions."""
import pytest
from avia_forecast.outputs import impact, chart_format as cf


def _series(v0, g):
    return {y: v0 * (1 + g) ** (y - 2025) for y in range(2025, 2051)}


def test_F1_impact_table_spot_years_cagrs_and_vs_baseline():
    run = {"total_pax": _series(100.0, 0.02), "cap_requirement": _series(5.0, 0.05)}
    base = {"total_pax": _series(100.0, 0.015), "cap_requirement": _series(5.0, 0.04)}
    t = impact.build_impact_table(run, 2025, baseline=base)

    assert t["spot_years"] == [2025, 2030, 2035, 2040, 2045, 2050]
    assert len(t["cagr_periods"]) == 3
    tp = t["metrics"]["total_pax"]
    assert tp["spot"][2025] == pytest.approx(100.0)
    assert tp["cagr"]["2025-2030"] == pytest.approx(0.02, abs=1e-9)     # BY->BY+5 CAGR
    # signed vs-baseline: run grows faster, so positive and widening
    assert tp["vs_baseline"][2025] == pytest.approx(0.0)
    assert tp["vs_baseline"][2050] > tp["vs_baseline"][2030] > 0
    assert set(impact.ROWS) >= {"total_atm", "cargo_tonnage", "ga_pax", "transfer_pax"}


def test_F2_source_line_singular_and_palette_pinned():
    assert cf.source_line() == "Source: OAG, AviaSolutions analysis"
    assert cf.validate_source_line("Source: OAG, AviaSolutions analysis")
    assert not cf.validate_source_line("Sources: OAG, AviaSolutions analysis")   # the common error
    assert cf.PINNED_PALETTE == ["156082", "E97132", "196B24", "0F9ED5", "A02B93", "4EA72E"]
    assert cf.SIZES["heading"] == 20 and cf.SIZES["axis"] == 18


def test_F4_author_stamp_and_year_labels():
    assert cf.AUTHOR == "Avia Solutions"
    assert cf.year_label(2025, 2025) == "2025A" and cf.year_label(2026, 2025) == "2026F"

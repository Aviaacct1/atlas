"""Capacity register: two-field K derivation, the seed-CSV loader and the ATFM
validation proxy (Capacity Register - Design and Sourcing v0.1). Author: Avia Solutions."""
import math
from pathlib import Path

import pytest

from avia_forecast.capacity import register as reg
from avia_forecast.capacity import spill as sp
from avia_forecast.aggregate import reconcile as rec
from avia_forecast.config import get

SEED = Path(__file__).resolve().parent.parent / "data" / "capacity_register_seed.csv"


def test_grade_a_derives_annual_k_from_rate():
    # GRU: 45 mvts/hr x 5840 h x default seats x default LF, in m pax/yr
    oh, spm, lf = 5840, get("capacity_register.seats_per_mvt_default"), get("capacity_register.load_factor_default")
    expected_m = 45 * oh * spm * lf / 1e6
    got = reg.derive_k_grade_a(45, None, None, None)
    assert got == pytest.approx(expected_m)


def test_grade_b_takes_design_directly():
    row = reg.derive_row({"iata": "DEL", "country": "IN", "K_grade": "B",
                          "design_annual_pax_m": "100"})
    assert row.k_annual_pax_m == pytest.approx(100.0)
    # practical capacity applies the peak-spreading allowance and scales to pax/yr
    allowance = get("capacity.peak_spreading_allowance")
    assert row.practical_capacity == pytest.approx(100.0 * allowance * 1e6)


def test_grade_c_is_unconstrained():
    row = reg.derive_row({"iata": "SVO", "country": "RU", "K_grade": "C"})
    assert row.practical_capacity is None
    # capacity_for -> 0.0 -> airport_solve treats as no register entry (unconstrained)
    K = reg.capacity_for(row)
    assert K == 0.0
    solve = sp.airport_solve(5_000_000.0, K)
    assert solve.retention == 1.0 and solve.spill == 0.0


def test_committed_steps_parse():
    row = reg.derive_row({"iata": "DXB", "country": "AE", "K_grade": "B",
                          "design_annual_pax_m": "90", "committed_steps": "2031:+25"})
    assert row.committed_steps == [[2031, 25.0]]


def test_seed_loads_and_grades_split():
    r = reg.load_register(SEED)
    assert "GRU" in r and "DXB" in r and "SVO" in r
    assert r["GRU"].k_grade == "A"
    assert r["DXB"].k_grade == "B" and r["DXB"].k_annual_pax_m == pytest.approx(90.0)
    assert r["SVO"].k_grade == "C" and r["SVO"].practical_capacity is None
    # UK grade-A seeds carry no declared rate yet (to-extract) -> unconstrained until sourced
    assert r["LHR"].k_grade == "A" and r["LHR"].practical_capacity is None


def test_atfm_flags_unconstrained_but_delayed():
    # grade C airport with chronic arrival delay -> wrong register entry, flagged
    f = rec.check_atfm_validation("XXX", "C", has_k=False, delay_per_arr=3.0)
    assert f.flagged
    # a graded airport with real K is not flagged even if delayed (delay is expected)
    f2 = rec.check_atfm_validation("DEL", "B", has_k=True, delay_per_arr=3.0)
    assert not f2.flagged
    # an unconstrained airport with no meaningful delay is fine
    f3 = rec.check_atfm_validation("SVO", "C", has_k=False, delay_per_arr=0.0)
    assert not f3.flagged

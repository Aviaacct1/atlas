"""Parity harness tests (Method Spec 10, build decision D9). Author: Avia Solutions."""
from pathlib import Path
import pandas as pd
import pytest

from avia_forecast import paths
from avia_forecast.parity import harness

# Jess Rowden's frozen template lives in the shared project folder and resolves through
# paths.py. It was addressed as parents[2] until 8 August 2026, which is C:\Avia on the
# Dev PC and C:\src once the repository moves, and is where the workbook is in neither
# case, so these three tests skipped silently from the day they were written.
WORKBOOK = Path(paths.PILOT_WORKBOOK)


@pytest.mark.skipif(not WORKBOOK.exists(), reason="pilot workbook not present")
def test_reads_output_contract_anchor():
    df = harness.read_output_contract(WORKBOOK)
    total25 = df[(df.metric == "od_pax_u_total") & (df.year == 2025)]["value"].iloc[0]
    assert round(total25, 2) == 23.78          # handover anchor
    assert set(df["year"]) >= {2000, 2025, 2026}
    assert df["metric"].nunique() >= 12         # all contract metrics present


@pytest.mark.skipif(not WORKBOOK.exists(), reason="pilot workbook not present")
def test_self_parity_is_exact():
    df = harness.read_output_contract(WORKBOOK)
    report = harness.compare(df, df.copy())
    assert harness.parity_passes(report)
    assert harness.summarise(report)["max_rel_diff"] == 0.0


@pytest.mark.skipif(not WORKBOOK.exists(), reason="pilot workbook not present")
def test_detects_diff_at_tolerance_boundary():
    df = harness.read_output_contract(WORKBOOK)
    py = df.copy()
    # perturb one non-zero cell by 0.01% (10x the 0.001% tolerance)
    idx = py.index[(py["value"].abs() > 1)][0]
    py.loc[idx, "value"] *= 1.0001
    report = harness.compare(df, py)
    assert not harness.parity_passes(report)
    assert harness.summarise(report)["failing"] == 1
    # a perturbation below tolerance (0.0001%) still passes
    py2 = df.copy(); py2.loc[idx, "value"] *= 1.000001
    assert harness.parity_passes(harness.compare(df, py2))

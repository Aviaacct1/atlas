"""First unit test of the estimation module: the synthetic worked examples of
Elasticity Design v0.1 section 7, computed end to end. This keeps the machinery
permanently checked against known truth on every build.

Note on reproducibility: the design document reported one specific noise draw
(clean cell bG 1.391, bF -0.586). The draw's seed was not recorded, so these
tests fix their own seeds. Seed 58 reproduces the documented draw's character
(bG 1.394, bF -0.574); the Monte Carlo test is the real evidence that the
estimator is unbiased around the true parameters rather than tuned to one draw.

Author: Avia Solutions.
"""
import numpy as np
import pytest

from avia_forecast.estimate import synthetic, level1, reliability, select, maturity
from avia_forecast.config import get

DOC_SEED = 58            # reproduces the design document's clean-cell draw character
BF_PRIOR = -0.60         # Level 3 Long Haul prior used by the T6 cross-check


# ---- 7.1 Airport that earns its own elasticities ----

def test_clean_cell_recovers_truth_and_passes_all_tests():
    df = synthetic.make_clean_cell(seed=DOC_SEED)
    fit = level1.fit_cell(df)
    # Recovery near known truth (true bG 1.30, bF -0.60, gamma ln 0.45 = -0.799)
    assert 1.20 <= fit.bG <= 1.55
    assert -0.85 <= fit.bF <= -0.35
    assert -0.95 <= fit.gamma <= -0.65
    assert fit.r2 >= 0.95
    trail = reliability.run_tests(fit, df, bF_prior=BF_PRIOR, avg_flow_mppa=4.0)
    assert trail.all_pass, trail
    applied = select.select(fit, trail, level3=(1.3, -0.5))
    assert applied.level == 1
    glo, ghi = get("applied_bounds.bG"); flo, fhi = get("applied_bounds.bF")
    assert glo <= applied.bG <= ghi and flo <= applied.bF <= fhi


def test_estimator_is_unbiased_monte_carlo():
    N = 300
    bg = np.empty(N); bf = np.empty(N); gm = np.empty(N); passes = 0
    for s in range(N):
        d = synthetic.make_clean_cell(seed=s)
        f = level1.fit_cell(d)
        t = reliability.run_tests(f, d, bF_prior=BF_PRIOR, avg_flow_mppa=4.0)
        bg[s], bf[s], gm[s] = f.bG, f.bF, f.gamma
        passes += int(t.all_pass)
    assert abs(bg.mean() - 1.30) < 0.03, bg.mean()
    assert abs(bf.mean() + 0.60) < 0.05, bf.mean()
    assert abs(gm.mean() + 0.799) < 0.03, gm.mean()
    assert passes / N >= 0.90


# ---- 7.2 Supply-shocked airport: the rule catching what it exists to catch ----

def test_base_opening_naive_rejected_by_T2():
    df = synthetic.make_base_opening_cell(seed=DOC_SEED)
    fit = level1.fit_cell(df)                       # naive: ignore the 2013 event
    trail = reliability.run_tests(fit, df, bF_prior=BF_PRIOR, avg_flow_mppa=4.0)
    assert trail.T2 is False                        # base opening masquerades as huge elasticities
    assert not trail.all_pass
    # Falls back to Level 2, unattended
    applied = select.select(fit, trail, level2=(1.1, -0.7), level3=(1.3, -0.5))
    assert applied.level == 2


def test_base_opening_with_event_dummy_rescued():
    df = synthetic.make_base_opening_cell(seed=DOC_SEED)
    naive = level1.fit_cell(df)                     # for comparison
    fit = level1.fit_cell(df, event_cols=["E2013"])
    trail = reliability.run_tests(fit, df, bF_prior=BF_PRIOR, avg_flow_mppa=4.0, event_cols=["E2013"])
    # Dummying the structural break brings the estimate back near truth (1.30);
    # the naive fit was far above it. Overshoot is the same irreducible-noise order
    # as the clean cell (design doc: 7% even in the clean case).
    assert abs(fit.bG - 1.30) < 0.20                # recovers true GDP elasticity
    assert abs(fit.bG - 1.30) < abs(naive.bG - 1.30)     # much closer than naive
    assert abs(fit.event_shift["E2013"] - 0.85) < 0.12   # recovers the +85% shift
    assert trail.all_pass, trail
    applied = select.select(fit, trail, level3=(1.3, -0.5))
    assert applied.level == 1                        # upgraded from safely-pooled to accurately-individual


# ---- selection + clipping + maturity ----

def test_selection_falls_through_to_level3():
    # No Level 1 fit and no Level 2: Level 3 default must always catch.
    applied = select.select(level1_fit=None, level1_trail=None, level3=(1.8, -0.5))
    assert applied.level == 3 and applied.bG <= get("applied_bounds.bG")[1]


def test_applied_bounds_clip():
    a = select.clip_applied(bG=3.0, bF=-2.0, level=1)   # both outside bounds
    glo, ghi = get("applied_bounds.bG"); flo, fhi = get("applied_bounds.bF")
    assert a.bG == ghi and a.bF == flo and a.clipped


def test_maturity_decay_monotone_to_floor():
    yrs = range(2025, 2056)
    path = maturity.decay_path(bG_T0=1.8, segment="Long Haul", years=yrs)
    assert path[0] == pytest.approx(1.8, abs=1e-9)
    assert path[-1] > get("maturity.bG_inf.Long Haul")   # approaches but not yet at floor
    assert np.all(np.diff(path) < 0)                     # strictly declining

"""Reliability rule T1-T6 and the CAGR cross-check (Method Spec 4.4,
Elasticity Design 2.1). Thresholds come entirely from the assumptions book.
Author: Avia Solutions.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

from ..config import get


@dataclass
class TestTrail:
    T1: bool
    T2: bool
    T3: bool
    T4: bool
    T5: bool
    T6: bool
    bG_implied: float
    t6_window: tuple

    @property
    def all_pass(self) -> bool:
        return all([self.T1, self.T2, self.T3, self.T4, self.T5, self.T6])


def _longest_clean_window(years, lo, hi, excluded):
    """Longest contiguous run of in-range years containing no excluded year."""
    best, run = [], []
    for y in sorted(years):
        if not (lo <= y <= hi) or y in excluded:
            run = []
            continue
        run = run + [y] if (run and y == run[-1] + 1) else [y]
        if len(run) > len(best):
            best = run
    return best


def cagr_cross_check(df: pd.DataFrame, bF_prior: float, bG_regression: float,
                     excluded_years=None):
    """T6. Returns (passes, bG_implied, (t1, t2)).

    `df` must carry P already adjusted for any estimated structural level shift,
    so the window can span the estimation period. Uses the Level 3 prior fare
    elasticity, not the estimated one, so a bad joint fit cannot vouch for itself
    (Elasticity Design 2.1)."""
    lo, hi = get("reliability.T6_default_window")
    excluded = set(get("estimation.pandemic_years")) | set(excluded_years or [])
    d = df.set_index("year")
    yrs = _longest_clean_window(list(d.index), lo, hi, excluded)
    if len(yrs) < 2:
        return False, float("nan"), (None, None)
    t1, t2 = min(yrs), max(yrs)
    lnP = np.log(d.loc[t2, "P"] / d.loc[t1, "P"])
    lnF = np.log(d.loc[t2, "F"] / d.loc[t1, "F"])
    lnG = np.log(d.loc[t2, "G"] / d.loc[t1, "G"])
    if lnG == 0:
        return False, float("nan"), (t1, t2)
    bG_implied = (lnP - bF_prior * lnF) / lnG
    ratio = bG_implied / bG_regression if bG_regression != 0 else float("inf")
    r_lo, r_hi = get("reliability.T6_cagr_ratio")
    return (r_lo <= ratio <= r_hi), float(bG_implied), (t1, t2)


def _structural_adjusted(df: pd.DataFrame, fit, event_cols) -> pd.DataFrame:
    """Divide P by (1 + estimated shift) over each structural event's active years,
    so the cross-check sees the demand series net of the modelled level shift."""
    d = df.copy()
    for c in (event_cols or []):
        shift = fit.event_shift.get(c, 0.0)
        d["P"] = d["P"] / np.where(d[c].astype(float) > 0, 1.0 + shift, 1.0)
    return d


def run_tests(fit, df: pd.DataFrame, *, bF_prior: float, avg_flow_mppa: float,
              cell_passes_history: bool = True, event_cols=None, fare_fixed=None) -> TestTrail:
    """Apply T1-T6 to a Level 1 fit. `fit` is a Level1Fit. `event_cols` are the
    structural event dummy columns present in df and the fit.

    When the fare elasticity is fixed at the segment value (Fable Part B: the
    restricted production Level 1), T1 and T2 test bG only; the bF sign and range
    tests move to Levels 2-3, where bF is actually estimated. `fare_fixed`
    defaults to the fit's own flag."""
    if fare_fixed is None:
        fare_fixed = getattr(fit, "fare_fixed", False)

    bG_rng = get("reliability.T2_range.bG")
    bF_rng = get("reliability.T2_range.bF")
    if fare_fixed:
        T1 = fit.bG > get("reliability.T1_signs.bG_gt")
        T2 = bG_rng[0] <= fit.bG <= bG_rng[1]
    else:
        T1 = (fit.bG > get("reliability.T1_signs.bG_gt")) and (fit.bF < get("reliability.T1_signs.bF_lt"))
        T2 = (bG_rng[0] <= fit.bG <= bG_rng[1]) and (bF_rng[0] <= fit.bF <= bF_rng[1])

    T3 = abs(fit.t_bG) >= get("reliability.T3_significance_min_abs_t")
    T4 = fit.r2 >= get("reliability.T4_fit_min_r2")

    T5 = (fit.n_obs >= get("reliability.T5_history.min_obs")) and \
         (avg_flow_mppa >= get("reliability.T5_history.min_avg_flow_mppa")) and cell_passes_history

    df_adj = _structural_adjusted(df, fit, event_cols)
    T6, bG_implied, window = cagr_cross_check(df_adj, bF_prior, fit.bG)

    return TestTrail(T1, T2, T3, T4, T5, T6, bG_implied, window)

"""Fare-elasticity strategy tests (Fable Part B): the supply-anomaly proof (B.4),
the restricted Level 1 regression, and V-FARE. Author: Avia Solutions."""
import numpy as np
import pytest

from avia_forecast.estimate import synthetic, level1, reliability, validate

TRUE_BF = -0.60
TRUE_BG = 1.30


def _fit_series(df, fare_col, dummies):
    d = df.rename(columns={fare_col: "F"})[["year", "P", "G", "F"]]
    return level1.fit_cell(d, dummies=dummies)


def test_B4_naive_on_observed_fares_mis_estimates_bF():
    # 2020-24 observed fares are supply-anomalous; demand followed normal fares.
    N = 200
    naive = np.array([_fit_series(synthetic.make_fare_anomaly_cell(seed=s), "F_obs", ("covid",)).bF
                      for s in range(N)])
    # naive is badly attenuated: fares look far less elastic than the truth
    assert naive.mean() > -0.35                     # nowhere near -0.60
    assert abs(naive.mean() - TRUE_BF) > 0.30       # a large, systematic error


def test_B4_recipe_recovers_bF():
    N = 200
    rec = np.array([_fit_series(synthetic.make_fare_anomaly_cell(seed=s), "F_est", ("covid", "supply")).bF
                    for s in range(N)])
    naive = np.array([_fit_series(synthetic.make_fare_anomaly_cell(seed=s), "F_obs", ("covid",)).bF
                      for s in range(N)])
    assert abs(rec.mean() - TRUE_BF) < 0.05                 # recovers the truth
    assert abs(rec.mean() - TRUE_BF) < abs(naive.mean() - TRUE_BF)   # far better than naive


def test_restricted_level1_recovers_bG_with_fare_fixed():
    df = synthetic.make_fare_anomaly_cell(seed=58)
    d = df.rename(columns={"F_est": "F"})[["year", "P", "G", "F"]]
    fit = level1.fit_cell_restricted(d, bF_segment=TRUE_BF, dummies=("covid", "supply"))
    assert fit.fare_fixed is True
    assert fit.bF == TRUE_BF                                 # fixed, not estimated
    assert abs(fit.bG - TRUE_BG) < 0.20                      # bG recovered on the fare-adjusted series (single-draw noise)
    # reliability re-scopes to bG only when the fare is fixed
    trail = reliability.run_tests(fit, d, bF_prior=TRUE_BF, avg_flow_mppa=4.0)
    assert trail.T1 and trail.T2                             # bG sign and range
    assert trail.all_pass


def test_restricted_regression_stabilises_bG_vs_unrestricted():
    # Fixing bF removes fare-GDP collinearity, so restricted bG has a tighter t.
    ts_r, ts_u = [], []
    for s in range(100):
        d = synthetic.make_fare_anomaly_cell(seed=s).rename(columns={"F_est": "F"})[["year", "P", "G", "F"]]
        ts_r.append(level1.fit_cell_restricted(d, bF_segment=TRUE_BF, dummies=("covid", "supply")).t_bG)
        ts_u.append(level1.fit_cell(d, dummies=("covid", "supply")).t_bG)
    assert np.mean(ts_r) > np.mean(ts_u)                    # more precise bG


def test_vfare_agreement_within_tolerance():
    r = validate.vfare_agreement(bF_observed=-0.62, bF_cost_driven=-0.55)   # gap 0.07 <= 0.15
    assert r.ok
    assert not validate.vfare_agreement(-0.30, -0.60).ok                     # gap 0.30 > 0.15

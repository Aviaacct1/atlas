"""Level 2 (pooled panel) and Level 3 (defaults + precision weighting) tests
(Method Spec 4.3-4.5; Elasticity Design 3-4). Author: Avia Solutions."""
import numpy as np
import pytest

from avia_forecast.estimate import synthetic, level2, level3
from avia_forecast.config import get


def _panel(seed0, spec):
    return [level2.Cell(f"c{i}", ap, pax, synthetic.make_clean_cell(seed=seed0 + i))
            for i, (ap, pax) in enumerate(spec)]


SPEC = [("LHR", 50), ("LHR", 20), ("LGW", 15), ("LGW", 8), ("STN", 7)]


def test_level2_recovers_pooled_elasticities_on_average():
    bG, bF = [], []
    for k in range(30):
        fit = level2.fit_panel(_panel(300 + 7 * k, SPEC))
        bG.append(fit.bG); bF.append(fit.bF)
    assert abs(np.mean(bG) - 1.30) < 0.06        # true 1.30
    assert abs(np.mean(bF) + 0.60) < 0.10        # true -0.60, noisier
    assert level2.passes_level2(level2.fit_panel(_panel(999, SPEC)))


def test_level2_below_minimum_not_estimable():
    fit = level2.fit_panel(_panel(1, [("LHR", 10), ("LGW", 10)]))   # 2 cells < 3
    assert not fit.estimable and not level2.passes_level2(fit)


def test_level2_weight_cap_holds():
    cells = _panel(1, [("LHR", 70), ("LGW", 20), ("STN", 10)])
    w = level2._capped_weights(cells)
    by_ap = {}
    for c in cells:
        by_ap[c.airport] = by_ap.get(c.airport, 0.0) + w[c.cell_id]
    assert all(v <= get("level2.weight_cap_share") + 1e-6 for v in by_ap.values())
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_level3_precision_weight_leans_on_prior_when_estimate_is_noisy():
    prior = 1.3
    assert abs(level3.precision_weight(2.0, 1.0, prior) - prior) < 0.1      # noisy -> near prior
    assert level3.precision_weight(2.0, 0.05, prior) > 1.9                  # tight -> near estimate


def test_level3_segment_default_from_measurement_and_bounds():
    # Package B, 23 August 2026 (MEASUREMENTS 16): the level 3 defaults are measured,
    # not literature priors. One elasticity per segment (the mature/emerging split
    # retired after five failed discriminator tests, so both maturity labels return
    # the same value), scaled from the pooled panel fit's 1.544 with the former
    # relativities preserved, and bF re-anchored to the measured -0.292 aggregate.
    d = level3.segment_default("Long Haul")
    assert d.bG == 1.739 and d.bF == -0.221 and not d.clipped
    emerging = level3.segment_default("International Short Haul", maturity="emerging")
    assert emerging.bG == 1.643                             # same value either label
    assert level3.segment_default("International Short Haul").bG == 1.643


def test_level3_clips_precision_weighted_above_bound():
    # a very tight, very high pooled estimate is clipped to the applied bound
    d = level3.segment_default("Long Haul", bG_est=3.0, se_est=0.02)
    assert d.bG == get("applied_bounds.bG")[1] and d.clipped

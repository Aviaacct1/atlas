"""Residual pseudo-airport (Phase 1 scope): below-scope airports collapse into one
{country}_RES entry, national totals stay whole, identities still hold. Author: Avia Solutions."""
import copy
import pytest

from avia_forecast import fixtures as fx
from avia_forecast import pipeline
from avia_forecast.config import get


def _pilot_with_small_airports():
    """UK pilot plus two genuinely sub-scope airports so the residual has something
    to carry (the real UK set is all above 2m)."""
    P = fx.make_pilot()                      # dist None -> pipeline uses default region distances
    small = [
        fx.Airport("EXT", "Exeter", False, "Exeter", 3.0,
                   fx._od(0.2, 0.6, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0), 1.2),   # ~0.9m
        fx.Airport("NQY", "Newquay", False, "Newquay", 2.0,
                   fx._od(0.1, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0), 1.2),   # ~0.3m
    ]
    P.airports.extend(small)
    P.catchments.setdefault("Exeter", []).append("EXT")
    P.catchments.setdefault("Newquay", []).append("NQY")
    return P


def test_partition_folds_small_airports_into_residual():
    P = _pilot_with_small_airports()
    modelled, residual = fx.partition_by_scope(P.airports, country="GB")
    keep = {a.iata for a in modelled}
    assert "EXT" not in keep and "NQY" not in keep      # both sub-2m, below coverage
    assert residual is not None and residual.iata == "GB_RES"
    assert residual.K == 0.0 and residual.hub is False


def test_residual_preserves_national_base_od_by_region():
    P = _pilot_with_small_airports()
    before = {r: sum(a.base_od.get(r, 0.0) for a in P.airports) for r in fx.REGIONS}
    scoped = fx.apply_scope(P, country="GB")
    after = {r: sum(a.base_od.get(r, 0.0) for a in scoped.airports) for r in fx.REGIONS}
    for r in fx.REGIONS:
        assert after[r] == pytest.approx(before[r])     # national total whole, region by region


def test_pipeline_runs_with_residual_and_identities_hold():
    P = _pilot_with_small_airports()
    scoped = fx.apply_scope(P, country="GB")
    assert any(a.iata == "GB_RES" for a in scoped.airports)
    res = pipeline.run(pilot=scoped)                     # every T-A..T-F asserts inside; a failure raises
    assert res.exceptions == []
    # the residual is unconstrained: its capacity requirement is zero at every year
    df = res.tidy
    rr = df[(df["iata"] == "GB_RES") & (df["metric"] == "cap_requirement")]
    assert (rr["value"].abs() < 1e-9).all()

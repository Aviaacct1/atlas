"""Propensity-into-demand wiring test (Cockpit B1 wired). Author: Avia Solutions."""
from avia_forecast import pipeline, fixtures


def _global_termu(res):
    t = res.tidy
    return {y: float(t[(t.metric == "term_u") & (t.iata != "-") & (t.year == y)]["value"].sum())
            for y in res.summary["years"]}


def test_propensity_damps_and_decelerates_the_mature_uk():
    p = fixtures.make_pilot()
    base = pipeline.run(pilot=p)                                  # constant elasticity
    prop = pipeline.run(pilot=fixtures.make_pilot(), use_propensity=True)
    assert prop.exceptions == [] and base.exceptions == []       # hard identities still hold
    # T-E re-grow diagnostic may escalate (soft), that is expected, not a failure

    b = _global_termu(base); q = _global_termu(prop)
    years = base.summary["years"]
    # mature UK: propensity path grows more slowly by the horizon
    assert q[years[-1]] < b[years[-1]]
    # propensity growth decelerates: later 5-year growth below earlier
    early = q[2035] / q[2030]
    late = q[2050] / q[2045]
    assert late < early

"""End-to-end two-pass orchestration on the synthetic UK pilot (Fable Q1).
Exercises every identity T-A..T-F together and checks determinism. Author: Avia Solutions."""
import pandas as pd
import pytest

from avia_forecast import pipeline
import build as build_entry


def test_run_completes_with_all_identities_and_no_exceptions():
    res = pipeline.run()
    assert res.exceptions == []                       # T-F within tolerance, nothing flagged
    assert "T-A,T-B,T-C,T-D,T-E,T-F enforced" in res.summary["identities"]
    assert not res.tidy.empty


def test_constrained_never_exceeds_unconstrained_and_capreq_nonneg():
    t = pipeline.run().tidy
    for iata in ["LHR", "LGW"]:
        u = t[(t.iata == iata) & (t.metric == "term_u")].set_index("year")["value"]
        c = t[(t.iata == iata) & (t.metric == "term_c")].set_index("year")["value"]
        assert (c <= u + 1e-9).all()
    cr = t[t.metric == "cap_requirement"]["value"]
    assert (cr >= -1e-9).all()


def test_binding_airport_shows_growing_capacity_requirement():
    t = pipeline.run().tidy
    cr = t[(t.iata == "LHR") & (t.metric == "cap_requirement")].sort_values("year")["value"].values
    assert cr[-1] > cr[0] > -1e-9                     # LHR binds harder over the horizon


def test_deterministic():
    a = pipeline.run().tidy.round(9)
    b = pipeline.run().tidy.round(9)
    pd.testing.assert_frame_equal(a, b)               # byte-identical build


def test_build_entrypoint_runs_pipeline():
    out = build_entry.build("pilot", "Baseline")
    assert out["exceptions"] == []
    assert out["n_airports"] >= 8 and out["cap_req_last_global"] > 0

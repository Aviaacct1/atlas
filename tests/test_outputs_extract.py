"""Dashboard extract tests (Data Architecture 5.1): the engine-to-front-end
contract. Author: Avia Solutions."""
import json
import pytest

from avia_forecast import pipeline, fixtures
from avia_forecast.outputs import extract as ox


def _ext():
    return ox.build_extract(pipeline.run(), fixtures.make_pilot())


def test_extract_has_all_levels_and_years():
    e = _ext()
    assert set(e["levels"]) == {"global", "region", "country", "airport"}
    years = e["meta"]["years"]
    for m in ["term_u", "term_c", "cap_requirement", "rpk_u_bn"]:
        assert len(e["levels"]["global"][m]) == len(years)
    assert {"LHR", "LGW", "MAN"} <= set(e["levels"]["airport"])   # real UK set


def test_global_equals_sum_of_airports():
    e = _ext()
    g = e["levels"]["global"]
    ap = e["levels"]["airport"]
    for m in ["term_u", "term_c", "cap_requirement"]:
        for k in range(len(e["meta"]["years"])):
            summed = round(sum(ap[i][m][k] for i in ap), 3)
            assert abs(g[m][k] - summed) < 1e-2           # global aggregates every airport


def test_constrained_not_above_unconstrained_at_global():
    e = _ext()
    g = e["levels"]["global"]
    assert all(c <= u + 1e-6 for c, u in zip(g["term_c"], g["term_u"]))


def test_flows_present_for_every_destination_region():
    e = _ext()
    for r in e["meta"]["regions"]:
        assert f"EU+UK|{r}" in e["flows"]
        assert len(e["flows"][f"EU+UK|{r}"]["flow_u"]) == len(e["meta"]["years"])


def test_extract_is_deterministic_and_json_serialisable():
    a = json.dumps(_ext(), sort_keys=True)
    b = json.dumps(_ext(), sort_keys=True)
    assert a == b


def test_writers_roundtrip(tmp_path):
    res = pipeline.run()
    e = ox.build_extract(res, fixtures.make_pilot())
    p = ox.write_extract(e, tmp_path / "ext.json")
    assert json.loads(p.read_text())["meta"]["scenario"] == "Baseline"
    ox.write_tidy_csv(res, tmp_path / "tidy.csv")
    rep = ox.write_exception_report(res, tmp_path / "exc.txt")
    assert "exception report" in rep.read_text()

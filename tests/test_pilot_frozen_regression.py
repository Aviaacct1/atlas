"""O-20: the synthetic UK pilot is regression-locked against a frozen extract, so the single-engine
merge cannot silently drift it. Keyed on iata|metric|region|year (region matters: flows and connecting
are per onward region). Author: Avia Solutions.

RE-FROZEN 23 August 2026 under package B (MEASUREMENTS 16): the level 3 elasticities
moved from literature priors to the pooled-panel measurement, which changes the pilot
deliberately, and this guard caught it exactly as designed. The frozen extract was
regenerated from pipeline.run on the tree of that date; any future drift against THIS
freeze is again unexplained until measured."""
import json
import os

from avia_forecast import pipeline

GOLDEN = os.path.join(os.path.dirname(__file__), "fixtures", "frozen_uk_pilot.json")


def _current():
    t = pipeline.run(use_propensity=True).tidy
    return {f"{r.iata}|{r.metric}|{r.region}|{int(r.year)}": round(float(r.value), 4)
            for r in t.itertuples()}


def test_pilot_matches_frozen_extract():
    assert os.path.exists(GOLDEN), "frozen golden missing"
    golden = json.load(open(GOLDEN))
    cur = _current()
    assert set(cur) == set(golden), "metric/airport/region/year set drifted from the frozen extract"
    diffs = [(k, cur[k], golden[k]) for k in golden if abs(cur[k] - golden[k]) > 1e-4]
    assert not diffs, diffs[:10]

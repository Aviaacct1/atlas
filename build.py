"""One-command build entrypoint (Data Architecture 5.2).

    build(vintage, scenario)

runs ingest-validation, estimation, forecast, aggregation, reconciliation and
outputs, then writes the exception report. Anything red stops the release.
Determinism: a given database state, assumptions vintage and code version produce
byte-identical outputs; no network access during a build. Phase A wires the
skeleton and the estimation stage; later stages arrive per the build sequence.
Author: Avia Solutions.
"""
from __future__ import annotations
import argparse
from avia_forecast import __version__
from avia_forecast.config import assumptions


STAGES = ["ingest", "estimate", "demand", "overlays", "capacity",
          "aggregate", "backtest", "outputs", "parity"]


def build(vintage: str, scenario: str = "Baseline") -> dict:
    book = assumptions()
    if scenario not in book["scenarios"]:
        raise ValueError(f"Unknown scenario {scenario!r}; see assumptions book.")
    from avia_forecast import pipeline
    res = pipeline.run(vintage=vintage, scenario=scenario)
    out = {"vintage": vintage, "scenario": scenario, "code_version": __version__,
           "stages": STAGES}
    out.update(res.summary)
    out["exceptions"] = res.exceptions
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Avia Global Aviation Forecast build")
    ap.add_argument("--vintage", required=True)
    ap.add_argument("--scenario", default="Baseline")
    args = ap.parse_args()
    print(build(args.vintage, args.scenario))

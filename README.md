# Avia Global Aviation Forecast - build

Bottom-up airport-to-global RPK forecast. This repo implements Method
Specification v0.1 and Data Architecture and Source Register v0.3.
Author: Avia Solutions.

## Design rules (Data Architecture 5.2)
- Configuration, not code: every parameter lives in `config/assumptions_book.yaml`,
  reconciled one-to-one with the Excel Control sheet. No numeric assumption sits in Python.
- Determinism: a given database state, assumptions vintage and code version produce
  byte-identical outputs. No network access during a build; ingestion is a separate, logged step.
- One command: `python build.py --vintage 2026v0 --scenario Baseline`.
- Plain stack: Python, pandas, statsmodels, SQLite/parquet.

## Modules (Data Architecture 5.1)
`ingest/` source adapters -> `estimate/` elasticities + reliability rule ->
`demand/` recursion + fare build-up -> `overlays/` adjustment + connecting ->
`capacity/` spill + CapReq -> `aggregate/` counting, RPK, reconciliation ->
`backtest/` -> `outputs/` tidy contract + exception report -> `parity/` Excel<->Python diff.

## Status (Phase A)
Skeleton, config layer, schema and the estimation module are implemented. The
estimation module's first test reproduces the Elasticity Design section 7 worked
examples on synthetic data with known truth. CAA adapter, demand core and parity
harness follow.

## Run tests
```
pip install -r requirements.txt
pytest
```

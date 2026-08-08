# Atlas switch register

Version 1.0, 8 August 2026. Avia Solutions.

Every switch, flag and environment variable that changes what the tool does, with an
owner and the test that would let it be turned on. A default-off switch is a temporary
state with an expiry, not a resting place. A switch with no test named against it is
unfinished work with a lid on.

Add a row when a switch is added. Remove a row when the switch is removed or made the
default; do not leave the row saying "on" forever.

## Data roots

Eleven variable names address five data locations today: the Global folder, the store
root, the Meridian application folder, the Zagreb folder and the duckdb scratch folder.
The OAG store alone answers to three names. The target is one name per location, read
only by `avia_forecast/paths.py`, with every other module importing from there.

| Variable | Root it sets | Read by | State |
|---|---|---|---|
| `AVIA_GLOBAL_ROOT` | `E:\Avia\Global` | `paths.py` | Keep. Canonical. |
| `AVIA_DB_ROOT` | `C:\Avia` (the duckdb stores) | `paths.py` | Keep. Canonical. |
| `AVIA_QSI_APP` | the Meridian application folder | `paths.py` | Keep. Canonical. Default must move to `C:\src\meridian\app`. |
| `AVIA_ZAGREB` | `E:\Avia\Zagreb` | `webapp/zagreb_write_excel.py`, `webapp/zagreb_write_report.py` | Fold into `paths.py`. Two modules define the same default, one of them as `r"E:\\Avia\\Zagreb"` with doubled separators. |
| `AVIA_OAG` | the OAG raw file folder | `scripts/ingest_oag_annual.py` | Fold into `paths.py`. |
| `AVIA_OAG_DB` | the OAG store | `scripts/backtest_seats_anchor.py` | Fold into `paths.py`, which already exports `OAG_DB`. |
| `AVIA_OAG_STORE` | the OAG store | `avia_forecast/ingest/oag_peak.py` | Duplicate of the above under a third name. Fold in. |
| `QSI_APP` | the Meridian application folder | `webapp/qsi_service.py` | Duplicate of `AVIA_QSI_APP`. Setting one and not the other gives a half-pointed host. Remove. |
| `QSI_OAG` | the OAG store | `webapp/qsi_service.py` | The third name for the same store, after `AVIA_OAG_DB` and `AVIA_OAG_STORE`. Fold in. |
| `QSI_SABRE` | the Sabre store | `webapp/qsi_service.py`, `webapp/build_history.py` | Fold into `paths.py`, which already exports `SABRE_DB`. |
| `AVIA_DUCKDB_TMP` | duckdb scratch | `avia_forecast/ingest/oag_peak.py` | Keep as a host-level override; add to `paths.py`. |
| `AVIA_PROJECT_DIR` | the project document folder | `webapp/zagreb_write_excel.py` | Keep. Documents, not data. |
| `PORT` | webapp port, default 8000 | `webapp/serve.py`, `webapp/qsi_service.py` | Keep. |
| `FORECAST_PASSWORD` | overrides `webapp/access_password.txt` | `webapp/qsi_service.py` | Keep. The file is gitignored and stays so. |

## Capability switches

| Switch | What it turns on | Default | Test that would let it be turned on | Owner |
|---|---|---|---|---|
| `config.headwinds` (per airport) | Compounding annual drag from a start year, for a charges increase or a capacity restriction | Absent from both configured airports, so no effect | `tests/test_airport_overlays.py` already passes. Needed: one configured airport with a real headwind and a stated source for the drag. Zagreb is the candidate. | John |
| `scripts/build_bum_candidates.py --optimise` | Frequency and gauge optimisation on candidate routes | off | Needs a run against a known route set with the result compared to the unoptimised case | Unassigned |
| `scripts/build_bum_candidates.py --market-only` | Raw market rank, skipping the QSI share | off | Diagnostic. Correct as an off default. | Unassigned |
| `scripts/build_peak_panel.py --auto-capped` | Automatic capacity cap detection on the peak panel | off | Needs the capacity register France test set, which is in progress | John |
| `scripts/build_peak_panel.py --describe` | Reports tables and columns, then stops | off | Diagnostic. Correct as an off default. | Unassigned |
| `scripts/bt2_model.py --train` | Retrains the BT2 model | off | Correct as an off default: training is deliberate. But see below. | Unassigned |
| `scripts/patch_config_capacity_v04.py --apply` | Writes the config changes rather than a dry run | off | Correct as an off default. | Unassigned |
| `scripts/patch_config_capacity_v04.py --refresh-oag` | Re-reads the OAG store when patching | off | Correct as an off default. | Unassigned |
| `scripts/estimate_airport_diagnostics.py --selftest` | Self-test path | off | Diagnostic. Correct as an off default. | Unassigned |

## Capability that is not behind a switch, and is off anyway

| Item | State | What would turn it on |
|---|---|---|
| `avia_forecast/outputs/chart_writer.py` | Nothing calls it. The Excel deliverable carries no charts. | Wire it into the Excel output path and extend `tests/test_impact_and_charts.py` to assert on the written workbook, not only on the format module. |
| `avia_forecast/estimate/fare_construction.py` | Nothing calls it. `data/fare_index_constructed.json` is frozen at 6 July 2026 and `fare_index.pass_through_theta` and `real_yield_trend_tau` are inert. | A build script that regenerates the fare index from the EIA fuel series, and a test that changing theta in the assumptions book changes a forecast number. |
| BT2 training scripts in `C:\Avia\bt2` | Hard-code a Cowork session path that no longer exists, so they cannot run on any machine today | Repoint them through `paths.py`. Until then `data/bt2_model_v1_2.pkl` cannot be reproduced, only used. |

Copyright Avia Solutions Limited. All rights reserved.

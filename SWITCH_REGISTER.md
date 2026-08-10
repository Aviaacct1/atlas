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

## Assumptions-book switches that default to off in code

The scan behind version 1.0 of this register looked at environment variables and
command-line flags and missed these, which are `config.get(name, False)` with no entry in
the assumptions book. A switch that is absent from the book reads as though it does not
exist, and the code default decides.

**All three moved into `config/assumptions_book.yaml` on 9 August 2026**, at exactly the
values they had as code defaults, so nothing moved by adding them. The forecast was
re-run to confirm: world 2060 unchanged at 9,644m, CAGR 3.26%.

| Key | Read in | State | What turning it on would do |
|---|---|---|---|
| `global_drivers.use_estimated_elasticities` | `global_demand.py:285` | **Off**, now stated in the book | The 137 estimated country income elasticities in `estimated_bG_by_country.json` are loaded on every run and then discarded. **Measured on 9 August: turning it on adds 23.3% to the world 2060 figure and takes the CAGR from 3.26% to 3.88%.** Leave it off. 45 of the 137 estimates sit at or beyond the applied bound of 2.2 and are clamped on the way in, the highest at 3.48, which says the fits are reading liberalisation and network build as income response. The test that would let it be turned on: re-estimation on O&D rather than terminal traffic, then this measurement repeated. See `MEASUREMENTS.md` section 1. Owner: John |
| `global_drivers.use_airport_elasticities` | `global_demand.py:203` | On, now stated in the book | Applies an airport's own fitted elasticity where it is reliable and its connecting share is at or below `airport_elasticity_max_cx`. 111 airports carry a reliable own fit |
| `global_drivers.maturity_basis` | `global_demand._maturity_weight` | **`saturation`** since 9 August 2026 | Decides whether a country takes the mature or the emerging income elasticity. `income_threshold` is the old basis and is a cliff at 25,000 international dollars per head; it reproduces the forecast to the fourth decimal and is kept as the control. `saturation` reads maturity off trips per capita against the regional asymptote, so the elasticity interpolates. Moving to it took the world CAGR 2025-2060 from 2.89% to 3.05% and China from 2.61% to 3.13%. The test that would send it back: a measurement of whether the elasticity split and the propensity headroom should both be monotone in saturation, since they now are. Owner: John |
| `global_drivers.airport_elasticity_max_cx` | `global_demand.py:210` | 0.25, now stated in the book | The connecting-share screen. 68 of the 111 sit above it and fall back to the country value, which is 2.1 points of the 12.2% correction of 8 August. [P1] pending the O&D re-estimation |

## Capability that was off and is now wired

| Item | Was | Now |
|---|---|---|
| `outputs/chart_writer.py` | Imported by nothing, so every configured-airport workbook went out with no chart while the formatting rules beside it were tested and green | Split into `add_forecast_chart(wb, ...)` and called by `outputs/excel_writer.write_instance_excel`. `tests/test_excel_writer.py` now asserts on the written workbook: a chart sheet and a chart part inside the file, not merely a module that could draw one |
| `estimate/fare_construction.py` and `data/jet_fuel_eia.json` | Both read by nothing. The fare index was frozen at 6 July 2026 and `fare_index.pass_through_theta` and `real_yield_trend_tau` changed no number the product reported | `scripts/build_fare_index.py` regenerates the index from the fuel series, check-only by default. `tests/test_fare_index_wiring.py` asserts that both assumptions move the index, and that the shipped file is the one the current assumptions produce, so the book and the file cannot drift apart unnoticed. The rebuild reproduces the shipped index exactly, which confirms it was genuinely built this way |
| Comparator figures in `webapp/dashboard.html` | `0.042` and `0.036` written into the page in two places, and four growth rates typed into the reconciliation table, all labelled placeholders by the page's own footnote | `config/comparators.yaml`, each with edition, basis, window, source and URL, carried into `dashboard.json` by the build and read by the page. The Avia column is computed from the run over each comparator's own window and basis |

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

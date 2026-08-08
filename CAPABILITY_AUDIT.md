# Atlas capability audit

Version 1.0, 8 August 2026. Avia Solutions.

What is built and live, and what is built and nothing calls. Produced by a static read
of the tree on 8 August 2026, cross-checked against `capability_audit.py` in the
`meridian` repo. Every count below was re-checked by hand against the filesystem before
it was written here, because a check that surprises you has to be confirmed before it is
acted on.

Tree audited: `C:\Avia\avia_forecast_build` after the 8 August reconciliation.
209 Python files. Test suite at the time of the audit: 326 passed, 6 skipped.

---

## 1. Modules nothing imports

Two, and both are capability rather than dead weight.

**`avia_forecast/outputs/chart_writer.py`.** Writes the impact table and Avia-format
charts to xlsx: dedicated chart sheet, legend at the bottom, no gridlines, a "Source:"
line, author stamped "Avia Solutions". No script and no test calls it. `chart_format.py`
beside it is called, by `tests/test_impact_and_charts.py`. So the formatting rules are
tested and the writer that would apply them to a deliverable is not wired to anything.

**`avia_forecast/estimate/fare_construction.py`.** Builds the cost-driven real fare
index from jet fuel and segment fuel shares, which is the G1 recipe in the method
specification. Nothing calls `build_fare_index`. See section 3: this is the more serious
of the two.

Everything else in the package is reached. Section 1 of the machine output lists 36
command-line tools that nothing imports, which is expected: they are entry points.

## 2. Switches with no hand on them

`config.headwinds` is read in three places in `avia_forecast/airports/instance.py` and
is set in neither `config/airports/bristol.yaml` nor `config/airports/zagreb.yaml`. Only
`tests/test_airport_overlays.py` sets it. The overlay applies a compounding annual drag
from a start year, with a part-year weight on the first year, which is how a charges
increase or a capacity restriction would be carried. It is implemented, tested, and has
never been applied to a configured airport.

Three further keys the machine output flagged were checked and are false positives:
`mirror_canonicality.flips` and `reliability.T2_range.bG` are both set in
`config/`, and `benchmark_007` is set at line 262 of `config/airports/zagreb.yaml`.

## 3. The fare channel

The forecast reads its fare series from `data/fare_index_constructed.json`, a static
file dated 6 July 2026. Nothing in the tree regenerates it. `fare_construction.py` is
the routine that would, and no script calls it.

The consequence is specific and testable. `fare_index.pass_through_theta` and
`fare_index.real_yield_trend_tau` in the assumptions book are read in exactly three
places: `demand/core.fare_path`, which is called only by `tests/test_demand_core.py`;
`estimate/fare_construction.build_fare_index`, which nothing calls; and that same test.
Both live consumers of the fare series, `pipeline.py` through `fixtures.fare_index()`
and `global_demand._fare_index()`, read the frozen JSON. Changing either assumption in
`config/assumptions_book.yaml` therefore changes no number the product reports.

This is not a claim that the fare index is wrong. It is a claim that it is frozen, that
the two published assumptions behind it are inert, and that neither state is visible to
anyone reading the assumptions book.

## 3a. The finding that moves the numbers

`global_demand.py` imported `DATA` from `paths.py`, the Global folder on `E:`, and then
eleven lines later rebound the same name to the repository's own `data` folder.
`E_DATA` was set from the rebound name. So three files it loads from `E_DATA` were being
looked for inside the repository, were not there, and each load caught the error and
returned an empty dictionary:

| File | What was lost | Now reaching the engine |
|---|---|---|
| `estimated_bG_by_country.json` | Every country ran on the default income elasticity | 137 countries |
| `oef_gdp_pop_by_iso2.json` | The forecast ran on the regional GDP growth default, not the Oxford Economics country forecast | 197 countries |
| `aci_hub_calibration_2024.json` | No airport carried a connecting share | 2,430 airports |

**This changes the product's headline number.** Running the global demand model both
ways on 8 August 2026:

| Basis | World O&D departing pax 2025 | 2060 | CAGR 2025-2060 |
|---|---|---|---|
| As it ran, staged data not reaching it | 3,140m | 10,983m | 3.64% |
| With the staged data reaching it | 3,140m | 9,644m | 3.26% |

Source: `avia_forecast/global_demand.run_global`, Baseline scenario, run on the tree of
8 August 2026 with and without `AVIA_GLOBAL_ROOT` resolving.

The lower figure is the one built on the Oxford Economics country forecasts and the
estimated country elasticities. It is 12.2% below the figure the engine was producing,
1,339m passengers in 2060. Nothing about this was visible: no error, no warning, no
failing test. The two data folders now carry different names in that module, and the
comment there says why they must not be collapsed back into one.

## 4. Fallbacks that do not report

37 silent exception handlers across 22 modules. Most are unremarkable. Six are not,
because they sit around a data load that the workstation move will break:

| Module | Load | Silent result |
|---|---|---|
| `global_demand._est_bG` | `estimated_bG_by_country.json` from `E:\Avia\Global\data` | `{}`: every country falls back to the default income elasticity |
| `global_demand._oef_gdp` | `oef_gdp_pop_by_iso2.json` from the same place | `{}`: falls back to the regional GDP growth default |
| `global_demand._airport_cx` | `aci_hub_calibration_2024.json` | `{}`: no per-airport connecting share |
| `global_demand._airport_regress` | `data/airport_regress.json` **in the repo, and gitignored** | `{}` |
| `global_terminal.run_terminal` | `oag_final_to_next_M.json` | `{}`: no per-airport destination-region seat shares |
| `global_terminal._load` | `aci_hub_calibration_2024.json` | raises, which is the correct behaviour and the exception to the pattern |

The fourth row is the one to fix first. `data/airport_regress.json` is excluded from the
repository, so a fresh clone will not contain it, and `_airport_regress()` catches a bare
`Exception` and returns an empty dictionary. A clone on the workstation will run the
global forecast with no airport regression and report nothing at all. It will produce
numbers. They will be different numbers.

Fix the six above so they name the file, the resolved path and the roots tried, then
exit non-zero or return a value the caller can test. Leave the other 31.

## 5. Paths and their owners

`avia_forecast/paths.py` is a sound central resolver: environment variable, then the
Windows working location, then the sandbox mount discovered by glob rather than by a
hard-coded session name. It is the right pattern and it should be the only one.

It is not. Eleven environment variable names address five data locations:
`AVIA_GLOBAL_ROOT`, `AVIA_DB_ROOT`, `AVIA_QSI_APP`, `AVIA_ZAGREB`, `AVIA_DUCKDB_TMP`,
`AVIA_OAG`, `AVIA_OAG_DB`, `AVIA_OAG_STORE`, `QSI_APP`, `QSI_OAG`, `QSI_SABRE`. The OAG
store alone answers to three of them. `webapp/qsi_service.py` reads `QSI_APP` while
`paths.py` reads `AVIA_QSI_APP`, and both carry their own default. Setting one and not
the other gives a host where half the tool points at the new location. Provisioning is
meant to be one variable per location.

Two files carried a dead Cowork session path as a fallback and were fixed on 8 August:
`scripts/backtest_seats_anchor.py` and `webapp/build_history.py`. Both now resolve
through `paths.py`. `scripts/validate_repo.py`, which the pre-commit hook runs, failed
before that change and passes after it.

## 6. What Atlas imports from Meridian

`scripts/run_qsi_bum.py` inserts the QSI application directory on `sys.path` and imports
`route_forecast` and `connection_builder` from it. `webapp/qsi_service.py` runs the same
module. The default for both is
`C:\Users\Carte\OneDrive\Documents\Claude\Projects\Avia QSI Tool\app`.

That tree is a superseded copy of Meridian. It is not a git repository, it is missing 34
modules that `C:\src\meridian\app` has, and it carries ten scratch files prefixed with an
underscore that Meridian does not. Its `reference_tables/airport_city_country.csv` is byte-identical to
Meridian's, so the reference data has not diverged; the code has.

Atlas should point at `C:\src\meridian\app`, the clone with the history and the remote.
`preagg.duckdb`, 86MB, exists only in the OneDrive tree and is data: it belongs in the
data root, not in either tool's folder.

There are no module-name collisions between Atlas's `scripts/` and `webapp/` and
Meridian's `app/`, so nothing is currently shadowed across the two trees. That holds
today and will not hold by itself.

---

## What this audit does not answer

Whether the accuracy Atlas publishes describes the thing a client is shown. The BT2
evidence programme that produces the track record is scored by `scripts/bt2_features.py`
against `data/bt2_model_v1_2.pkl`, and the scripts that trained that model, in
`C:\Avia\bt2`, hard-code a Cowork session path that no longer exists. Ask that question
before the Global Forecast is sold, and ask it early, because the answer may be a
conversation rather than a change.

Copyright Avia Solutions Limited. All rights reserved.

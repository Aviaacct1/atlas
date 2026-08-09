# Handover: the OGF deck, the base rebuild, and what is open

Version 1.0, 9 August 2026. Avia Solutions. Supersedes "HANDOVER - OGF Deck Build -
9 August 2026" on everything it covers; that document is still the record of what the
tree looked like before today.

Start the next session with `PROMPT - Next Session - Stage Length and World Bank.md`.
This is the detail behind it.

---

## 1. Where things are

**Two repositories moved today.** Atlas at `C:\src\atlas` and Meridian at
`C:\src\meridian`. The Meridian change is the airport reference table and Atlas depends
on it, so pull Meridian first on any machine.

Data stays where it was: `C:\Avia` for the duckdb stores, `E:\Avia\Global` for the
Global folder and OEF, `C:\Avia\preagg.duckdb` for the Sabre base year O&D.

Tests: `py -3.12 -m pytest tests -q` from the repo root, **336 collected, 335 pass, 1
skip**. The skip is `test_oag_tiling_overlap`, which hard-codes `C:/Avia/oag.duckdb`
rather than resolving through `paths.py`; it runs on the workstation and skips
elsewhere. Repository check: `py -3.12 scripts\validate_repo.py`, expect 0.

**Working rule unchanged.** Pull before editing, push after. Git commands run in John's
PowerShell, never through a Cowork mount: a mount blocks unlink, so even a
`git add --dry-run` leaves `.git\index.lock` behind. Sessions write code and run tests;
John commits.

## 2. The forecast as it now stands

**World O&D departing passengers, Baseline: 3,341m in 2025 to 7,582m in 2050, a CAGR of
3.26%.** The base year moved today from 3,139.7m, 6.4% higher, because the airport
reference table was completed. The growth rate did not move.

Airports in the base 3,233 to 4,202. Modelled set 677 to 717. Catchments 642 to 675.
Coverage of world O&D by the modelled set 86.2% to 85.7%.

## 3. Against Boeing, after the rebuild

`py -3.12 scripts\compare_regions_boeing.py` reproduces this. RPK CAGR 2024-2044 against
the Boeing CMO 2025 workbook held on Egnyte.

| Region | Avia | Boeing | Diff | Diff after the stage length bridge |
|---|---|---|---|---|
| South Asia | 7.7% | 7.0% | +0.7pp | +0.7pp |
| Southeast Asia | 5.6% | 7.0% | -1.4pp | -0.2pp |
| Africa | 4.5% | 6.0% | -1.5pp | -1.1pp |
| China | 3.3% | 5.3% | -2.0pp | -1.9pp |
| Middle East | 2.8% | 4.4% | -1.6pp | -1.1pp |
| Latin America | 2.7% | 4.3% | -1.6pp | -0.6pp |
| Northeast Asia | 2.7% | 2.4% | +0.3pp | +1.2pp |
| Oceania | 2.3% | 3.0% | -0.7pp | +0.6pp |
| Eurasia | 2.1% | 3.1% | -1.0pp | -0.1pp |
| North America | 2.0% | 2.8% | -0.8pp | -0.3pp |
| **World** | **3.3%** | **4.2%** | **-0.9pp** | **-0.2pp** |

**The finding of the day is the last column.** Boeing publishes RPK. Atlas forecasts
passengers and converts to RPK with a stage length held constant, so our RPK CAGR is our
passenger CAGR to the decimal place, while Boeing's carries their stage length growth
inside it. `compare_regions_boeing.py` said in its own header that a constant stage
length cancels in a CAGR. It cancels between our RPK and our own passengers. It does not
cancel against a counterparty whose RPK contains a growing stage length, which is the
only comparison the script exists for.

Measured from the OAG schedule, stage length grew **0.6% a year at world level over
2015-2025**. Carried into the conversion as a test, the world gap goes from -0.9pp to
-0.2pp. Two thirds of the headline gap is a conversion convention. What remains
concentrates in China, Africa and the Middle East, where affordability is the mechanism
Boeing uses and we do not model it.

Nothing has been changed on the back of this. `scripts/gap_decomposition.py` measures.
A single historic rate applied everywhere over-corrects Oceania and Northeast Asia, so
the fix is a stated stage length path per region, and that is the first job of the next
session.

## 4. The fleet productivity wedge

Boeing's Market Overview pages 24 and 25. The identity holds to zero residual:

    ASK = departures x seats per departure x stage length

| Window | Segment | ASK | Seats | Departures | Gauge | Stage |
|---|---|---|---|---|---|---|
| 2015-2019 | single aisle | 6.9% | 6.2% | 5.0% | 1.2% | 0.6% |
| 2015-2019 | widebody | 6.0% | 5.3% | 4.5% | 0.7% | 0.7% |
| 2015-2025 | single aisle | 4.5% | 3.6% | 2.7% | 0.9% | 0.8% |
| 2015-2025 | all segments | 3.3% | 2.7% | 1.3% | 1.4% | 0.6% |

Gauge splits by shift-share: single aisle 2015-2025 is up-gauging 0.6% a year and
densification 0.4%. Boeing over 2004-2023 show ASK 5.7%, seats 4.8% and fleet 3.1%.
Their window cannot be reproduced: the store holds 2015-2019 and 2023-2025, with
2020-2022 excluded by policy, and the deck says so on the slide.

**Boeing's fourth term is not produced.** Flights per aircraft per day needs a count of
aircraft in service. Deriving it from the dashboard's `PROD_NB = 330` and
`PROD_WB = 1,050` would return whatever was typed in. It is an acquisition item
alongside fleet age.

## 5. What was built today

| Thing | Where | Why it matters |
|---|---|---|
| OAG store guard | `scripts/guard_oag_wedge.py` | 15 checks, runs before any wedge number. Caught the two-way Heathrow anchor and the impossible sector distances |
| Aircraft body types | `config/aircraft_body_types.yaml` | All 245 codes in the store with an aisle count and a class, so Boeing's single aisle, regional jet and widebody segments each cut from the same data |
| Fleet wedge | `scripts/build_fleet_wedge.py` | The identity above, plus stage length by Boeing region |
| The gap, split | `scripts/gap_decomposition.py` | The last column of the table in section 3 |
| Deck data | `scripts/build_ogf_deck_data.py` | Network, LCC share and single aisle by business model, eight years |
| The deck | `scripts/build_ogf_deck.py` | 14 slides, Observatory style, regenerates from the forecast |
| Deck check | `scripts/check_deck.py` | Reads the built file as a zip: dash sweep, metadata, en-GB, fonts, source lines |
| Missing airports | `scripts/measure_missing_airports.py` | Sized the hole in the base |
| Its effect | `scripts/measure_missing_airports_effect.py` | Ran the demand model through it, in memory, twice |
| Reference supplement | `scripts/build_airport_reference_supplement.py` | The 991 rows the reference table was missing |
| Colocation detector | `scripts/detect_colocated_airports.py` | Finds airports sharing a city from great circle distances alone, calibrated on the reference table |
| Ingest guard | `scripts/ingest_global_base.py` | Names every dropped origin above 0.1m and stops if one above the 2m scope floor would be dropped |

Meridian: `app/reference_tables/airport_city_country.csv`, 3,568 rows to 4,559.

The deck is at `C:\Users\Carte\OneDrive\Documents\Claude\Projects\Avia Global Forecast Tool\OGF Market Overview - DRAFT.pptx`.

## 6. Open, in the order I would take it

**1. Ingest the World Bank fully. John has confirmed this.**
`data/worldbank_pop_gdppc.json` holds **30 countries**.
`global_demand.country_headroom` returns None without a record, so the propensity
ceiling can bind on 2,607m of 3,341m outbound O&D, 78%, and cannot bind on 734m, 22%.
Russia, Korea, Vietnam, Canada, Malaysia and the Philippines are all outside it and
compound at regional GDP growth with no saturation. That is Vietnam at 1,217m passengers
by 2060 and Astana seventeen times its 2015 self. Extend the ingest to every country in
the base, re-run, and measure the effect before and after. Direction: it will pull those
countries DOWN, so the world figure falls and the gap against Boeing widens. See
`MEASUREMENTS.md` section 4.

**2. The stage length path.** A stated path per region, converging rather than a flat
extrapolation of 2015-2025, with the before and after on every published figure. This is
the change that moves the world number towards 4.0% and it needs John's sign-off on the
path itself, not just the result.

**3. Beijing Daxing is still outside every published figure.**
`global_terminal.run_terminal` iterates `aci_hub_calibration_2024.json`, not the base,
and reports `n_airports` as the length of that file, which is why 2,430 never moved.
TFU, NQZ and NLU are in the ACI file and now carry base O&D for the first time; Chengdu
Tianfu enters the dashboard at 44.79m terminal growing to 130.81m. **PKX is not in the
ACI file.** Needs either the ACI 2024 record for Daxing, if they file it under another
code or as a Beijing system entry, or a stated rule for admitting an airport the base
holds and ACI does not. A method decision.

**4. The China fit channel, the last part of the original hypothesis.** PEK carries a
fitted income elasticity of 1.089 estimated over 1994-2024 and CTU 1.5 over 1999-2024,
both windows running through a transfer that reads as a collapse in demand. Re-estimate
the airport regressions on combined city system panels, Beijing as PEK plus PKX plus NAY
and Chengdu as CTU plus TFU. This is the only channel left that could move China towards
Boeing.

**5. Absolute fare levels, the F15 item.** Our fare series is an index with no level, so
we cannot draw affordability, which is the mechanism behind the four regions that do not
close after the stage length bridge. A data acquisition decision.

**6. Airbus.** The GMF region scheme is a placeholder in `config/region_schemes.yaml`
and is a lookup table away from being real.

**7. The 2026 workbooks.** Boeing's CMO 2026-2045 and Airbus's GMF 2026-2045 are
published and not in Egnyte. The 2026 rates in `config/comparators.yaml` come from press
releases, which round. Needed before the October meeting with Wendy Sowers if the deck
is to stand against her current numbers rather than last year's.

**8. Ten airports in the reference table carry no city name**, all below the 2m scope
floor: PXN, TTQ, EKK, SZC, QJG, XHK, QFT, WEC, GBX, JBD. They fill themselves when Jess
pulls OAG's own airport reference.

**9. The track record question**, carried forward unanswered from the last handover. The
dashboard shows a track record produced by something the live forecast does not import.
It has to be answered before the OGF is sold.

## 7. Traps that cost time today, so they do not cost it twice

**The Cowork sandbox cannot read the OAG store at scale.** 4GB and two cores against a
16.8GB store over a mount. `build_ogf_deck_data.py` ran twelve minutes on eight years and
produced nothing; `detect_colocated_airports.py` needed a one-year filter to finish at
all. Both are fine on the workstation. The MCP bash tool also caps around 178 seconds, so
anything longer needs `nohup` and polling.

**Read the file the code reads, not the one that is easy to open.** The propensity
finding was nearly published off the dashboard's `cty` payload, where 227 of 231
countries carry a zero population. That payload is not what the engine reads. The engine
reads `worldbank_pop_gdppc.json`, and the true answer, 30 countries, is a different and
smaller claim than the one the wrong file supported.

**A guard that writes before it checks is decorative.** The first version of the ingest
guard wrote the base and then complained about it, leaving the bad file on disk for the
next step.

**Summing versus taking the maximum over week keys.** A first replacement detector
grouped by week and took the max, which returns the busiest month rather than the year
and put Cairo 2019 at 1.2m departing seats. It found nothing, which is how it was caught.

**A calibration must remove trend AND season.** The store truncation check went through
two wrong designs: against the year's own median every European January failed on winter
seasonality, and against the same month in other years every 2015 slice failed on ten
years of Asian growth. What works is each slice against the other slices of its own
region-year at a 50% floor, plus a year-on-year annual step check.

**The Heathrow 2019 anchor is TWO WAY.** 477,954 movements and 100.3m seats count
arrivals and departures. A departures-only query returns exactly half, 238,978 and 50.2m,
and reads as a store missing half its data. The docstring in
`avia_forecast/ingest/oag_store.py` now says so.

**Three hypotheses of mine were wrong today and the data said so each time.** The missing
airports were a level defect and not a growth defect, and correcting them moved China the
wrong way. The 45 unnamed airports were not rail stations; every one carried scheduled
service. And the propensity ceilings do not bind in the places the previous handover said
they bind. Measure before asserting, and record the correction rather than quietly
changing the story.

**Sandbox path notes.** `paths.QSI_APP` defaults to a Windows path, so a sandbox run needs
`AVIA_QSI_APP` or `--qsi`. `scope_global.py` has no CLI parser and takes its arguments
through `run(year, qsi)`. Some scripts need `PYTHONPATH=.`.

Copyright Avia Solutions Limited. All rights reserved.

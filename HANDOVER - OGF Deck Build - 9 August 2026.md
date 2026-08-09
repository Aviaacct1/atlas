# Handover: the Observatory OGF deck, and where Atlas stands

Version 1.0, 9 August 2026. Avia Solutions. Read this before the next session.

Paste the prompt in `PROMPT - Next Session - OGF Deck.md` to start. This document is the
detail behind it.

---

## 1. Where things are

**Atlas is on GitHub.** `C:\src\atlas`, branch `main`, remote
`https://github.com/Aviaacct1/atlas.git`, tag `atlas-baseline-08Aug2026`. A clone
provisions and passes `check_env.py`. Data stays at `C:\Avia`; the Global folder and OEF
are on `E:\Avia\Global`; Meridian is at `C:\src\meridian`.

Run the tool: `cd C:\src\atlas\webapp` then `"Run Avia Forecast (with QSI service).bat"`,
open `http://localhost:8000`. Tests: `py -3.12 -m pytest tests -q` from the repo root,
**expect 336 passed**. Repository check: `py -3.12 scripts\validate_repo.py`, expect 0.

**Working rule.** Pull before editing, push after. Git commands run in John's PowerShell,
never through a Cowork mount: a mount blocks unlink, so even a `git add --dry-run` leaves
`.git\index.lock` behind. Sessions write code and run tests; John commits.

## 2. The forecast as it now stands

World O&D departing passengers, Baseline: **3,140m in 2025 to 9,644m in 2060**, a CAGR of
**3.26%**. On an RPK basis over Boeing's 2024-2044 window, **3.3%**.

Two corrections got it here, both on 8 August, both recorded in `MEASUREMENTS.md`.

`global_demand.py` imported `DATA` from `paths.py` and rebound the same name to the
repository's own data folder eleven lines later, so three staged files were looked for
inside the repo, were not there, and each load returned an empty dictionary in silence.
Fixing it brought in 137 country elasticities, 197 country GDP paths and 2,430 airport
connecting shares, and **took the world 2060 figure down 12.2%**, from 10,983m to 9,644m.
Almost all of that is the GDP driver; the connecting share is 2.1 points of it and the
country elasticities none, for the reason below.

Anything quoted from a global run before 8 August 2026 came off the higher path.

## 3. The comparison with Boeing, on Boeing's regions

`py -3.12 scripts\compare_regions_boeing.py` reproduces this. All 2,430 airports assigned,
no unmapped, RPK CAGR 2024-2044 against the Boeing CMO 2025 workbook held on Egnyte.

| Region | Avia | Boeing | Diff |
|---|---|---|---|
| South Asia | 7.7% | 7.0% | +0.7pp |
| Northeast Asia | 2.6% | 2.4% | +0.2pp |
| Oceania | 2.4% | 3.0% | -0.6pp |
| North America | 2.0% | 2.8% | -0.8pp |
| Eurasia | 2.0% | 3.1% | -1.1pp |
| Southeast Asia | 5.6% | 7.0% | -1.4pp |
| Middle East | 2.9% | 4.4% | -1.5pp |
| Africa | 4.5% | 6.0% | -1.5pp |
| Latin America | 2.7% | 4.3% | -1.6pp |
| China | 3.4% | 5.3% | -1.9pp |
| **World** | **3.3%** | **4.2%** | **-0.9pp** |

**The pattern is the finding.** We are ahead in South and Northeast Asia and behind by
1.4 to 1.9 points in China, Latin America, the Middle East, Africa and Southeast Asia.
Those five are the emerging markets whose growth Boeing explains through affordability,
the fall in fare as a share of GDP per capita. We do not model that mechanism and cannot
draw that slide. Our propensity ceilings, 2.2 trips per capita for Africa and 2.6 for Asia
Pacific, are the second suspect and bind in the same places.

**What it is not.** The GDP vintage. We run Oxford Economics 31 July 2024, two years old,
and that looked like the obvious explanation. Compared like for like against the OEF
August 2025 Base case on the same 50 countries, the newer vintage is 0.4 points lower in
2025-2026, 0.15 to 0.34 points higher from 2027, and lands within **0.26%** on the level
by 2031. A newer vintage would not close a 0.9 point gap. Getting to that took two wrong
answers first: mismatched country samples, then reading the Low scenario because the sheet
has Actual, Low, Base and High bands side by side. Read the band header, never the column
position.

## 4. What was built on 8 and 9 August

| Thing | Where | Why it matters |
|---|---|---|
| Region schemes | `config/region_schemes.yaml` | Boeing's ten regions as a partition of ISO2. Airbus is a documented placeholder, not yet read from the GMF appendix. |
| Region reconciliation | `scripts/compare_regions_boeing.py` | The table above, from config, not typed numbers. `--json` for the deck build. |
| Slide inventory | `OGF DECK - Slide Inventory against Boeing Market Overview 2025.md` | All 22 content slides of the Sowers deck mapped: 6 can, 7 partial, 9 cannot. |
| Comparators | `config/comparators.yaml` | Boeing 4.0%, Airbus 3.9%, IATA 3.6%, ACI 3.4%, each with edition, basis, window, source and URL. Read by the dashboard. |
| Measurements | `MEASUREMENTS.md` | The elasticity switch and the 12.2% breakdown, with the runs named. |
| Switch register | `SWITCH_REGISTER.md` | Every switch with an owner and the test that would let it be turned on. |
| Capability audit | `CAPABILITY_AUDIT.md` | What is built and what nothing calls. |
| Fare index rebuild | `scripts/build_fare_index.py` and `tests/test_fare_index_wiring.py` | Check-only by default. A guard fails if the assumptions book and the shipped index drift apart. |
| Host check | `check_env.py` | Interpreter, packages, data roots, the six files the engine loads silently, three smoke tests. |

## 5. Traps that cost time, so they do not cost it twice

**Guards earn their keep, and every one of these was caught by a guard rather than by
luck.** Build the guard before the analysis.

- The dashboard's `country` field is **mixed**: a name for some airports, an ISO2 code for
  others. Assuming one form silently lost 441 airports, every Brazilian and Indian field
  among them, to an Unassigned bucket.
- Unquoted `NO` in YAML parses as the boolean false, so **Norway silently left the region
  scheme**. Every country code in `region_schemes.yaml` is quoted for that reason.
- A `.gitignore` rule does **not** untrack a file already tracked. Two generated JSON files
  from the 7 July commit would have travelled to the workstation in the clone.
- `py -3.12` selects the system interpreter whether or not a virtual environment is
  active. Call `.venv\Scripts\python.exe` by path.
- `.bat` files must be CRLF and must not use a parenthesised `if / else`; cmd.exe mangles
  both.
- Three build scripts import the names from `paths.py` individually rather than the module,
  so `paths.PREAGG` raised `NameError` and `build_dashboard_data.py` died two minutes in
  having printed all its checks. An AST pass for names used and never bound found them.

## 6. What is open, in the order I would take it

**1. The fleet productivity wedge.** Pages 24 and 25 of the Sowers deck. Boeing shows ASK
at 5.7%, seats at 4.8% and fleet at 3.1% for 2004-2023, and names the difference:
densification, up-gauging, longer stage lengths, more flights a day. Our 0.9 point gap has
to live inside that wedge. We produce the ASK and imply the fleet; we do not explain the
gap between them. Build this first: it either explains our number or exposes it, and it is
the same arithmetic seen from the fleet side.

**2. Absolute fare levels, the F15 item.** Our fare series is an index with no level, so
we cannot draw affordability, which is the mechanism behind the five regions where we lag
worst. This is a data acquisition decision, not an engineering one.

**3. Stage length is constant in our RPK conversion.** `SL` in
`scripts/compare_regions_boeing.py` and in `dashboard.html` is a fixed per-region average,
already flagged [P1]. Boeing has stage length growing, which is part of why RPK outruns
passengers for them and not for us. A constant cancels in a CAGR, so it does not explain
the growth gap, but it does make our RPK levels indicative rather than sound.

**4. Cargo.** Four slides, none of which we can produce. We forecast landed tonnage at
airport level and hold nothing on the world air cargo market. Either buy the data or scope
the OGF as passenger and airport cargo and say so.

**5. The 2026 workbooks.** Boeing's CMO 2026-2045 and Airbus's GMF 2026-2045 are published
but not in Egnyte. The rates in `config/comparators.yaml` for the 2026 editions come from
press releases, which round. Jol flagged the same thing in 2023: the release quotes higher
than the data file. If we launch against the 2026 CMO we need its workbook.

**6. Airbus region scheme.** Placeholder in `config/region_schemes.yaml`. Populate from
the GMF appendix.

**7. Country elasticities stay off.** `global_drivers.use_estimated_elasticities` is
false. Turning it on adds 23.3% to the world 2060 figure. Do not, until the country fits
are re-estimated on O&D: 45 of the 137 sit at or beyond the applied bound of 2.2 and are
clamped, the highest at 3.48. See `MEASUREMENTS.md` section 1.

**8. The track record question.** The dashboard shows a track record produced by something
the live forecast does not import. John has parked it. It has to be answered before the
OGF is sold.

## 7. The deck itself

Target: an Observatory OGF deck in the shape of the Boeing Market Overview, for the team
to review the forecast against and for use with third parties, and ready for John's
October meeting with Wendy Sowers alongside her estimated 2026 numbers.

Not started. The analysis behind it largely is: the region reconciliation, the comparator
figures and the slide inventory are done. Build the fleet wedge first, then the six slides
we can fill outright, then take the cargo and fare-level decisions.

House style applies: Arial, A4, author and last-modified-by set to "Avia Solutions",
proofing language en-GB, no em or en dashes anywhere including chart labels, a source line
on every figure, and every chart carrying its unit and period with actual and forecast
distinguished.

Copyright Avia Solutions Limited. All rights reserved.

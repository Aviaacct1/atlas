# Next session: the World Bank ingest and the stage length path

Paste everything below the line into a new Cowork session.

---

We are continuing the Observatory Global Aviation Forecast. The deck exists and
regenerates; what is left is two forecast changes and two method decisions.

Mount these folders: `C:\src\atlas`, `C:\src\meridian`, `C:\Avia`, `E:\Avia`,
`C:\Users\Carte\OneDrive\Documents\Claude\Projects\Avia Global Forecast Tool`.

Read first, in this order:

1. `C:\src\atlas\HANDOVER - Base rebuild and the open decisions - 9 August 2026.md`, the
   full state.
2. `C:\src\atlas\MEASUREMENTS.md`, sections 3, 3a and 4. Section 4 is the job.
3. `C:\src\atlas\CHANGELOG.md`, entries 108 to 114.
4. `C:\src\atlas\SWITCH_REGISTER.md` and `CAPABILITY_AUDIT.md`, what is switched off and
   what nothing calls.

Confirm the tree before building anything:

```
cd C:\src\atlas
py -3.12 -m pytest tests -q                      expect 336 collected, 335 pass, 1 skip
py -3.12 scripts\validate_repo.py                expect exit 0
py -3.12 scripts\compare_regions_boeing.py       expect world Avia 3.3% v Boeing 4.2%,
                                                 China -2.0pp, Eurasia -1.0pp
py -3.12 -c "import json;d=json.load(open('data/global_scope_summary_2025.json'));print(d['world_od_m'],d['airports_total'])"
                                                 expect 3341.3 and 4202
```

If any of those differs, stop and find out why. In particular the world base year is
3,341.3m as of 9 August, not the 3,139.7m that appears in anything written before that.

## Hard rules

* Git commands run in my PowerShell, never through the session's file mount. A mount
  blocks unlink, so even `git add --dry-run` leaves a stale `.git\index.lock`. You write
  code and run tests; I commit. Pull before editing, push after. Meridian and Atlas both
  moved on 9 August and Atlas depends on Meridian, so pull Meridian first.
* Every figure names its source in the same sentence: a file read this session, an
  Egnyte file, a URL searched this session, or the locked model. Nothing from recall. If
  there is no source, say so and ask.
* Do not change a forecast number without telling me first and measuring the effect.
  `global_demand.run_global` takes `base_od` and `airport_meta` as arguments, so a
  measurement can be run in memory without touching a file. Use that.
* Avia house style throughout, including chart labels: UK English, no em or en dashes
  anywhere, author and last-modified-by "Avia Solutions", proofing language en-GB. Every
  chart states its unit and period and distinguishes actual from forecast.
* Build the guard before the analysis. On 9 August the guards caught a two-way anchor
  read as one-way, an ingest that wrote its output before checking it, and a detector
  reading monthly peaks as annual totals. Each would have produced a plausible table.
* Read the file the code reads. The propensity finding was nearly published off the
  dashboard payload rather than the file the engine opens, and the wrong file supported
  a much larger claim.

## The work, in order

**1. Ingest the World Bank fully. This is the priority and it is agreed.**
`data/worldbank_pop_gdppc.json` holds 30 countries. `global_demand.country_headroom`
returns None without a record, so the propensity ceiling cannot bind on 734m of 3,341m
outbound O&D, 22% of the world, and those countries compound at regional GDP growth with
no saturation at all. Russia, Korea, Vietnam, Canada, Malaysia and the Philippines are
among them. Extend `scripts/ingest_*` to cover every country in the base, from the World
Bank population and GDP per capita PPP series, then measure the effect region by region
in memory before writing anything. Expect it to pull those countries down, so the world
figure falls and the gap against Boeing widens. Tell me the number before it is
committed. See `MEASUREMENTS.md` section 4.

**2. The stage length path.** Our RPK conversion holds stage length constant, so our RPK
CAGR is our passenger CAGR, while Boeing's carries their stage length growth. Measured
growth is 0.6% a year at world level over 2015-2025 and applying it closes two thirds of
the gap. Build a stated path per region, converging rather than a flat extrapolation of
history, because a single historic rate over-corrects Oceania and Northeast Asia. Bring
me the path and the before and after before it goes in. `scripts/gap_decomposition.py`
already produces the comparison.

**3. Then bring me two method decisions.** How Beijing Daxing enters the terminal model,
which iterates `aci_hub_calibration_2024.json` and does not contain PKX, so Daxing is in
the base and still absent from every published figure. And whether to re-estimate the
airport regressions on combined city system panels, Beijing as PEK plus PKX plus NAY and
Chengdu as CTU plus TFU, which is the last channel that could move China towards Boeing.

**Deliverable.** The measurements first, as numbers I can decide against, then the
changes, then a regenerated deck and `py -3.12 scripts\check_deck.py` clean. Everything
by script, committed, so it rebuilds when the forecast moves.

**What I want from you as you go.** Tell me when something cannot be done and why, in one
line, rather than filling it with something approximate. If a hypothesis of yours turns
out wrong, say so plainly and record the correction; three of mine were wrong on 9 August
and the value was in the data contradicting them, not in the guess.

Copyright Avia Solutions Limited. All rights reserved.

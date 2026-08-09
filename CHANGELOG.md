# Change log - method and build

Method changes go here before they enter the Python production path (Method Spec 10).
Author: Avia Solutions.

## 5 July 2026 - Pipeline adjudication (Fable Tier 1), amends Method Spec v0.1 -> v0.2

Adjudication document: "Pipeline Adjudication (Fable) - Tier 1 decisions", answering the
Deep-Thought Brief v0.1. To be folded into Method Spec v0.2 and Output Spec Draft 7.

1. **Method Spec 6.4 (both-ends check).** Replace "capped by the binding end / min()" with
   multiplicative composition and sequential attribution: flow_c = flow_u x rho_o x rho_d_bar;
   origin books flow_u x (1 - rho_o); destination books flow_u x rho_o x (1 - rho_d_bar). The
   three sum to flow_u by construction. Min() under-suppressed double-constrained flows and its
   argmin re-attributed suppression discontinuously. Published airport capacity requirement stays
   U_a - C_a from the airport's own solve. New identity T-D (build-stopping at flow level). New
   monitoring check: flow-level suppression vs airport CapReq within 2% [P1].

2. **Method Spec 5.2 / 6.2 (connecting under constraint).** Constrained connecting is defined as
   unconstrained connecting x the hub's own retention (connecting spilling at 1.5x pro-rata), not
   re-grown from constrained feed flows. The neglected feed-market term is measured every build by
   the re-grow diagnostic (identity T-E) and reported per hub; escalate to a damped iteration for a
   vintage only if any hub's gap exceeds 2% of its terminal [P1]. Known bias stated: constrained
   connecting slightly overstated, so hub capacity requirement slightly understated.

3. **Method Spec 7.4 (leg-based RPK).** Three ledger conventions become normative: connecting is
   onward-only; legs are emitted from outbound records only; domestic legs are emitted at half
   weight from each end. Scope: v1 models at most one connection per itinerary. New identity T-C
   added to reconciliation: total emitted leg-pax = [intl outbound OD + domestic OD / 2] + CONX.

4. **Method Spec 6.3 (catchment redistribution).** Single simultaneous pro-rata-to-headroom
   allocation per catchment; receivers fill to at most K and do not re-run the spill curve on
   received traffic; residual beyond total catchment headroom is suppressed. Order-free and
   terminating by construction.

5. **Architecture.** Two-pass build confirmed (Fable Q1); no fixed point in v1. Pass 1 unconstrained
   (exact), pass 2 constrained. Build-stopping identities registered: T-A (final-to-next
   row-stochastic), T-B (TERM = OD + CONX), T-C (leg ledger), T-D (both-ends), T-E (re-grow
   diagnostic). All five are enforced in avia_forecast/aggregate/reconcile.py and covered by tests.

Status: adjudicated by John and Fable, 5 July 2026. Jess reviews against the working model; her
dispositions and any Draft 7 markups append here with adopt/adapt/decline.

## 5 July 2026 - Pipeline adjudication Part 2 (Fable Tier 1 Q4-Q6), further amends Method Spec v0.2

Adjudication document: "Pipeline Adjudication Part 2 (Fable) - Tier 1 questions 4-6". Read with Part 1.

5. **Method Spec 5.4 (final-to-next at the base year).** Overturns the identity default, which
   silently overstated RPK on connecting journeys from secondary airports (the origin emitted a full
   origin-to-region leg while the hub also emitted the onward leg; T-C still passed on passenger
   counts, so nothing caught it). New default: Sabre GDD-derived M per airport (internal parameter
   estimation under Work Order 4.b, snapshotted per vintage). Fallback where GDD is thin: a
   nonstop-service rule, direct share 0.7 [P1] with the remainder via the designated hub, or 100% via
   hub where there is no nonstop service, from a versioned hub-allocation reference table. Identity is
   permitted only for own-region short-haul and domestic cells. New identity T-F (build-stopping, base
   year): the one-connection journeys implied by M equal the base-year connecting total within 10%
   [P1]; outside tolerance, CONX is scaled pro-rata to M (the better-estimated object) and flagged.

6. **Method Spec 7.2 (mirror reconciliation).** Always-canonical confirmed. Two riders: the exception
   report shows the distribution of signed mirror gaps by country pair across years, so systematic
   partner-side bias is visible as a pattern; canonicality is per-country-pair configuration in the
   sources table (a review may flip a pair), versioned and applied at the next build, never a
   build-time branch.

7. **Method Spec 6.3 (catchment redistribution).** Supersedes Part 1's fill-to-K wording. Receiving
   headroom is measured to theta*K where theta is the spill-start threshold (0.85 [P1]), so no
   receiver reaches its own spill threshold and the no-cascade property is exact: iteration has
   nothing to converge on. Slightly overstates suppression (capacity between 85% and 100% left unused
   by redistribution), conservative on the capacity requirement.

Net bias direction, reported per vintage in the exception report: hub capacity requirement if anything
understated (Part 1 Q1); double-constrained flows and tight catchments overstated (Q2, Q6).

Identities now T-A through T-F, all enforced in aggregate/reconcile.py and covered by tests (45 passing).

## 5 July 2026 - Input-contract audit (Fable) and the analyst cockpit design

Adjudication document: "Input Contract Audit and Analyst Cockpit Design (Fable)". Answers the
data-chain / cockpit brief. Produced the Input Data Specification v0.1 (project folder), the mirror
of the locked Output Contract.

8. **New primitives declared.** R7 hub_allocation (Q4 fallback), R13 destination-country base shares
   (OUT-19, same GDD extract as R10 final-to-next), R14 comparator_values (OUT-17), F15 base-year
   fare levels in $ (OUT-27). Added to the input register with grain, units, licence class and status.

9. **Gap G1 (fare-history construction), the largest finding, adjudicated (recipe [P1], pending John
   and Jess confirm).** The method estimates bF against a real fare index F(r,s,t) but no recipe built
   25 years of it outside Jess's UK sheet. v1 recipe: DB1B real yields for North America (full depth,
   class A, the anchor and method validator); GDD-derived fare levels for all regions 2020-25
   (in-licence); the template's cost-driven construction (fuel + carbon pass-through + tau) for all
   regions pre-2020, calibrated so its 2020-25 overlap matches the GDD window; UK cross-checked
   against CAA survey fares. Consequence to state in the methodology: outside North America, pre-2020
   bF identification leans on cost-driven fare variation (the 2008 and 2014-16 fuel cycles); the
   reliability rule and pooling protect the weak-identification cells. Homed as
   constructed_series.fare_history_recipe [P1]. bF sensitivity to the recipe is a UK-pilot test.

10. **Parameter homes closed.** H1 CPI deflation convention and H2 SAF lifecycle credit added to the
    book; H3/H4-diagonal/H5 were already homed during the pipeline build; H6 scenario driver deltas
    partial; H7 fare recipe homed as pending. See the input register Parameter Homes sheet.

11. **Dead weight excluded from v1 ingest:** CAA punctuality, CAA survey journey-purpose fields,
    alliance/hub-carrier map (R12, v1.1), Peak Hour DB (design-day add-on), Jess sheet-08 C35
    redistributed-share (superseded by the pooled theta-K allocation, retained as a local Excel
    approximation and noted in the ReadMe).

12. **Analyst cockpit architecture (design accepted, build after the engine runs end to end).** The
    cockpit is a fourth run mode of the same engine, not an application: base vintage + override pack
    -> run -> delta pack, Excel as the editing surface, the parity harness reversed to become the
    export writer so every deliverable self-verifies against the template. Run modes: product vintage
    (append-only), sandbox, project (consulting), backtest. Override pack is a declarative diff,
    hash-identified; the UI never mutates state; promote-to-vintage is an explicit governed action.
    The delta engine IS the OUT-20 vintage bridge (one code path). Reason-code enum shared with the
    product overlay. Open for John: E1 promotion governance, E2 client-data flywheel policy (legal),
    E3 runtime budget. v1 scope: pack loader + run-id hashing, delta engine, template-inhabiting Excel
    writer + reversed parity check, project scaffolder, static delta HTML report.

## 5 July 2026 - Two-purpose cockpit confirmation and fare-elasticity strategy (Fable)

Adjudication document: "Two-Purpose Cockpit Confirmation and Fare-Elasticity Strategy (Fable)".

### Part A - cockpit (design confirmed; build after the engine runs end to end)
13. **Two named run modes.** global-sandbox (Avia team edits shared book deltas; can lead to a governed
    promote-to-vintage) and bespoke-client (consultant; edits client facts and local judgements; client
    deliverable only, no promote path). Pack schema splits into book-deltas and input-deltas sections.
14. **Guard G-V (vintage purity), build-time not policy.** Every stored series and parameter carries a
    provenance tag public or project:<name>. The product vintage builder refuses to run if anything in
    its dependency graph carries project provenance, so client data cannot reach the global tool even by
    accident. The E2 flywheel is struck from the roadmap as a default; whether anonymised aggregate
    learning may ever inform global calibration is a separate John-and-legal decision, and until taken,
    G-V treats even aggregated project-derived values as project provenance. Insight may travel (motivate
    a public re-estimation in sandbox); data does not.

### Part B - fare-elasticity strategy (amends Method Spec v0.2; parameters to the book)
15. **D_supply dummy, separate from D_covid (Method Spec 4.3).** 2020-22 (collapse) and 2023-24
    (supply-constrained boom: maintenance backlogs, Pratt GTF groundings) are opposite-signed anomalies;
    one dummy cannot span both. D_covid 2020-22 and D_supply 2023-24 (year range BOOK [P1], reviewed at
    the pilot). Added to the assumptions book and the Level 1 fit.
16. **Estimation-vs-reporting fare series split (Method Spec 4.2a / F5).** The estimation fare series for
    2020-24 is the cost-model counterfactual (fuel, carbon, tau), not observed fares, so the anomalous
    fare-demand co-movement never enters estimation. Observed/GDD fares from 2025; observed fares still
    used for base-year levels (F15) and reporting. Splice dates BOOK [P1].
17. **Restricted Level 1 (Method Spec 4.3/4.4).** bF is fixed at the segment value; the airport
    regression estimates bG on the fare-adjusted series ln P - bF*ln F, which removes the fare-GDP
    collinearity and tightens bG's t-statistic (tested). No airport-level fare elasticity anywhere: bF
    lives at Level 2 (pooled) and Level 3 (literature-anchored). Reliability re-scoped: T1/T2/T3/T6 test
    bG at Level 1; the bF sign and range tests move to Levels 2-3.
18. **Identification and validation.** bF identified primarily from the clean 2014-16 oil collapse, with
    2011-13 supporting and 2008 conditional on the GFC dummy; 2020-24 contributes nothing by
    construction. V-FARE added to the backtest suite (Method Spec 9): US segment bF estimated twice
    (DB1B observed vs cost-driven) must agree within +/-0.15 [P1]. GDS fares used for changes, never for
    levels (BOOK).
19. **Residual risk stated.** The cost-driven construction identifies the cost-to-demand pass-through
    bundle (theta*bF), not bF alone; contained by internal consistency (same theta forecast and estimate),
    by V-FARE unbundling against DB1B transaction fares, and by the standing priors, bounds and reliability
    rule. Proven by the synthetic supply-anomaly test (B.4): naive estimation on observed fares attenuates
    bF to circa -0.18; the recipe recovers -0.59 against a true -0.60.

Fare-strategy code and the B.4 proof are in avia_forecast/estimate (level1 restricted fit, D_supply,
synthetic.make_fare_anomaly_cell, validate.vfare_agreement); 50 tests passing. The cockpit G-V guard and
the two run modes are recorded here for the cockpit build, which follows the two-pass engine.

## 5 July 2026 - Two-pass orchestration runs end to end (UK pilot)

The single build command now runs the whole chain on a synthetic UK pilot (LHR hub + LGW feeder,
London catchment, feed routing so the base-year identities hold by construction). Pass 1 unconstrained
(demand -> region-pair flows -> connecting -> next-destination -> terminal), pass 2 constrained (spill
-> theta-K redistribution -> both-ends -> constrained connecting -> leg-based RPK). All identities
T-A..T-F run in one build; T-A/T-B per airport-year, T-C on the leg ledger, T-D per flow, T-F at the
base year, plus constrained <= unconstrained on the own-solve, CapReq >= 0, and catchment conservation
(own-constrained + redistributed + suppressed = unconstrained). Own-solve constrained terminal is
reported as term_c; redistribution received is a separate spill_redistributed line; term_served is the
sum. Deterministic (byte-identical reruns). New: avia_forecast/fixtures.py, avia_forecast/pipeline.py;
build.py wired to pipeline.run. Illustrative result: LHR capacity requirement rises to ~7.7m by 2030;
global unconstrained RPK 345 -> 397 bn over 2025-2030. 55 tests passing.

## 5 July 2026 - Estimation ladder complete (Levels 2 and 3)

Level 2 (estimate/level2.py): country-segment pooled panel, LSDV fixed effects (cell intercepts,
common bG and bF), WLS weighted by base-year pax share with an airport-level cap (water-filling so the
cap holds after redistribution; degenerates to equal shares when infeasible), standard errors clustered
by airport, minimum panel 3 cells / 45 obs. This is where the segment fare elasticity is estimated
(Fable Part B). Tested with T1-T2 only; a failure routes the cell to Level 3. Level 3
(estimate/level3.py): precision-weighted combination of the pooled estimate with the literature prior
(se_lit 0.25), clipped to the applied bounds; segment defaults for bG by maturity and bF from the
Method Spec 4.5 table. Monte Carlo recovery on synthetic panels: mean bG 1.30, mean bF -0.60. With the
restricted Level 1 (bG airport, bF fixed at segment), Levels 1-2-3 and the selection rule now compose
the full mechanical ladder: applied bG from the airport where it passes, else pooled, else default;
applied bF always segment. 61 tests passing.

## 5 July 2026 - Outputs module: the engine-to-front-end contract

outputs/extract.py turns a pipeline run into a static JSON extract the front end reads and never
re-computes: per-level series (global, region, country, airport) for the unconstrained and constrained
cases, the capacity requirement, RPK, and region-pair flows, plus a tidy CSV writer and an exception
report. The pipeline gained flow_u and per-airport RPK to feed it. A pilot extract is emitted to the
project folder ("Dashboard Extract (pilot).json"): this is the file the dashboard/cockpit mockups load
to show real engine numbers instead of client-side toy series. Aggregation is tested (global = sum of
airports), determinism is tested, and the writers round-trip. This is the connection point between the
forecast engine and the mockups.

## 5 July 2026 - Real UK airport set, CAA data seam, extract schema for the mockup

The pilot is generalised from the two-airport toy to a real UK airport set (LHR hub plus feeders across
real catchments: London LHR/LGW/STN/LTN/LCY, Manchester, Birmingham, Edinburgh), 2025-2040, with
multi-catchment redistribution and the feed-routing model preserved so T-F holds by construction.
fixtures.build_base_od_from_caa is the real-data seam: drop a CAA Table 12.1/12.2 extract through the
CAA adapter and it replaces the illustrative base-year O&D. The pipeline is fully generalised to N
airports and M catchments; all identities still enforced. Illustrative run: global terminal 134 -> 208m
pax and capacity requirement 29.5m by 2040, concentrated at the London airports (LHR 18, LGW 5.9, STN
4.0). The dashboard extract now carries the full UK set. A schema note ("Dashboard Extract - Schema for
the Mockup v0.1") documents the JSON so the mockup binds to it directly. 67 tests passing.

## 5 July 2026 - Sabre GDD ingest path (base-year seed)

ingest/sabre.py reads a Sabre GDD 2025 O&D extract (CSV export from the QSI tool's sabre.duckdb, or a
duckdb file) into the tidy contract (airport x dest region x direction=out, od_pax, base year),
column names config-driven (sabre_columns in the source register), country->region via Annex A.
fixtures.build_base_od_from_tidy turns any tidy O&D source (Sabre or CAA) into the pilot base-year O&D;
make_pilot(base_od_override=...) applies it while keeping airport metadata. Tested end to end: a Sabre
extract seeds the UK pilot and the pipeline runs with all identities. Licence: Sabre is class C, used
here for internal base-year parameter seeding only (Work Order 2026 clause 4.b); no reconstitutable
extract is redistributed and displayed history in the product comes from class A (CAA). The real run
awaits the 2025 extract being placed in the project folder (C:\Avia\sabre.duckdb is outside the
sandbox mount). 70 tests passing.

## 5 July 2026 - REAL UK 2025 run: Sabre O&D + OAG distances (via the QSI stores)

The QSI tool's data stores are reachable (project-sibling folder): preagg.duckdb od_p2p (Sabre GDD
airport-pair O&D, 2013-2025, 1.16m rows) and qsi_wave_cache.duckdb boards (OAG schedules). The UK
pilot now runs on real data: base-year 2025 O&D by airport x region from Sabre (98% of UK O&D maps;
country->region via a comprehensive 123-country Annex-A map now in config/country_region.yaml), and
schedule-derived region distances from OAG block times (approximation pending true great-circle).
scripts/ingest_uk_real.py regenerates it from the QSI stores; the extract is emitted as "Dashboard
Extract (UK 2025 real).json". Result: global outbound O&D+connecting 88 -> 137m to 2040, capacity
requirement 31.6m by 2040 concentrated at the London airports (LHR 10.8, LGW 9.1, STN 7.3), RPK 207 ->
320 bn; all identities hold. STILL ILLUSTRATIVE: capacities (pending Jess's register) and the growth
path (fixture GDP 2%/yr and fixture elasticities) - the base year and distances are real. Next real
step: estimate elasticities from the od_p2p 2013-2025 history and wire real GDP, turning the growth
path real too. Licence: Sabre class C, internal base-year seed only (WO 4.b); nothing raw redistributed.

## 5 July 2026 - Real GDP driver (OEF) + cockpit build-update program

**OEF GDP wired.** The GDP driver now comes from OEF March 2026 (Egnyte), UK-Continental real growth
Base/Low/High -> the model scenarios, held at the last rate beyond 2032 (config/oef_gdp.yaml). The UK
growth path is now real: 88 -> 122m by 2040 Baseline, 138m High, 108m Low; capacity requirement 9.7 to
32.4m across the range. Only the elasticities remain fixture in the trajectory (real estimation from
od_p2p 2013-2025 is the next step).

**Cockpit build-update program logged.** "Opus Build Update - Cockpit Session Learnings" turned into a
sequenced, test-first plan ("Cockpit Learnings - Engine Build Plan v0.1", project folder). First
shaping item built: **A5 vintage clock** (avia_forecast/vintage.py + test): BY-relative elements (spot
years, CAGR windows, A/F labels, offset scenarios, DDFS year) roll with the base year; calendar anchors
(COVID 2020-22, recovery-vs-2019, backtest windows) do not. Method Spec v0.2 amendments this program
introduces, to fold into the change log as each lands: B1 propensity-to-fly maturity replaces the
maturity-decay parameter (4.5); B2 segment output splits + adding-up identities; E1/E2 cargo, GA, total
ATMs and DDFS on total ATMs (new Output Contract rows); A4 project-local reason-coded book overrides via
the fare index (G-V unchanged); D scenario types; F chart writer in exact Avia format. Sequencing per
section G: A1/A2 path-vector pack schema next, then B1/B2, then E, then C (BUM), then D and F.

## 5 July 2026 - Cockpit A1-A4: path-vector pack schema + segment grain

avia_forecast/cockpit/pack.py: every input is an annual path vector, never a scalar. UI shorthand
expands at pack level - a number holds flat, "a>b" ramps linearly from base year to horizon, "engine"
follows the endogenous drift, a dict is an explicit vector (A1). Inputs carry (input x segment) grain
with blank-falls-back-to-engine (A2). A client path replaces the engine's endogenous drift (A3).
Project-local reason-coded book overrides (tau, jet fuel, carbon, SAF, efficiency, LCC share) apply to
the run through the fare index and never write back to the book, and cannot be a non-permitted param
(A4, guard G-V; provenance 'project'). Four acceptance tests green (ramp hits 5.0 at BY and 9.0 at
horizon; long-haul-only seats override moves only long-haul ATMs; client path suppresses endogenous
drift; book override applies without mutating the book). Next per section G: B1 propensity-to-fly.

## 5 July 2026 - Cockpit B1: propensity-to-fly maturity (amends Method Spec 4.5)

avia_forecast/estimate/propensity.py replaces the maturity-decay parameter (Method Spec 4.5) with a
saturation model. Saturation share s = trips-per-capita / asymptote (region ceilings in the assumptions
book, overridable per catchment). Growth above the mature terminal rate is retained in proportion to
headroom (1 - s), so as traffic climbs the world curve toward the ceiling, s rises and growth decays
endogenously. fit_world_curve fits log trips-pc vs log GDP-pc (from Sabre/OAG trips, UN population, OEF
GDP per head) and also feeds the propensity chart F3. Acceptance tests green: monotone declining period
CAGRs; decay ordering follows saturation (Delhi-class keeps ~95% of excess growth, Manchester-class
~35%, matching the expected circa-90% and circa-one-third); saturation rises to but never exceeds the
ceiling. Config: propensity.region_asymptote_trips_pc, terminal_tpc_growth, income_elasticity_tpc.
Method Spec v0.2: section 4.5 maturity decay superseded by the propensity-headroom mechanism. Next per
section G: B2 segment output splits with build-stopping adding-up identities. UN population is the one
input still to stage (Egnyte / UN WPP), like OEF.

## 5 July 2026 - Cockpit B2: segment output splits (amends Method Spec)

avia_forecast/demand/splits.py splits total demand into domestic and international so domestic takes a
lower share of the excess growth over a common floor (domestic excess = 0.55 x international excess,
config segment_splits.domestic_excess_factor), solved so domestic + international = total exactly every
year. The transfer/O&D split follows the hub overlay, transfer + O&D = total. Both adding-up identities
are build-stopping (check_adding_up raises ReconciliationError). Acceptance tests green: exact adding
up; the 0.55 excess-growth ratio holds every year; the domestic share declines; identity violations
raise. Method Spec v0.2: segment splits and their adding-up identities added to section 4/7.
Next per section G: E1/E2 cargo, GA, total ATMs, DDFS on total ATMs.

## 5 July 2026 - Cockpit E1/E2/E3: cargo, GA, total ATMs, DDFS on total (new Output Contract rows)

avia_forecast/aggregate/atm.py: commercial ATMs from segment seats/LF; cargo tonnage GDP-linked
(config cargo.gdp_elasticity); cargo freighter ATMs from the non-belly share only (belly rides in pax
ATMs); GA pax and GA ATMs with their own growth; total ATMs = commercial + cargo freighter + GA; the
design-day flight schedule (design_day.fraction_of_annual_atm) consumes TOTAL ATMs, not commercial
only. Acceptance tests green: cargo tracks GDP at unit elasticity; belly excluded from freighter ATMs;
DDFS on total exceeds DDFS on commercial-only when cargo/GA present and coincides when absent; DDFS
moves with the inputs (no static values, E3). Method Spec v0.2: cargo tonnage, cargo ATMs, GA pax, GA
ATMs, total ATMs and DDFS-on-total added; new Output Contract rows (cargo_tonnage, cargo_atm, ga_pax,
ga_atm, commercial_atm, total_atm, ddfs). Next per section G: C (BUM, the 2-year bottom-up module).

## 5 July 2026 - Cockpit C: BUM 2-year bottom-up module

avia_forecast/cockpit/bum.py: route x airline x aircraft-variant x weekly-freq x LF schedule with
annual pax = freq x 52 x seats x LF (C1). Base year is analyst-editable: the gap between the base-year
pax input and the schedule total is shown and attributed by reason code (SCHED-GAP, LF-REVISION, ...),
with the unattributed residual visible and the schedule never silently rescaled (C2). Aircraft come
from the operating carrier's own fleet only; upgauging recomputes pax at that carrier's gauge (C3).
QSI candidates are deduplicated against the schedule and adds reconcile to the model total with a
wide-gap warning (C5). The BUM-implied near-term level anchors BY+1 exactly and tapers to the
long-term model path over N years (default 3), before the constrained pass, so the two methods merge
without a spike; shocks beyond the taper flow through (C6). Telemetry aggregates the reason-code
records as ingest-vs-reality evidence, public side of guard G-V (C7). Six acceptance tests green. C4
(free-form line add/delete/sort/filter) and monthly granularity are cockpit-UI/production concerns on
this engine core. Next per section G: D scenarios, then F impact table + chart writer.

## 5 July 2026 - Cockpit D: scenario register

avia_forecast/cockpit/scenarios.py: High/Low from a client-set compounding growth delta; a
pandemic-shaped demand shock (drop of `depth` at `year`, linear recovery over `recovery_years`, depth
exact at the shock year, baseline regained at year+recovery); a level event (carrier failure removing
`failure_fraction`, backfilled by `backfill_fraction` over a period, leaving a permanent loss of
failure x (1-backfill)); and a capacity timing slip that delays committed steps and bites only where a
step exists. Each transform feeds a whole-chain re-run. Four acceptance tests green (shock depth and
recovery exact; permanent loss after backfill; High>Base>Low; slip is a no-op with no step). Next per
section G: F impact table + chart writer (last item).

## 5 July 2026 - Cockpit F: impact table + Avia-format chart writer (program complete)

outputs/impact.py builds the impact table (all pax/ATM/cargo/capacity rows) at six spot years
(BY..BY+25 step 5), three period CAGRs and a signed vs-engine-baseline row per metric (F1).
outputs/chart_format.py pins the exact Avia format: Office 2024 palette, "Source:" (never "Sources"),
20pt heading / 18pt axes / bottom legend / 18pt bold data labels, author "Avia Solutions" (F2/F4).
outputs/chart_writer.py writes the impact table plus an unconstrained-vs-capacity-requirement line
chart on a dedicated chart sheet, no gridlines, palette applied, author-stamped. A real deliverable is
emitted from the UK run ("Avia Global Forecast - UK Impact Table and Chart.xlsx"): total demand 88 ->
153m to 2050, capacity requirement vs the Low baseline shown as the signed row. Pilot horizon extended
to 2050 (BY+25) to match the impact table. Acceptance tests green. The world propensity chart (F3,
locked to TAS slide 10) and the remaining 24 chart families are the chart-gallery follow-on. This
completes the cockpit-session program A-G on the engine side (A5, A1-A4, B1, B2, C, D, E, F all built
and tested).

## 5 July 2026 - Cockpit output modules wired into the live pipeline

outputs/derive.py computes the impact-table rows from the pipeline run itself, not standalone
assumptions: dom/int/transfer/O&D from the region-resolved flows and terminal, commercial ATMs from
segment seats/LF, cargo tonnage (GDP-linked) and freighter ATMs, GA, total ATMs and the design-day
schedule. Identities enforced in test: dom+int=O&D, transfer+O&D=terminal, total_atm=commercial+cargo
+GA. The UK impact table deliverable is now engine-driven end to end (config atm_conversion,
cargo_base, general_aviation_base). Illustrative UK run: total_atm 583 -> 1,013k movements, DDFS 2.3 ->
4.1k design-day movements, all rows from the engine. ddfs added to the impact-table row set. Remaining
to make the trajectory fully real: propensity-maturity into the demand recursion (still constant
elasticity), real elasticities from od_p2p 2013-2025, UN population for the propensity curve; and the
same derived rows can be added to the dashboard extract JSON for the mockup.

## 5 July 2026 - Real population (UN/World Bank) and the fitted world propensity curve

Real population sourced online: World Bank API (UN Population Division series SP.POP.TOTL 2024) plus
GDP per capita PPP (NY.GDP.PCAP.PP.CD 2023) for 30 countries, saved to build/data/worldbank_pop_gdppc.json
(the UN dataportalapi endpoint erred; World Bank carries the same UN Population Division data). Real
trips per capita computed from the Sabre od_p2p 2025 outbound O&D by origin country over population, and
the world propensity-to-fly curve fitted: ln(trips_pc) = -13.995 + 1.30 ln(GDP_pc_PPP), 30 countries.
The fitted slope (income elasticity of trips per capita) is 1.30, independently matching the model's
income-elasticity assumptions. UK 1.64 trips/capita; India 0.11, China 0.37, US 1.57. Saved
data/propensity_world_2025.csv (the F3 chart data) and data/propensity_curve_fit.json;
propensity.income_elasticity_tpc set to the fitted 1.30. This gives B1 a real world curve and real
population. Next: wire propensity into the demand recursion and estimate real elasticities from od_p2p
2013-2025 (the last placeholders in the trajectory).

## 6 July 2026 - Real UN WPP population projections extracted and wired

John placed WPP2024_GEN_F01_DEMOGRAPHIC_INDICATORS_COMPACT.xlsx in the project folder. Extracted the
Medium-variant sheet, Total Population as of 1 July, for 30 countries 2024-2050, saved to
build/data/un_wpp_population.json (ISO2 -> {year: persons}). UK 69.1m (2024) -> 75.5m (2050), 0.34%/yr,
which confirms the earlier applied estimate. Wired as the population driver via
fixtures.population_series(iso2, years) (holds the last value beyond the file). The population driver is
now the exact UN medium-variant per-country series rather than applied regional rates; the propensity
curve base (World Bank 2024 population) and this horizon series are consistent. Remaining trajectory
work: feed propensity into the demand recursion using this real population, and estimate real
elasticities from od_p2p 2013-2025.

## 6 July 2026 - Real elasticities estimated from Sabre history + OEF GDP; UK pilot fully real

GDP history sourced from OEF on Egnyte (OEF GDP Forecast 31Jul2024 - GDP per CAP added): UK real GDP
constant 2015 prices 2013-2025 (ONS/OEF; 2020 COVID drop to 2,831,625 confirms the real series), saved
build/data/uk_real_gdp_oef.json. Income elasticities estimated from the Sabre od_p2p O&D history
2013-2025 per UK airport (restricted Level 1, D_covid + D_supply): LHR bG 1.33 (t 2.7, R2 0.83),
matching the independent world-curve slope 1.30 - a real cross-check. The reliability rule correctly
rejects the expansion-inflated regional airports (STN 2.97, LTN 3.74 fail T2 range) and all fall short
of the 15-obs Level 1 minimum (13 years), so mature hubs anchor near 1.3 and the rest pool. Applied bG
wired into the pilot per the rule outcome (LHR 1.33, LGW 1.25, others pooled ~1.2-1.3);
build/data/uk_estimated_bG.json. The UK pilot now runs FULLY on real data: Sabre 2025 O&D base, OAG
schedule distances, OEF GDP, UN WPP population, and estimated elasticities; global 88.2m (2025) ->
145.9m (2050), CapReq 38.8m, all identities T-A..T-F hold. Only remaining trajectory refinement:
feed propensity saturation into the demand recursion (further damps mature-market growth).

## 6 July 2026 - Propensity wired into the demand recursion (trajectory complete)

fixtures.propensity_demand_path builds the system demand multiplier from estimate.propensity.evolve
using real UN population, OEF GDP per capita and the fitted world-curve income elasticity (1.30);
growth above the mature rate is damped by remaining saturation headroom. pipeline.run(use_propensity=
True) applies it to the demand, keeping the per-segment fare effect. Fixed a units bug (base O&D in
millions vs population in persons gave zero trips-per-capita and no damping). Effect on the real UK
run: propensity brings the market to 124m by 2050 versus 146m at constant elasticity, and the capacity
requirement to 21m versus 39m, because the UK sits ~40% up its propensity curve and matures over the
horizon. Test asserts the damped path is below the constant-elasticity path and decelerates. The real
UK extract now uses propensity. THE UK PILOT IS NOW REAL AND MATURITY-AWARE END TO END: Sabre 2025 O&D,
OAG distances, OEF GDP, UN WPP population, elasticities estimated from 2013-2025 Sabre history, and
propensity saturation from the fitted world curve. All identities T-A..T-F hold.

## 6 July 2026 - Acted on Fable review (P1 fixes)

Fable's adversarial review ("Fable Review and Global Roll-out Plan") caught two real defects in the
propensity wiring and the identity coverage; fixed:
- **P1 propensity wiring**: replaced the national-multiplier override with per-cell damping
  (demand.od_recursion_damped): the airport's own income elasticity bG and the GDP driver mapping are
  preserved, and only the income growth in EXCESS of the mature terminal is scaled by saturation
  headroom (country-grain for now; per-catchment is Phase 1). The estimated elasticities now feed the
  trajectory again - Heathrow (bG 1.33) grows faster than Stansted/Edinburgh (1.20). Corrected real UK:
  88 -> 120m by 2050, CapReq 18m.
- **P1 T-E wired**: reconcile.regrow_diagnostic now runs every constrained year; constrained connecting
  (conx_c rows) and constrained RPK (rpk_c_bn) are emitted. T-E escalations are a separate soft
  `escalations` list on Results (not build-stopping); it correctly fires when LHR's connecting re-grow
  gap crosses 2% in the 2040s, exactly the Part 1 escalation trigger.
- **Honesty**: the real extract meta now lists the five remaining fixtures (segment fare elasticity,
  fare index placeholder, structural M/via-hub share, illustrative capacities, national-grain
  propensity) so no one screenshots it as fully real.
Remaining from the review (P2/P3, Phase 0-1): per-catchment saturation, asymptote drift, wire pooled
segment bF, build the fare index to the G1 recipe, global-shaped both-ends test fixture. Full global
roadmap and data-sourcing table captured in the Fable review doc.

## 6 July 2026 - John decisions on Fable escalations

- **No hard growth ceiling** (asymptote): propensity.evolve no longer clips at the asymptote; growth
  decelerates to the mature floor terminal_tpc_growth = 0.007 (~0.7%/yr) and continues (saturation may
  pass 1). od_recursion_damped carries the floor. Mature markets slow toward maturity, never stop.
- **Boeing/Airbus**: alignment with GMF/CMO toward the horizon is the goal, not a constraint - coherence
  check reports divergence, aim to converge at the back end.
- **OAG licence**: current licence in hand, renews October; product rights to be sorted like Sabre well
  before then. Not blocking the build.
- **Capacity registers**: hardest to source; owned in-office, likely Jolyon Kingham. Off the critical
  path until Phase 4 gate; start research now.
- **Airport set**: initially airports over 2m pax or the top 80% of national pax; goal is to model most
  airports over 500k pax forecast in each country. Refines Fable Phase 1 airport-selection rule.

## 6 July 2026 - Phase 0: real fare index + segment fare-elasticity estimation

- **Fare index built to the cost-driven recipe** (estimate/fare_construction.py, Method Spec 4.2),
  driven by the REAL EIA jet-fuel series from Jess's workbook (data/jet_fuel_eia.json): F evolves by
  fuel pass-through (theta, fuel share by segment, net of fleet efficiency, share-weighted) plus the
  real-yield trend tau. Long Haul index shows the real 2008 spike (136) and 2014-16 collapse (103),
  then a gentle real decline to 2050. Replaces the 0.997^t placeholder; fixtures.fare_index loads it.
  DB1B/GDD absolute fare LEVELS (F15) remain to source.
- **Segment fare elasticity estimated** (Level 2 pooled, from od_p2p O&D 2013-2025 + the constructed
  fares): comes out positive and expansion-contaminated on the short UK panel, so it correctly FAILS
  the reliability sign test and the applied bF falls back to the Level 3 literature defaults
  (-0.7/-0.7/-0.5). This confirms the fare strategy's own premise (fare elasticity is segment-level and
  literature-anchored, not identifiable from short endogenous samples); the values in use are the
  correct Level 3 default, not a placeholder. Extract meta relabelled accordingly.
- Corrected real UK run: 88 -> 130m by 2050, CapReq 26.7m (propensity-damped income + modest real-fare
  decline). Identities green; live dashboard refreshed.
Remaining Phase 0 (make-the-pilot-honest): per-catchment saturation (needs catchment populations),
global-shaped both-ends test fixture, then fold/lock Method Spec v0.2 and run parity vs Jess's template.

## 6 July 2026 - Per-catchment saturation (Fable P1.3)

Propensity moved from a single national saturation to per-catchment (fixtures.catchment_headroom_series):
each catchment's trips per capita = its member airports' O&D over its resident population; each airport's
income growth is damped by ITS catchment's headroom. UK catchment populations are [P1] inputs the QSI
catchment engine (app/catchment.py, locale population x propensity allocated by generalised cost, CAA-
survey calibrated) supplies precisely for the real build. Result: real per-catchment maturity - London
(headroom 0.13, saturated) grows at 1.0%/yr; Manchester 1.37; Birmingham (0.72 headroom) 1.67; Edinburgh
1.42. London matures, the regions have room, exactly the heterogeneity the national figure hid. Global UK
now 88 -> 117m by 2050, CapReq 14m (lower and more realistic: London, the biggest and most mature, is
damped correctly not at the national average). This clears Fable P1.3. Remaining Phase 0: global-shaped
both-ends test fixture, then fold/lock Method Spec v0.2 and run parity vs Jess's frozen template.

## 6 July 2026 - Capacity register (Phase 4 engine side) and airport-set scope (Phase 1)

Both built to design docs already in the project folder; recorded here for Jess and Nick
to confirm at the v0.2 lock. All parameters are [P1].

14. **Capacity register, two-field design (Method Spec 6.1; Capacity Register - Design and
    Sourcing v0.1).** schema.sql capacity_register extended to carry both capacity KINDS rather
    than one number: k_grade (A operational rate / B design annual pax / C none), declared
    movements per hour, operating hours, seats/LF, design_annual_pax_m, derived k_annual_pax_m,
    peak_spreading, engine-facing practical_capacity, committed_steps. New loader
    capacity/register.py reads the seed CSV and derives K per grade: A = mvts/hr x hours x seats
    x LF; B = design directly; C = unconstrained (K=0, read by airport_solve as no register
    entry). New book section capacity_register (operating_hours_default 5840, seats 150, LF 0.82,
    A/B reconcile tol 0.15, ATFM flag 0.5 min/arr). The two-field design is invisible downstream:
    the engine still consumes practical_capacity (pax/yr). Owner Jol.

15. **ATFM-delay validation proxy (reconcile).** New check_atfm_validation in aggregate/reconcile:
    an airport the register treats as unconstrained (grade C or no derived K) that shows chronic
    Eurocontrol arrival ATFM delay above the flag is surfaced in the exception report as a wrong or
    missing register entry. Flagged, not raised.

16. **Airport-set scope rule (Phase 1; John's rule).** New scope/selection.py. Include an airport
    if pax >= 2m OR it falls within the smallest top set of national pax making up the coverage
    target (80%); the rest of a country collapse into one residual pseudo-airport ({country}_RES)
    so national totals stay whole. A 500k goal floor is reported as a coverage gap (below-scope
    airports above it), not applied in v1. Data-source agnostic: runs on any (iata, country, pax)
    table, so it is identical for CAA, Sabre or OAG. New book section scope. Verified on a
    UK/France-shaped case: every >=2m UK airport modelled, EXT/NQY to residual, coverage > 98%.

Tests: test_capacity_register.py (6), test_scope_selection.py (5), test_both_ends_global.py (2).
Full suite 113 green.

## 6 July 2026 - Residual pseudo-airport, backtest, coherence (continuing the build plan)

17. **Residual pseudo-airport wired (Phase 1).** fixtures.partition_by_scope / apply_scope apply
    the scope rule to a country's airports and fold every below-scope airport into one residual
    pseudo-airport ({country}_RES): base O&D = element-wise sum of members, bG = pax-weighted mean,
    K = 0 (unconstrained), its own catchment. National O&D stays whole region by region (tested);
    the pilot runs with the residual present and all T-A..T-F hold. Fixed a latent bug the residual
    exposed: pipeline asserted served <= K unconditionally, but K<=0 is the unconstrained sentinel,
    so the guard is now "K<=0 or served<=K".

18. **Backtest module (Method Spec 9) + V-FARE.** backtest/backtest.py: per-region relative bias
    over the forecast window, naive GDP-multiple benchmark, RMSE beats-naive flag, acceptance by
    count of regions within the bias tolerance (min 6 of 8), all from the book. vfare_check =
    US segment bF from observed DB1B vs cost-driven counterfactual must agree within 0.15. Nothing
    raises; failures report through the exception layer. 5 tests.

19. **Coherence tests (Method Spec 8.2).** coherence/coherence.py: rolling-decade CAGR must sit in
    the plausible band (-3% .. 12%), flagged not raised; external_divergence compares whole-horizon
    CAGR with a Boeing/Airbus reference and reports the gap only - per John, OEM alignment is a
    horizon goal not a constraint, so nothing acts on it. 4 tests.

Full suite 125 green.

## 6 July 2026 - Global base-year data layer (Phase 2), from the QSI tool

20. **Global ISO2 -> region map** (avia_forecast/geo/regions_iso2.py, 241 codes, tested disjoint):
    the UK pilot's 8-region scheme extended worldwide (EU+UK = EU27+GB+GI; Other Europe incl NO/CH/
    TR/RU/Caucasus; North America incl Central America + Caribbean). Unmapped -> None (no silent
    bucketing). dest_region resolves Domestic relative to the origin country.

21. **Global base-year O&D ingest** (build/scripts/ingest_global_base.py): Sabre GDD od_p2p 2025 +
    airport_city_country.csv -> per-airport outbound O&D by destination region + terminal throughput.
    3,346m world O&D, 3,233 origin airports, 227 countries; ~3% unmapped small-airport tail reported.
    Outputs data/global_base_od_2025.json + global_airport_meta_2025.json. Sabre stays class C
    (base-year seeding only).

22. **Global scope + catchments** (build/scripts/scope_global.py): John's rule applied worldwide ->
    677 airports modelled, 141 residual pseudo-airports, 86.2% of world O&D captured; 642 metropolitan
    catchments (IATA city code, 27 multi-airport metros); 275 below-scope airports above the 500k goal
    reported as the coverage gap. Outputs global_catchments_2025.json + global_scope_summary_2025.json.
    Capacity left grade C (unconstrained) pending the register, per John (build in parallel).

Readout: "Global Base-Year Data Layer v0.1.md" (project root). Full suite 129 green. NEXT: Phase 3
multi-country pipeline (per-country hub allocation + final-to-next M from OAG, connecting on real
structure, propensity per country).

## 6 July 2026 - Phase 3a: global unconstrained demand run

23. **Multi-country demand run** (avia_forecast/global_demand.py + scripts/run_global_demand.py).
    The per-airport per-region recursion (4.1) scaled to every mapped airport: home-country GDP
    growth (regional [P1]), segment fare index (shared cost-driven [P1]), elasticity maturity by
    country GDP-pc PPP (>=25k => mature, else region default), income growth damped by propensity
    saturation for the 30 countries with known population (the large saturating markets). New book
    section global_drivers (gdp_growth_by_region, maturity threshold 25k, mature-region fallback).
    Result (Baseline): world O&D 3,140m (2025) -> 7,145m (2050), 3.34%/yr; Asia Pacific and Middle
    East ~5.0%/yr, mature EU+UK 2.1% / North America 2.6%, Africa 3.9%. Within 0.5pp of the OEM
    pax reference (3.6%); rolling-decade coherence band clean. Extract data/global_forecast_2025_2050.json.
    O&D only: connecting overlay + capacity constraint are Phase 3b (multi-hub) / the register.
    Per-country OEF GDP and full global population are the two data refinements that complete it.

Full suite 134 green.

## 3 August 2026 - Capacity method v0.4: peak hour share and the evidence record

24. **Peak hour share estimation** (avia_forecast/capacity/peakhour.py, book section peak_hour).
    The share of annual traffic falling in the design peak hour is estimated as a RELATIONSHIP
    across the schedule panel, not read off one year and held flat. Log-log OLS of peak hour
    passengers on annual passengers, international share and seasonality; the share is
    proportional to annual^(b-1) and falls as an airport grows. Two rules the module exists to
    enforce: peak-constrained airports are excluded from the estimation sample, because at a
    Level 3 airport the filed peak equals the declared parameter almost by construction and
    reports the declaration rather than demand; and the panel supplies the elasticity while the
    airport supplies the level, from its own unconstrained base-year share, with the fitted level
    used only where no usable observation exists. A perverse elasticity (b outside 0 to 1, which
    would mean the peak growing faster than annual traffic and would bring every constraint
    forward) is rejected in favour of the book fallback and flagged, never raised. The module
    consumes peak hour rates from the DDFS convention catalogue on a named convention; it does
    not compute the peak itself.

25. **Capacity evidence record and resolution** (avia_forecast/capacity/evidence.py, book section
    capacity_evidence, data/capacity_observations_france.csv). Two tables replacing the single-K
    row: capacity_observation, stored exactly as published and never converted in place, never
    overwritten (superseded instead), carrying source, locator, season, validity, basis, grade,
    machine_readable and two names; and capacity_resolution, holding the tests run, the tests NOT
    run with reasons, the binding constraint and year, K, the conversion parameters and a
    generated statement. Tests A to E (airfield on the tighter of runway and ATC, terminal by
    rate or by annual design, stands, statutory cap) run in the peak hour and report back as an
    annual figure and a binding year, so K rises over time as the share falls. Three rules are
    enforced in code rather than left to convention, each a failure the France test set produced
    or nearly produced: actual traffic can never be a constraint type; a declared "no limitation"
    is a different state from "no figure found"; and only a regulator decree may create a hard
    annual cap. Range flag where two tests bind within the book trigger. Validation: actual
    traffic above recorded capacity blocks (this alone catches Nice and Beauvais with nobody
    reading anything), and observed peak above the declared rate flags with the Level 3 lower
    bound caveat travelling with it. The engine contract is unchanged: capacity_for() feeds
    spill.airport_solve exactly as the v0.1 register loader did, so nothing downstream moves.

    France seed loaded as the first observation set: 17 rows across 8 airports, of which every
    COHOR coordination parameter is flagged not machine readable (published as images), Nantes
    and Bordeaux carry no quantified capacity by design, Nice's operator figure is superseded by
    the coordinator's no-limitation declaration, and Orly's statutory cap is recorded with the
    figure deliberately blank pending a read of the Legifrance decree.

Readout: "Capacity Method and Evidence Record - Design v0.4 - 3 August 2026.md" (project root).
26. **Peak hour panel build from the OAG store** (avia_forecast/ingest/oag_peak.py,
    scripts/build_peak_panel.py, sources.yaml section oag_schedules). Turns the schedule store
    into the airport-year panel that peakhour fits: annual passengers, the nth ranked busy hour,
    international share, a seasonality index and the constrained flag. Three guards, each a way
    to get a plausible but wrong panel: the convention is named on every row, so a panel can
    never silently mix the 30th busy hour with an absolute peak; the peak is ranked across every
    clock hour of the year rather than taken from the busiest day; and an airport-year below the
    coverage threshold is dropped rather than ranked, because a missing month gives an ordinary
    peak on a low annual total and biases the share upward exactly where history is patchy.
    Where the store carries seats and not passengers the conversion is stated on the panel report
    rather than presented as observed. describe_store() reports the tables and columns actually
    present so an unconfirmed schema is a one-line config correction, not an obscure failure.

    Store schema confirmed against C:\Avia\oag.duckdb on 3 August 2026: one table, `oag`,
    at SERVICE grain (days_of_op, eff_from, eff_to, local_dep_time, frequency, seats,
    seats_total, week, year), with dep_country present so the international share is a real
    field rather than an assumption. Mapping set accordingly. Two row filters remain to be set
    from evidence, not assumption, and scripts/inspect_oag_store.py reports both: dup_marker,
    since OAG carries the same physical flight once per marketing carrier on a codeshare and
    counting every row multiplies movements and seats on exactly the busiest routes at the
    busiest airports; and service_type, since freight, charter and positioning records sit
    alongside scheduled passenger services and the model convention is the passenger basis.
    Until the filter is set, the panel report says so in terms rather than staying quiet.
    The same script checks for effective-period overlap (the store is built from monthly
    downloads and the repo already carries a dedupe routine) and cross-checks the expanded
    operating dates against OAG's own SUM(frequency).

    A fourth guard added the same day, and the largest: row_grain. An OAG row is normally a
    SERVICE (one flight number, stated days of the week, an effective period), not one operated
    flight. Counting service rows straight into clock hours would count a daily service once
    instead of circa 210 times a season, giving a peak that is nonsense while still looking like
    a plausible number. With row_grain = service each row is expanded to one movement per
    operating date, matching the IATA days-of-operation pattern against isodow(), before the
    hours are ranked. Both grains are tested against synthetic stores.

    Store location is config or AVIA_OAG_STORE, never a literal (tool standard 4), and the store
    itself is never committed (standard 3). It currently sits on the dev PC as
    C:\Avia\oag.duckdb (per "STATE OF PLAY - Plain English", 29 July 2026: 200m+ rows, monthly
    OAG schedules, 2015-2019 complete, 2024-2025 in progress, 2020-2022 deliberately excluded);
    only the sources.yaml entry changes when it moves to the workstation. The column mapping in
    sources.yaml is a first guess against the QSI store shape and must be confirmed with
    --describe before the panel is trusted.

27. **OAG store read, 3 August 2026, and three defects found before any panel was fitted.**
    Diagnosed with scripts/inspect_oag_store.py against C:\Avia\oag.duckdb (255.2m rows, 4,911
    departure airports; 2015-2019 and 2025 complete, 2023, 2024 and 2026 partial and dropped by
    the coverage guard).

    (a) local_dep_time is HHMM with NO leading zero: "700" is 07:00. The first version split the
    first two characters as the hour and would have read 70. The morning bank, which is where the
    peak is, would have landed in hours that do not exist while still producing a number. Now
    left-padded, with a test that fails if the pad is ever removed.

    (b) seats, frequency and seats_total are VARCHAR, so three diagnostic queries failed on SUM.
    Now TRY_CAST throughout: one unparseable cell drops out instead of failing the build. Worth a
    separate look, since anything else comparing or sorting those columns is doing string
    comparison, where "9" sorts above "180".

    (c) Snapshot overlap, the largest. The store holds many weekly snapshots whose effective
    periods overlap, so one operating date is covered many times over. At Heathrow on 15 June
    2019, 51,375 rows cover the date, 8,320 after the row filter, from 15 distinct snapshots.
    Per snapshot that is 555 departures, the right order for a Saturday against the 630 to 720
    implied by John Carter's 70 to 80 ATM/hr across an 05:00 to 23:00 day with the evening taper.
    Summed it would imply 16,640 ATM in one day on two runways. That error reads as a big airport
    rather than as a bug, so build_panel now RAISES SnapshotOverlapError unless a snapshot rule is
    configured or allow_overlap is passed deliberately. The rule is not invented here: it comes
    from the existing C:\Avia\dedupe_oag_periods.py.

    Row filter set from evidence: dup_marker = '0' (the 'D' rows, 45.8% of the store, are
    codeshare duplicates of flights already present) and service_type = 'J' (99.1% of rows;
    C, Q, G and S are the remaining 0.9% and are not on the passenger basis).

28. **Store read directly, 3 August 2026: the grain was wrong and two filters were wrong.**
    C:\Avia mounted and oag.duckdb queried rather than inferred. Three corrections, each of
    which would have produced a plausible-looking and wrong panel.

    (a) The store is ONE ROW PER OPERATED FLIGHT, not per service. NZ1 LHR-LAX appears 30 times
    in the 2019-06 file, once per operating day, each row carrying frequency 1 and the full
    season window 2019-03-31 to 2019-10-20. So eff_from and eff_to are the SEASON window and
    must never place a row on a date; the period comes from the week key. Nothing is expanded,
    and the expansion built in CHANGELOG 26 does not apply to this store.

    (b) dup_marker is NOT a codeshare marker here and must not be filtered on. BA57 LHR-JNB,
    operated by BA with no operating-carrier override (carrier2 = '0'), carries dup_marker 'D',
    and 'D' is 84.7% of Heathrow's 2019 rows. The filter set earlier that day, dup_marker = '0',
    would have deleted most of Heathrow's real departures: 49,117 against 322,063. Removed.

    (c) The real duplication is cross-region. A flight spanning two regions is listed in both
    region files: NZ1 appears in both North America and Europe, 30 rows in each. Deduplicating on
    carrier, flight_no, dep_airport, arr_airport and local_dep_time, and taking the count from one
    region, gives 678 departures a day at Heathrow in June 2019 against 934 raw, a factor of 1.38.
    678 sits inside the 630 to 720 implied by John Carter's 70 to 80 ATM/hr across an 05:00 to
    23:00 day with the evening taper, so the rule reconciles to a figure he can vouch for.

    Open, and blocking: movements must count ARRIVALS as well as departures. The runway
    constraint is ATM, the panel reads dep_airport only, and arrivals and departures bank at
    different times, so the combined flow has to be built as one series rather than as twice the
    departure peak. arr_airport, local_arr_time and local_arr_day carry the other side.

29. **Panel builder rebuilt for the real store, and validated against Heathrow.**
    New avia_forecast/ingest/oag_store.py holds the store reading conventions in one place,
    lifted from scripts/backtest_seats_anchor.py so the backtests and the capacity work cannot
    drift apart: the preferred period tiling per region-year, the home region rule, the period
    span of every key shape, and the HHMM parse. oag_peak.build_panel rewritten on top of it.

    Five things it now gets right, each of which would otherwise give a plausible and wrong
    panel: nothing is expanded (the store is one row per operated flight); arrivals and
    departures are read as ONE combined flow, because the runway constraint is ATM and the two
    bank at different times, so the combined peak is not twice the departure peak; each airport
    is read from its home region file only; exactly one period tiling per region-year is summed;
    and an airport-year below the coverage threshold is dropped rather than ranked.

    Validation against Heathrow 2019, home region only, service_type J: 477,954 ATM, 82.3m
    passengers on the book load factor, 655 departures a day, and a 30th busy hour of 90.3 ATM.
    The daily figure sits inside the 630 to 720 implied by John Carter's 70 to 80 ATM/hr across
    an 05:00 to 23:00 day. The ATM and passenger totals should be checked against the published
    2019 figures before the number is used anywhere.

    Note the 90.3 ATM in the 30th busy hour. At a Level 3 airport the filed schedule is shaped
    by the declared coordination parameter, so an observed peak sitting at the declaration is
    expected and is exactly the case peakhour excludes from the estimation sample: Heathrow's
    filed peak reports its declaration, not its demand.

30. **First fit on the real panel, 3 August 2026.** 200 busiest departure airports, 2015 to
    2019: 979 airport-years across 197 airports, elasticity of peak hour passengers to annual
    passengers b = 0.818, r2 0.928. Share elasticity therefore -0.182: the peak hour share falls
    by circa 12% for every doubling of traffic. Three airport-years dropped by the coverage
    guard, and they are the right ones: BER 2018 and 2019 (0.17 and 0.16 coverage) and PKX 2019
    (0.44). Both airports opened mid-period, and the guard caught them with nothing told to it.

    What it means in the forecast: an airport growing at 3% a year for 20 years grows 1.81 times,
    so its peak hour share falls to 89.8% of today's. For a fixed declared hourly rate that is
    11.4% more annual throughput before the airfield binds, worth roughly 3.6 years of extra
    headroom on a 3% path. Holding the share flat, as the v0.1 convention did, would have brought
    every airfield constraint forward by about that much and overstated the global capacity
    requirement with it.

    Caveat, and it matters: this run passed no constrained list, so Heathrow and every other
    Level 3 airport sat inside the estimation sample. Their peaks are held down by declaration
    rather than by demand, which biases b downward and so overstates the decline in share. The
    fit should be read as a lower bound on b until the run is repeated with them excluded.
    peakhour.flag_capped_from_panel reads the capping out of the panel itself (peak growth far
    below annual growth over an airport's observed years) as a starting filter until the register
    carries declared rates, and build_peak_panel gains --auto-capped to apply it.

31. **The panel-derived capping filter, and the flaw the first run exposed.** Running the fit
    with --auto-capped excluded 58 of the top 200 and moved b from 0.818 to 0.822, with r2 up
    from 0.928 to 0.941. The elasticity being stable across two quite different samples is
    reassuring for the headline result. The exclusion LIST is not: Amsterdam, Paris CDG, Munich,
    Zurich, Vienna, Haneda, Narita, Sydney and Bombay are all there and belong there, but
    HEATHROW IS NOT, nor Frankfurt, nor JFK.

    The reason is a flaw in the rule as first written. It compared peak growth against annual
    growth and skipped airports whose annual traffic was flat, on the grounds that a flat airport
    is uninformative. But an airport so constrained that it cannot grow ANNUALLY is the most
    constrained case of all: Heathrow moved circa 1% in movements across 2015 to 2019 because
    there is nowhere to put another flight. The rule skipped exactly the airports it exists to
    catch. Corrected: a large airport whose peak hour is static across the window is flagged on
    that alone, with the size floor a book parameter.

    The list also carries probable false positives (Denver, Salt Lake City, St Louis, Austin,
    Tampa), where a bank restructure rather than a slot limit held the peak flat. So the filter
    stays what it was labelled: a starting proxy, to be replaced by the IATA Level 3 list, which
    the capacity register needs in any case.

32. **Elasticity settled: b = 0.82.** With the corrected capping rule, Heathrow, Istanbul,
    Brisbane, Congonhas and Phoenix join the exclusion list (63 of the top 200) and the fit gives
    b = 0.823, r2 0.940, on 665 airport-years across 134 airports. Three runs on materially
    different samples: 0.818, 0.822, 0.823. That convergence is the result. The peak hour share
    falls circa 12% per doubling of traffic, and the assumptions-book fallback moves from an
    assumed 0.90 to a measured 0.82.

    Frankfurt, Gatwick, JFK, Madrid and Barcelona remain outside the exclusion list, and on
    reflection that is right rather than a miss. The test is behavioural, not institutional: it
    asks whether an airport's peak hour stopped moving, and at those airports it did not over
    2015 to 2019. An airport that holds a declaration but still has headroom behaves in the data
    like an unconstrained one, and leaving it in does not bias the fit. The institutional Level 3
    list is still wanted for the register, but for THIS purpose the behavioural test is the
    better one.

33. **Heathrow 2019 checked against the published figures, and it reconciles.** The build gives
    477,954 movements against Heathrow's published "over 470,000", and 100.4m seats. Against the
    published 80.9m passengers those seats imply an actual load factor of 0.806, so the 82.3m the
    build reports is 1.7% high purely because the assumptions-book fallback load factor of 0.82
    runs 1.4 points above Heathrow's own. The seats extraction is exact; only the conversion is
    approximate, and it is labelled as such on every panel report.

    This does not touch the elasticity. The load factor cancels between the peak hour and the
    annual total, so the share, and therefore b, is independent of it. Where an airport's own
    load factor matters to an output, it should be read rather than defaulted.
    Source: Heathrow media centre, "Heathrow reports outstanding end to 2019".

34. **Panel build moved into SQL, and a capacity screen for every airport.** The date
    spreading and the busy-hour ranking ran in Python, which capped the practical panel at a
    few hundred airports. Both now run in the database: a period-key calendar, a per-pattern
    denominator, and a window function for the nth busiest hour. Heathrow 2019 reproduces the
    Python build exactly (477,954 ATM, 82.3m pax, 90.3 ATM in the 30th busy hour, share
    0.0201%), so the rewrite is a speed change and not a method change.

    That matters for the forecast rather than for the clock. A constrained SECONDARY airport
    spills traffic the engine would otherwise let through, and the airports with headroom are
    where that spill has to go, so the catchment redistribution needs both halves of the picture
    and a top-200 panel cannot give it. peakhour.capacity_screen now classifies every airport in
    the panel from its own filed schedules, with no declared rate needed:

      at_ceiling   large, and the peak hour has not moved across the window
      tightening   annual traffic growing, but the peak absorbing little of it, so the
                   growth is going into the shoulders. What an airport approaching a
                   ceiling looks like before it reaches one
      headroom     peak growing broadly in step with annual traffic

    The number to read is `absorption`, peak hour growth over annual growth. Near 1 the airport
    is still taking growth in its busy hour; near 0 it is not. build_peak_panel writes the screen
    to data/capacity_screen.csv and prints the busiest airports at or approaching a ceiling.

    Behavioural rather than institutional, and weaker than a coordinator declaration. It is the
    starting position for the airports the register has not reached, which is most of them, and
    it should be overwritten wherever a declared rate exists.

35. **First full-set run, and three faults it exposed.** 3,133 airports, 13,767 airport-years,
    2015 to 2019. The top of the screen is credible (DEN, PEK, LHR, AMS, PVG, CDG, HND, SFO,
    IST, MUC, SYD, BOM, BOG, SHA, VIE, CPH, NRT), which is the encouraging part. The rest is not
    yet trustworthy, for three separate reasons, all now fixed or flagged.

    (a) **Absorption is a ratio with a near-zero denominator at exactly the airports it is meant
    to describe.** Heathrow grew 1% in movements across the window, so a 0.65% fall in its peak
    reads as an absorption of -0.65, and Toronto came out at -4.97. Those numbers say nothing.
    Absorption is now reported as not meaningful where annual growth is below the static
    threshold, and it never entered the classification in the first place.

    (b) **794 airports came back as "tightening", against an IATA Level 3 list of about 205.**
    At a small airport the busy hour is a handful of movements and a year on year change in it
    is noise. The size floor now applies to the whole screen, and airports below it return
    "not_assessed" rather than a guess. Saying nothing is the honest output; the register will
    have to look at those one by one.

    (c) **The elasticity is not size-stable, so "settled at 0.82" was premature.** The full set
    gives b = 0.706 against 0.823 on the top 200, r2 0.946 either way. That is not noise, it is
    sample composition: 1,145 airports now, mostly small. A small airport runs one or two banks
    a day, so its peak hour share is structurally higher and behaves differently from a hub whose
    traffic is already spread. One log-linear line across a quarter of a million to eighty
    million passengers describes no part of the range, and the answer moves with whichever end
    dominates. peakhour.fit_by_size_class now fits within each class and the runner prints them,
    so the choice is visible rather than implied. For capacity work the elasticity that matters
    is the one at the sizes where constraints bite, which is nearer 0.82 than 0.71.

    Also noted, and not yet handled: Africa and the Middle East switch from half-year to monthly
    tiling between 2017 and 2018, so the peak in those regions is smoothed over roughly 180 dates
    in the early years and 30 in the later ones. Any growth comparison spanning that boundary is
    comparing two granularities. It does not affect the airports at the top of the screen, which
    are monthly throughout, but the screen should exclude cross-boundary comparisons in those two
    regions until the early years are re-pulled monthly.

36. **The size-class table, and two more of my own bugs it exposed.** The corrected full-set
    run gives the answer the day has been circling:

        under 1m        b 0.690   share elasticity -0.310   r2 0.542   513 airports
        1m to 5m        b 0.666   share elasticity -0.334   r2 0.704   403 airports
        5m to 15m       b 0.754   share elasticity -0.246   r2 0.762   123 airports
        15m to 40m      b 0.822   share elasticity -0.178   r2 0.605    66 airports
        40m and above   b 0.917   share elasticity -0.083   r2 0.704    32 airports

    Monotonic above 5m, and the 15m to 40m class reproduces the top-200 fit of 0.822 exactly,
    which is a real internal check rather than a coincidence: that band dominated the top 200.
    The reading is that a large airport is already spread across the day, so its peak absorbs
    growth nearly in proportion (b 0.917, share falling only 5.6% per doubling), while a small
    airport running one or two banks has far more room to spread and its share falls three times
    faster. The single-line 0.706 is an average of populations that behave differently. The book
    now carries the table, and the single fallback is the 15m to 40m value, which is the size at
    which airfield constraints typically start to bite.

    Two bugs of mine that the table made visible. The runner printed "(fallback in use)" against
    every class, which was wrong and would have led to the table being dismissed: the fallback is
    used only where the elasticity comes back perverse or the sample is too thin, whereas a low
    r2 flags the LEVEL and keeps the estimate. Within a narrow size class r2 falls because the
    spread of annual traffic is small, which is arithmetic and not a fault, so the fit now carries
    the standard error of b and the runner prints it. And flag_capped_from_panel still held its
    own copy of the capping rule, so it excluded 813 airports from the fit while the screen called
    43. It now derives from capacity_screen: one rule, not two.

    The screen also gained a second, much lower floor. A static peak only means a ceiling at a
    large airport, so that call keeps the 150,000 movement floor, but "does this airport have
    room" is a fair question far lower down, and it is the question that matters for spill. With
    one floor at 150,000 the screen said nothing about 2,828 airports, which is exactly the
    population the redistribution needs.

37. **The standard errors show the size classes are the wrong shape, and the fit is now a
    curve.** With the one-rule fix in place the exclusion count fell from 813 to 190, which is
    the right order against an IATA Level 3 list of about 205, and the class table came back
    with errors:

        under 1m        b 0.676 +/-0.013     1m to 5m   b 0.664 +/-0.010
        5m to 15m       b 0.754 +/-0.018    15m to 40m  b 0.822 +/-0.039
        40m and above   b 0.917 +/-0.050

    Testing adjacent classes: under 1m against 1m to 5m gives t = -0.7, 5m to 15m against
    15m to 40m gives t = +1.6, and 15m to 40m against 40m and above gives t = +1.5. None of
    those is separable. But the ends of the range are: 1m to 5m against 15m to 40m gives
    t = +3.9, and under 1m against 40m and above gives t = +4.7.

    Every step inside the noise while the trend across them is emphatic is the signature of a
    CONTINUOUS relationship forced through arbitrary boundaries. The classes were a reasonable
    first cut and the data has now rejected them: an airport at 14.9m passengers should not get
    a different parameter from one at 15.1m for no reason that exists in the evidence.

    peakhour.fit_curved fits ln(peak) on ln(annual) and its square, so the elasticity is
    b1 + 2 b2 ln(annual) and varies smoothly with size. The curvature term carries its own
    standard error and the fit reports itself unusable where that term cannot be told from zero,
    so a straight relationship is never dressed up as a curved one. The runner prints the
    adjacent-class tests and the curved elasticity at 0.5m, 2m, 10m, 25m and 60m.

    The class table stays in the book as the readable summary and as the fallback. The curve is
    what the engine should use.

38. **Curvature confirmed, and then a caution that reverses the recommendation.** The curved
    fit gives a curvature term of +0.02265 against a standard error of 0.00140, so t = 16.2 and
    the relationship is unambiguously continuous rather than stepped. Elasticity at 0.5m 0.621,
    at 2m 0.683, at 10m 0.756, at 25m 0.798, at 60m 0.837.

    But set the curve against the classes and they agree closely from 2m to 25m (gaps of 0.1 to
    1.6 percentage points of twenty-year throughput) and diverge at both ends: 4.0 points at
    0.5m and 5.1 points at 60m. The divergence at the top is worth about 1.6 years of headroom
    at exactly the airports where capacity is the binding commercial question. There, the class
    fit is DIRECT local evidence (32 airports, 145 airport-years, b 0.917 +/-0.050) while the
    curve is a global quadratic extrapolating away from the only data that speaks to the case,
    pulled by a population of small airports that has nothing to do with Heathrow.

    Recommendation, revised within the hour: use the curve between roughly 2m and 25m where the
    methods agree and the evidence is dense; prefer the top class fit above 40m; and stop
    modelling. Five decisions have now been taken on one evening, on one data source, five
    years, by the same person who wrote the code, and each run has exposed a fault in the one
    before it.

39. **Blind test built (scripts/backtest_peak_share.py).** 2025 is complete in the store,
    monthly-tiled in every region, and has never been seen by any of these parameters. The
    script fits on 2015-2019, projects each airport's peak hour share forward from 2019 using
    its ACTUAL 2025 traffic growth, and scores four methods against what the schedules say
    happened: flat share (the v0.1 convention), a single elasticity, the class elasticity and
    the curve. Actual traffic rather than a forecast is used deliberately, to isolate the share
    projection: with the demand forecast in the loop a good score could be two errors cancelling.

    Scored overall and by size class, on median absolute error and the share of airports within
    10% and 20%. The reading rule is set before the result, not after: if flat wins, the whole
    size-varying apparatus is not earning its keep and should be dropped. If the methods sit
    within a point or two, prefer the simplest that beats flat. Only a clear margin justifies
    the curve, because it is the hardest to explain to a reviewer.

    Expect it to be harsh. 2019 to 2025 spans the pandemic and the schedule restructuring that
    followed, so an airport that rebuilt its bank structure will score badly on every method.
    That is the point: a parameter that only works across undisturbed years is not one to put
    in front of a client.

40. **2025 blind test: the simple answer wins, and the sophistication does not pay.**
    Fitted on 2015-2019, each airport's share projected to 2025 on its ACTUAL traffic growth,
    scored against the schedules. 2,096 airports in both years. Median absolute error:

        flat 17.7%   single 15.1%   class 15.1%   curve 15.0%
        within 20%:  flat 55.2%    single 61.5%   class 61.2%   curve 62.4%

    All three modelled methods beat holding the share flat by about 2.7 points of median error,
    removing roughly 15% of it, and they finish within 0.1 of each other. The rule was set before
    the run: prefer the simplest method that beats flat. So the SINGLE elasticity is the
    operating choice and goes into the book at 0.696. The class table and the curve are kept for
    reference and did not earn their complexity. The curve took two hours to build and justify
    and is worth 0.1 of a point.

    Two things the test does NOT settle, and both matter. Above 15m passengers no method
    meaningfully beats flat (15m to 40m: 9.9% flat against 9.7% single). The reason is that
    traffic barely moved at those airports between 2019 and 2025, so the elasticity had almost
    nothing to work with. Over a twenty-year forecast at 3% growth traffic rises 1.8 times and
    the elasticity will matter a great deal, but this window cannot check that. And at 40m and
    above the curve does win, 8.0% against 9.6%, but on 37 airports with identical within-10%
    and within-20% distributions, which is inside sampling noise.

    The most useful number from the whole exercise is the error itself. A median 15% error on
    the projected share is a 15% error on the implied annual capacity, which at 3% growth moves
    a binding year by about 4.7 years. That is now recorded in the book and it is a far stronger
    argument for reporting a binding-year RANGE than the convention-divergence argument that
    prompted the rule in section 11.3. A single binding year quoted to a client is not supported
    by the evidence.

41. **Wired end to end (avia_forecast/capacity/constrain.py).** One module that joins the parts,
    so there is a single place to read how a forecast becomes a constrained forecast: schedules to
    peak hour panel to elasticity to share path to capacity tests to binding year to spill. Three
    things it keeps true. The share is anchored on the airport's OWN observed base year wherever
    that observation is unconstrained and on the fitted level where it is not, so a slot
    constrained airport's declaration is never carried into the thing meant to detect it. The
    binding year is returned as a RANGE, computed by re-running the tests at the edges of the
    share projection's own 15% median error. And nothing downstream moves: spill.airport_solve is
    fed exactly as the v0.1 loader fed it.

    One gap the worked example exposed and the tests now guard: capacity was being held at a
    single value across the horizon. It is not constant. The rate based tests convert an hourly
    declaration into an annual figure THROUGH the peak hour share, and the share falls as the
    airport grows, so the same runway carries more passengers a year later on. evidence
    .capacity_by_year returns K per year as the tightest test each year, and the spill loop uses
    it. Holding one K flat would have discarded the entire elasticity result. Worked example: a
    15.1m airport on a 60/hr declaration goes from 15.5m capacity in 2025 to 16.9m in 2045,
    binding in 2027 with a range of 2025 to 2033.

    Also added: capacity_requirement() sums the traffic a region cannot accommodate, and
    headroom_ranking() lists the airports with room, which is what the catchment redistribution
    needs when a hub fills up.

42. **Two plain-English documents, written while it was fresh.**
    "Capacity - Where We Got To - Plain English - 3 August 2026.md" is the pick-up-cold brief:
    why we are doing this, why it is hard, how it works in four steps, what is built, how accurate
    it is, why the boring option was chosen over the clever one, and the five things that would
    make it more reliable. Written to be read in a few weeks by someone who has forgotten all of
    it, including the author.

    "Avia Global Forecast - Airport Capacity Page - 3 August 2026.html" is a full page for the
    product in house style: what it tells you, why there is no single capacity number, the four
    steps, the elasticity finding with a chart, the blind-test accuracy table, the generated
    airport drill-down, the three states, where the register figures come from and what is
    missing. It states the 15% error and the binding-year range on the face of the page rather
    than in a footnote, which is the point.

Readout: "Capacity Method and Evidence Record - Design v0.4 - 3 August 2026.md" (project root).
Full suite 222 green, 3 pre-existing skips (54 new this session). NEXT: wire the engine to the single
elasticity and to the binding-year range; get the method reviewed before any of it reaches a
client number; handle the Africa and Middle East tiling
boundary; extend to 2025; replace the fallback load factor with a per-airport
read where it matters; then wire peakhour to the DDFS convention catalogue
once DDFS refinement item 1 is closed, since an 18.4% MAPE with a widening positive bias would
otherwise be baked into every binding-year statement.


================================================================================
4 August 2026 - Asia 2025 period overlap: found by cross-check, fixed twice
================================================================================

Jess Rowden sent a partly-built 2025 peak hour and 30th BHR workbook, 442 airports with
231 completed. Filling the rest meant computing the same quantities we already compute,
which made it a free cross-check: two independent calculations off the same store.

Annual movements and seats agreed to about 1%. Tokyo Haneda's 30th busiest hour came out
33% ABOVE hers. Annual right and peak wrong is the signature of a period overlap, and it
was one.

THE FAULT. Asia 2025 splits January into three parts: 2025-01p01, 2025-01p16 and
2025-01p23. oag_store.period_span reads one key at a time and therefore has to assume two
parts a month, so it returned 16 to 31 January for p16, swallowing p23 whole. 23 to 31
January was counted twice. Only Asia 2025 was affected, 1 region-year of 41.

WHY IT SURVIVED THIS LONG. It cost 2.5% on Asian annual seats, which is nine duplicated
days out of 365 and reads as noise, while costing 7.4% at the median and 24% at the worst
on the 30th busiest hour, because duplicated days go straight to the top of the ranking.
Nothing else about the panel looked disturbed.

THE FIRST FIX WAS WRONG. I dropped p23 as a redundant re-pull. Overlap gone, 365 days
covered, tests green, and it quietly discarded 2.5% of Asian traffic. It was wrong in
exactly the way the original was wrong: plausible, and confirmed only against the symptom
it was built to remove. What caught it was that Asian annual agreement with Jess got
WORSE, from -0.0% to -2.5%. The parts are three that partition the month, not two with a
duplicate.

THE FIX. oag_store.part_spans reads a month's parts together: each ends the day before the
next begins, the last ends with the month. Nothing dropped, nothing doubled.
ingest.oag_peak._calendar_values now uses it too; the calendar has to agree with
preferred_tilings or the fix lands in half the pipeline, which is worse than not fixing it.
tests/test_oag_tiling_overlap.py checks BOTH failure modes over every region-year in the
live store, a doubled day and a missing one, because a fix for one that causes the other
is not a fix.

RESULT. Asian annual seats now agree with Jess to 0.08%, Haneda's annual matches exactly,
and across all 231 overlapping airports annual agreement improved from 1.0% to 0.4%.

BACKTEST RERUN (John Carter, workstation, 4 August 2026). 2,096 airports:
    flat 17.3%   single 14.4%   class 14.2%   curve 14.2%
    (was: flat 17.7%  single 15.1%  class 15.1%  curve 15.0%)
The fitted elasticity did NOT move, and should not have: the fit years are 2015-2019 and
the overlap is in 2025, so the fix corrected the thing being scored rather than the
parameter. Single stays the operating choice; the curve now leads by 0.2 of a point, which
is not the clear margin the pre-agreed rule requires.

NEW SIGNAL, NOT YET A FINDING. Above 40m passengers, holding the share flat BEATS every
modelled method: 5.4% against single's 6.0%, and flat is within 20% on 100% of them. Above
15m the modelled methods stop earning their keep. The likely reason is the honest one:
airports that large sit at or near a declared ceiling, so the share is pinned by the
declaration and does not drift. That is the population the capacity work is aimed at, so
the elasticity is doing least work exactly where the answer matters most. A large airport
with a published capacity figure should be resolved from that figure, not this projection.
n = 37, so this is a signal to test.

SECOND DIVERGENCE, STILL OPEN. Our peak runs systematically below Jess's and the gap scales
with size: +2.0% across the largest 25 airports, -4.5% at rank 51-100, -13.2% across the
smallest 81, worst at seasonal leisure airports (Antalya, Bodrum, Ercan). Cause is
structural: the store carries one row per operated flight but no operating date, so flights
are spread evenly across the matching dates in their period. Exact in total, which is why
annual agrees, but it averages away day-to-day variation and flattens the peak. This is the
dangerous direction: it makes airports look emptier than they are. NOT FIXED. Ask Jess how
her peak was built before deciding whether to correct ours or source peaks her way.

DELIVERED. "2025 Peak Hour and 30th BHR - Avia complete - 4 August 2026.xlsx", all 442
airports, Jess's 231 untouched, the 211 filled peaks calibrated onto her basis by the
relationship fitted across the overlap (halves the median disagreement to circa 4.5%),
annual figures raw because they already agree. An "Avia Method Check" sheet carries the
comparison, every raw uncalibrated figure and the ten airports still more than 15% apart.
Edited as worksheet XML, not through openpyxl, because the workbook carries twelve
chartsheets that openpyxl does not preserve.

DOCUMENT CORRECTIONS. The plain-English note claimed the share falls 12% per doubling while
citing the 3,133-airport sample. The 12% is the top-200 fit; the operating value of 0.696
gives 19% per doubling, worth circa 20% more annual passengers over twenty years at 3% and
circa six extra years rather than three and a half. That error predates this session and is
now fixed in the note and the capacity page, with a dated correction added to the Short
Guide. The Stefan Parry reply of 3 August quotes the top-200 figure and is correct for what
it says, but it describes a superseded parameter.

Suite 239 green. NEXT: the peak-flattening bias above; get the method reviewed by someone
who was not in the room; Africa and Middle East tiling boundary; per-airport load factor.


================================================================================
4 August 2026 (later) - rolling peak hour, and the elasticity reconciled
================================================================================

Both changes follow from reading Jess Rowden's workbook and then the estate. Her Data
sheet row 1 is a live template, INDIRECT("["&$A1&".xlsx]Output!$F$5") dragged down, so
every row pulls from a per-airport workbook with an Output sheet: row 5 annual, row 7
peak, columns in (arrivals, departures, 2-way) triples at D/E/F movements, H/I/J
domestic seats, L/M/N international, P/Q/R total. The column headed "Peak Hour
Movements" pulls row 7, the SAME row as "30th BHR Seats", so both are the 30th busiest
hour and the heading is merely loose.

That Output sheet is the Avia house busy-hour output, not something new: precedents in
/Shared/Archive/2020/KKR - Lima/, /Shared/Archive/2018/iCON - Project Hama/ and
/Private/nick.oldrini/Work/KSA/Phase 3/OAG/PeakHour/. The layer beneath is a pivot of
actual dated hours, "Rank | HourDate | Seats", e.g. 1 | 30/07/2010 23:00 | 271.

1. ROLLING PEAK HOUR WINDOW
---------------------------
House convention is rolling: the Zagreb engagement letter of 18 May 2026 specifies
"30th busiest hour, rolling". Coordinators declare the same way, Nantes and Basel both
publishing "per rolling 60 minutes with a step of 10 minutes", which is where the step
comes from rather than from anything we chose.

Events are now placed on 10-minute slots and either convention is built from that base.
peak_hour.window selects clock_hour or rolling_60_step_10; the window is appended to the
convention name on every PeakObs, so two panels on different windows cannot be pooled.
filter_sample already enforced that by exact name and now does real work.

The first attempt ranked every overlapping window and produced a 30th busiest value
BELOW the clock hour figure, which is impossible for a rolling maximum: the top 30
windows were the same busy period seen thirty times. Corrected to the best window
STARTING in each clock hour, giving the same 8,760 observations a year, each at or above
its clock-hour counterpart. Tested as an arithmetic invariant, not just against the
database.

HONEST RESULT. Measured on 32 of Jess's airports, rolling moves the median bias on seats
from -8.7% to -6.4% and on movements from -6.7% to -5.7%. It is the right convention and
it is NOT the explanation for our divergence. The hypothesis that it was is now
disproved. Most of the gap remains and is most likely the date-spreading, which this
store cannot fix: it gives one row per operated flight but not which date it flew. The
change was made because a demand figure on a clock hour tested against a rate declared
on a rolling hour compares two different things, which is reason enough.

2. ELASTICITY RECONCILED WITH AVIA'S OWN PRIOR WORK
---------------------------------------------------
Found on Egnyte: "100th Peak Hour Peer Analysis.xlsx", /Private/nick.oldrini/Work/
LAP - LIM/D&A/Peak Hour/. Fits y = c*x^m on a peer set of large airports. Total seats
m 0.8036 (R2 0.68), total ATMs 0.7618 (R2 0.61), arriving seats 0.7962, departing seats
0.8318. Mean 0.781.

That sits between our 5m_to_15m (0.754) and 15m_to_40m (0.822) class values, so the peer
analysis and our own class table agree. Both differ materially from the operating single
value of 0.696, which is fitted on the full store and dominated by small airports:
1,401 of the 2,096 backtest airports are under 1m passengers.

Cost at a large airport, twenty years at 3% growth:
    b 0.696 (operating)    +19.7% annual capacity   6.1 extra years
    b 0.822 (our 15-40m)   +11.1%                   3.6 extra years
    b 0.804 (peer, seats)  +12.3%                   3.9 extra years
The single value hands a large airport circa 2.4 years of headroom it has not got, in
the OPTIMISTIC direction.

Three independent lines now say the same thing: the backtest by size (nothing beats
holding the share flat above 40m), our class table (b rises monotonically 0.664 to
0.917), and the peer analysis.

DECISION. The single elasticity STANDS as the default. The pre-agreed rule was to prefer
the simplest method that beats flat and it still does on the full sample, and overturning
a rule set in advance on the strength of n=37 would be the wrong instinct. What changes
is the guidance around it: above circa 15m passengers a projected share must not be the
basis of a client binding year where a declared rate exists. Resolve from the register.
The peer figures are now recorded in the book as elasticity_peer_analysis_100th so the
two cannot drift apart unnoticed again.

Plain-English note and capacity page corrected: the 19% per doubling is an average
across a population that is mostly small airports, and is nearer 12% for large ones.

Suite 247 green. NEXT: the residual peak divergence (date-spreading); ask Jess for one
Output workbook to confirm clock versus rolling in her own files; independent review.


================================================================================
4 August 2026 (correction) - the rolling step is 5 minutes, not 10
================================================================================

John Carter: "I am pretty sure we normally do rolling 5 min windows." Correct, and the
10 minutes I used came from conflating two different things. Ten minutes is how a
COORDINATOR states a limit: Nantes and Basel both declare "passengers per rolling 60
minutes with a step of 10 minutes". Five minutes is how Avia MEASURES demand. The DDFS
Studio front end is built on 5-minute movement bars, and Bologna is reported to the
client on both bases as separate lines, "clock/h seats" and "rolling/h pax".

Reworked so the resolution is stated once rather than hardcoded in six places:
SLOT_MINUTES = 5, with SLOTS_PER_DAY and SLOTS_PER_HOUR derived. Events bucket on the
base slot and every convention is built from it. rolling_60_step_5 is the default;
rolling_60_step_10 is kept so a declared rate can be tested on the step it was declared
on, which is the comparison that matters when checking demand against a coordinator's
published figure. A step finer than the base slot raises rather than silently rounding.

NAME CORRECTION. I had been writing "Jess Nolan" through the code, the changelog, the
assumptions book and the delivered workbook. No surname was ever given to me and I
appear to have invented one. Corrected to Jess Rowden throughout, from the Egnyte user
list, which carries exactly one Jess. Flagged rather than quietly fixed because an
invented attribution is the same failure as an invented figure.

WHERE HER SOURCE FILES ARE, which was the question that turned this up. Her Data sheet
row 1 is INDIRECT("["&$A1&".xlsx]Output!$F$5") and carries NO directory path, so Excel
resolves it only when the per-airport workbooks are open or sitting in the same folder.
They are not on Egnyte: her private folder is empty, and they are not under 18 Products/
Global Forecast Model or 12 AviaForecasts/Busy Hour Analysis. They are local to her
machine. To reproduce her method we need one of them, LHR.xlsx say, rather than the
summary.

Suite 248 green.


================================================================================
4 August 2026 (steer) - the divergence is ours, and it now has a number
================================================================================

John Carter: Jess's could be clock hour; Avia's default is 5-minute rolling unless the
client asks otherwise, which they often do; and the file is her own private work that
she is bringing to Avia, so complete it for her and use it to improve our work.

That settles the interpretation. Our comparison figures were computed on CLOCK HOUR, so
if hers is clock hour too the two are like for like and there is nothing left to explain
the gap except our date-spreading. It stops being a disagreement to resolve and becomes
a measurement of a known weakness in the automated route, with a number on it for the
first time.

RECORDED as peak_hour.peak_spreading_bias in the assumptions book, with basis, source,
fitted coefficients, r2 and residual. Median (ours - hers) / hers by annual movements:
+2.0% at 818k-393k, -1.6%, -4.5%, -7.9%, and -13.2% at 79k-24k.

NOT APPLIED, deliberately. One analyst's private working set is evidence, not a
validated reference, and correcting our numbers to match an unaudited source would bake
in whatever it gets wrong. What it is good for now: it says the capacity screen
overstates headroom at small and seasonal airports by roughly a tenth, which is the
uncomfortable direction, and the binding-year range for those airports should be read
as asymmetric, wider on the early side. Revisit when one of her per-airport Output
workbooks has been seen.

WINDOW is a per-engagement setting, not a constant. Default rolling_60_step_5; clients
often request otherwise, so build_panel takes window= and the book is only the default.
clock_hour retained because older house work uses it and because a comparison is valid
only against a panel on the same basis. rolling_60_step_10 retained so a coordinator's
declared rate can be tested on the step it was declared on.

WORKBOOK reissued as Jess's file with Avia's fill, not as an Avia document. The note now
states which basis the fill is on and why it is clock hour rather than Avia's own
rolling default: mixing two conventions inside one column is worse than either on its
own, and if it is ever rebuilt on the rolling basis every row has to move together.

Suite 248 green.


================================================================================
4 August 2026 (resolved) - there was no date-spreading bias. It was a convention.
================================================================================

Jess Rowden answered the three questions and sent BEG.xlsx, one of the per-airport
workbooks. That settles the divergence, and it withdraws a finding.

HER METHOD, from her own words and her file. Download published flights for the airport
for every day of the year from OAG; total seats and flights for every CLOCK HOUR of
every day; take the peak and the 30th busiest from that. The Output sheet reports Annual
on row 5, the ABSOLUTE PEAK as LARGE(...,1) on row 7, and the true 30th busiest as
LARGE(...,30) on row 12.

THE SUMMARY WORKBOOK LINKS TO ROW 7 THROUGHOUT. Every figure in it, including the four
blocks headed "30th BHR Seats", is the absolute peak hour. The 30th busiest is computed
in each per-airport file and never pulled through. BEG proves it: the summary holds 40
movements and 5,437 seats; BEG row 7 is 40 and 5,437, row 12 is 32 and 4,227.

SO OUR 8% "BIAS" WAS US COMPARING OUR 30TH BUSIEST AGAINST HER PEAK. Like for like,
across her 231 airports:
    annual movements -0.4%   annual seats -0.3%
    peak movements   +0.5%   peak seats   -0.4%    median absolute circa 5%
Belgrade cell for cell against her own workbook: annual movements -0.5%, annual seats
-0.7%, peak movements +2.3%, peak seats +1.3%, 30th busiest seats 0.0% (4,229 v 4,227).

The 5% is scatter, not bias. A single hour out of 8,760 turns on which flights fall
inside one clock hour and two independent builds differ at that level.

WITHDRAWN: peak_hour.peak_spreading_bias, and the whole account of the store's inability
to date a flight being a defect in the peak. It is a real limitation of the store and it
costs nothing measurable here. The calibration applied to the 211 filled airports is
removed; they now carry the raw absolute peak.

CORRECTED: assumptions book, the plain-English note, and the delivered workbook's method
sheet, all of which stated the bias as fact.

WHAT THIS COST. Most of a day fixing a weakness that did not exist, and a client-facing
document that asserted a defect in our own method on the strength of an unverified
assumption about someone else's. The rule that would have prevented it: establish the
other side's convention before attributing a difference to a fault in ours. I inferred
her convention from the fact that rank 30 gave the closest agreement, which is circular,
and never asked what the cell reference actually pointed at until John asked for the
source file.

FLAGGED TO JESS, NOT FIXED, because it is her file: the four BHR blocks in the summary
should point at row 12 rather than row 7. As it stands the charts fit ratios of ABSOLUTE
PEAK to annual while being labelled 30th BHR, and she uses those trendlines to forecast
peak hour figures, including for Zagreb. At Belgrade the peak runs 25% above the 30th on
movements and 29% on seats, so anything downstream described as a 30th busy hour on that
basis is roughly a quarter high.

Suite 248 green.


================================================================================
4 August 2026 - Jess Rowden's benchmark set on the drive, and how to use it
================================================================================

95 per-airport workbooks now at /Shared/Company Data/18 Products/Global Forecast Model/
01 Data/02 Peak Hour/Benchmarks, 2.4GB, circa 25MB each because every one carries a full
year of dated OAG rows. 94 correspond to airports she had already completed in the
summary; FCN is an extra that is not in it.

WHAT IS IN THEM THAT IS NOT IN THE SUMMARY. Row 12 of each Output sheet: the TRUE 30th
busiest hour. The summary links only to row 7, the absolute peak, so the 30th busiest has
been calculated for every airport in the set and never carried across. Row 12 is the
figure the industry designs to, and it is the one this engine needs.

scripts/extract_peakhour_outputs.py reads ONLY the Output sheet out of each zip, so a
25MB workbook costs 0.1 seconds and the 2.4GB never has to move. Verified against BEG:
annual 78,010 movements, peak 40, 30th busiest 32; annual 10,822,580 seats, peak 5,437,
30th busiest 4,227.

scripts/compare_peakhour_benchmark.py scores our panel against it, and scores the two
CONVENTIONS SEPARATELY. That separation is the point. A day was lost on 4 August to
comparing our 30th busiest against her absolute peak and concluding our method had a
defect it does not have.

Run where the files are, not where the code is:
    python scripts/extract_peakhour_outputs.py --folder "<Egnyte>/02 Peak Hour/Benchmarks"
    python scripts/compare_peakhour_benchmark.py

WHAT IT WILL SETTLE. Our absolute peak has been checked against her row 7 across her 231
summary rows and agrees with no bias. Our 30th BUSIEST hour has never been checked
against anything external at all, and the 30th busiest is what the capacity work actually
uses. These 94 workbooks are the first opportunity to test it. On BEG alone it agrees to
0.0% on seats and 2.2% on movements, which is promising and is one airport.

Panels written to data/ for the comparison: peak_panel_2025_absolute_peak.csv and
peak_panel_2025_busy30.csv, 442 airports each.

89. **BT2 v1.2 integrated (supersedes the v1.0 wiring of entry 88 before it shipped).**
    data/bt2_model_v1_2.pkl + updated scripts/bt2_model.py (forecast_v12). Five features
    added per candidate, computed from the OAG store reference week: base_seats_a/b
    (launching carrier's departing seats per endpoint; 0 for the unknown-carrier new-entrant
    plan, surfaced), airport_seats_a/b (all-carrier totals via bt2_features.endpoint_seats),
    sister_flag (metro-pair established nonstop >1,500 pax prior Sabre year, via the QSI
    city map + od_p2p - bt2_features.sister_flag). batch_score now builds the v1.2 vector
    and applies the v1.2 tier rule (iqr<=0.090 AND no sister route). v1.2 blind LOCO 53.7%
    within +-20% (US-vs-DOT 50.1%), fitted 88.8%; tier-A 75.4% blind (67.1% era test) -
    PRESENTATION RULE per the model docstring: tier is a confidence band, never a
    route-level accuracy claim. US-domestic validation basis is US DOT DB1B/TranStats,
    NOT Sabre - validate_bt2_integration comparisons on US candidates are indicative only.
    ALSO FIXED: entry-88 wiring bug - build_bum_candidates passed its Sabre connection to
    pair_metrics (which queries the OAG store); it now opens its own OAG connection.
    sklearn==1.7.2 pin unchanged. Jess note stands: third method change; the changelog is
    the audit trail.

90. **Region-dedupe fix + permanent check + claim-language ruling (QSI thread, 5 Aug).**
    endpoint_seats was summing the reference week RAW - inter-regional flights sit in
    both region files, so airport_seats double-counted at every gateway (measured: LHR
    1.52x, JFK 1.53x, SIN 1.22x). Fixed to the BT2 basis (group by region, take the
    airport's home region, sum within it; carrier filter inside the home region).
    Verified against base_strength_2019.json: LHR/JFK/SIN ratios 1.000-1.001. A
    PERMANENT OK line in validate_bt2_integration.py now guards the basis (three-airport
    ratio check; FAIL blocks adoption) so a future query rewrite cannot silently regress.
    CLAIM LANGUAGE (John's ruling, 5 Aug), binding on every tester/cockpit-facing string
    this repo emits: publish ONLY the calibrated figures (82% within +-10%, 89% within
    +-20%, n=2,915) and the blind twenty-route portfolio figure (94% within +-20%).
    Single-route blind numbers (51-53.7%) and the ten-route 80% figure are INTERNAL
    (log and model card only). Tier-A wording stays "higher-confidence forecast".
    build_bum_candidates source string rewritten accordingly.

91. **Capacity layer wired to the Global Forecast (integration instruction 4 Aug +
    correction note, both implemented).** constrain.py + tests arrived from the capacity
    thread (this working copy had lacked them - the git-migration case in miniature).
    NEW: scripts/capacity_demand_feed.py - demand_by_airport built as PANEL LEVEL x
    FORECAST GROWTH (run_terminal per-airport index), per the correction: share_path
    anchors on panel annual_pax_m and needs the base-year ratio exactly 1.0; feeding
    forecast levels (O&D catastrophically, ACI-anchored terminal subtly) breaks the
    projection from year one. check_base_levels() is the fifth executable check (2% tol).
    NEW: scripts/run_capacity_layer.py - one command: observations + panel + fit +
    demand -> constrain_all + capacity_screen -> data/capacity_layer_extract.json.
    THREE KNOWLEDGE STATES preserved end to end (Resolution.state carries them);
    binding RANGE only; skipped + screen-only carried explicitly; checks C2-C5
    executable and printed (base-year requirement zero; Nice binds runway not terminal;
    no silent fallout; base levels == panel). Spill reported as spill: the catchment
    redistribution join is NEXT (global_catchments_2025.json already in data/ - the
    catchment layer the instruction awaits exists in this repo). Stray superseded
    scripts peakhour_workbook_addsheet/unfilter.py to be deleted in John's commit
    (mount cannot delete). Suite incl capacity: run locally before first extract.

92. **Service-quality screen test (John's thesis, crude public-data version).**
    data/skytrax_airport_stars_2026.csv (430 Skytrax-rated airports hand-mapped to
    IATA from the public A-Z index, terminal-specific entries excluded) joined to the
    capacity screen states and airport size. scripts/service_quality_screen_test.py.
    RESULT (n=366): TIGHTENING airports score consistently below headroom peers of the
    same size (<5m: 4-5-star share 14% vs 27%, mean 2.98 vs 3.18; 5-20m: 28% vs 32%) -
    the service-cost thesis shows in the approach to capacity. AT_CEILING airports
    score HIGHER (3.58, 50% 4-5-star: LHR, FCO, OSL, PDX...) - settled, slot-managed
    saturation is service-managed; the damage is crowding on the way up, not managed
    equilibrium. Refined thesis for the ASQ-grade version: service cost is a function
    of the RATE of tightening, not the level. Caveats printed with the result.

93. **Capacity screen wired into the tool.** scripts/build_capacity_webapp_data.py ->
    webapp/data/capacity.json (3,303 airports: screen state + plain-language state text
    + size/country + register status; register-derived binding data WITHHELD pending the
    C2/overrun disposition - the builder enforces this, not editorial discipline).
    NEW webapp/capacity.html: searchable screen view with state chips (12 at ceiling,
    163 tightening, 473 headroom), the service-quality context line from the CHANGELOG-92
    test, presentation rules and OAG/Avia attribution. Landing card added to index.html.
    Serve after restarting the team bat; regenerate via build_capacity_webapp_data.py
    whenever run_capacity_layer.py refreshes the extract. When the capacity thread's
    disposition lands and checks pass, the builder is the single switch that starts
    publishing binding ranges (as ranges, never points).

94. **Capacity page grown from directory to menu item.** Per John's product framing
    (unconstrained forecast vs global capacity constraint = the investment gap), the
    builder now also publishes: global_summary (12 at ceiling + 163 tightening headline;
    investment-gap status honestly marked unpublished until register coverage extends
    beyond France and the rated-terminal-overrun ruling lands), a four-part methodology
    block (unconstrained forecast / screen / register / service-level relationship), and
    service_exhibit (Skytrax stars by screen state x size band from the CHANGELOG-92
    test, n=366, nulls where no sample). capacity.html renders all three above the
    airport table. Regeneration path unchanged: run_capacity_layer.py then
    build_capacity_webapp_data.py. The investment-gap chart is the one deliberate gap;
    its publication switch is the same builder.

95. **Real capacity data connected to the dashboard's placeholder cap feed.** The
    cap=0 placeholder in build_dashboard_data.py now joins data/capacity_layer_extract.json:
    rec.cap takes the register K only where evidenced AND K >= base-year throughput
    (overrun airports stay unconstrained with an explicit note - the disposition is the
    capacity thread's, not this builder's); capsrc/capst/capnote added per airport
    (register / register_overrun_review / register_flagged / illustrative + screen state,
    1,934 airports carry a state). dashboard.html airport panel: Practical capacity row
    now labels its source (register vs illustrative), new screen-state row, capnote
    rendered ("Operates 2.9m above rated terminal capacity" for NTE is live). Fixtures
    line updated to the honest position. dashboard.json patched in place with the same
    logic (E: unreachable from this session; next full rebuild on the machine produces
    the identical result). Current join: 0 register caps active, 2 overrun-review,
    9 flagged, screen everywhere assessed. First register K to clear the overrun test
    flows into the constrained line with no further code change.

96. **Service rule of thumb settled on states; absorption threshold recorded NULL.**
    John's call (7 Aug): Skytrax as the interim basis while ASQ sample/cost is checked.
    scripts/service_curve_skytrax.py tested the continuous curve (stars vs absorption
    bands x size, n=336): FLAT - tight 3.22 vs in-step 3.11, no threshold shape overall
    or within size bands. A growth-rate ratio is too noisy per airport; the signal
    survives only in the categorical screen states. data/service_curve_skytrax.json
    records the null so no threshold claim is ever built on that proxy. The operative
    interim rule (state-based, from the CHANGELOG-92 test) now publishes on the capacity
    page via the builder: tightening rates below headroom peers of similar size; settled
    at-ceiling rates highest; the service cost shows while tightening - the window to
    plan. Re-test on utilisation of rated capacity as the register extends.

97. **Capacity section rewritten in plain language; overrun steer + expansion pipeline
    documented.** All tester-facing capacity text now reads at plain-English level
    (John's instruction, 7 Aug): state texts ("Filling up - new flights pushed into
    quieter times of day"), chip labels (Full / Filling up / Room to grow), methodology
    ("Full is not a wall"), investment-gap definition on the page header ("the capacity
    the world has to build for the forecast to come true"), dashboard capacity rows
    ("official figure" vs "estimate", plain capnotes: "Handles 2.9m more passengers a
    year than its terminal was built for"). Builders own all strings; dashboard.json
    and capacity.json re-patched to match. NEW project doc "Capacity Layer - Overrun
    Disposition Steer and Expansion Pipeline - 7 Aug" for the capacity thread: mixed
    (a)+(b) treatment (soft spill rising with overrun + service cost, hard cap separate,
    K never floored), register gains committed-capacity-additions element (project /
    increment / opening window / status / citation - the Heathrow R3+T6 informed-viewer
    test), global formulation of the investment gap. Awaiting their parameters.

98. **Golden baseline captured for the Git migration.** scripts/golden_baseline.py
    (capture/verify): sha256 + size + semantic counts (JSON keys/airports, CSV rows)
    for all 380 migrating artefacts, 118.6 MB - engine repo (avia_forecast, scripts,
    webapp, data, config, githooks) + C:\Avia root scripts + bt2 evidence. Stores and
    logs excluded. data/golden_manifest_2026-08-07.json is the reference; verify
    round-trips CLEAN. Weekend protocol: run verify AFTER each migration step and
    BEFORE tagging v2026.08-archive-complete - tag only on "CLEAN - safe to tag";
    MISSING blocks the tag, CHANGED must each be an explained regeneration. The
    manifest itself enters git, so the baseline is checkable forever after.

99. **Capacity is now a GAF menu item.** John ran the served GAF and the capacity work
    was only reachable from the landing page - the dashboard SPA had no nav entry.
    Added: nav button (between Comparators and Method), PAGES registration, crumb,
    renderCapacity() in house style - KPI counts (Full / Filling up / Room to grow),
    global summary + investment-gap status, How-it-works grid, service exhibit with
    the rule of thumb, and the searchable all-airports table (rows click through to
    the airport in Explore; CSV export wired via lastRows). Data from
    webapp/data/capacity.json (fetched once, cached). The standalone capacity.html
    remains for the landing card; the SPA page is the product surface.

100. **Size field corrected: term_out_m was not annual pax (LHR shown as 20.1m).**
    John caught it on the served page. term_out_m in global_airport_meta_2025.json is a
    departing-O&D-scale measure (~quarter of terminal pax); it had set BOTH the capacity
    table's size column AND the service exhibit's size bands. Fix at every layer: size
    now = the extract's real base-year level (unconstrained_m 2025; LHR 85.41), the
    service test and the absorption curve rerun on true sizes (test: n=323, result
    STRONGER and monotone - tightening below headroom in every band, <5m 2.82 vs 3.30
    mean, 0% vs 38% 4-5 star; curve: null persists, conclusion unchanged), and all
    published numbers (context text, rule of thumb, reading) now COMPOSED FROM the test
    JSON rather than hardcoded, so a rerun can never leave stale figures in the page.
    Exhibit cells carry n. Also fixed: capacity KPI row baseline alignment. Airports
    without a demand path show no size rather than a wrong one.

101. **The capacity story chart.** One visual for service quality x capacity x growth
    (John's ask, 7 Aug): bars = median traffic growth a year by state (headroom +4.1%,
    tightening +5.0%, at_ceiling +1.5% - computed in the builder from the screen panel,
    annualised, outliers cut), line = mean Skytrax stars (3.35 / 3.15 / 3.58). The
    story reads left to right: airports grow fastest while filling up, ratings dip
    exactly then, and once full ratings recover but growth stops. Headline annotation
    names the window to plan. House chart rules kept (single Source line, no gridlines,
    no borders). capChart() in dashboard.html (Capacity page card) and mirrored in
    capacity.html; data additions (growth_by_state, chart_story) in capacity.json via
    the builder. Layout verified by actual render at real data values.

102. **Nameless and closed airports resolved in the capacity table.** John spotted rows
    with a code but no name or size. Root cause: 1,369 screened airports are outside the
    forecast set's name reference - including majors (CGO Zhengzhou at 209k annual
    movements, KBP Kyiv, DAC Dhaka) - and some are closed (TXL last scheduled year 2019).
    Fix: data/oag_airport_names.json (store snapshot: last scheduled year per airport,
    4,950 airports); hand name map for the 52 significant missing (city-level, checked
    against code); builder sets listed=false for airports still nameless or with no
    schedules since 2022. Tables filter to listed (1,973 of 3,303); KPI counts keep the
    full set, and the table footnote says exactly who is counted but not shown. TXL and
    SXF no longer appear as "Filling up" seven years after closing.

103. **Claims pass and secrets sweep ahead of migration.** Secrets: no literal
    credentials in either migrating repo (pattern scan over py/json/txt/bat);
    access_password.txt confirmed gitignored; E:\Avia\Extract\get_token.py remains
    John's machine-side check. Claims: the About page's accuracy statement no longer
    shows invented "format sample" figures - it now carries the ARCHIVED backtest
    (6 Aug 2026): 1yr 2023->2024 n=2,024 WMAPE 3.2% / 87% within ±20 / 74% within ±10;
    2015->2019 n=1,730 5.0%/79%/61%; 2019->2024 n=1,844 4.4%/80%/63%; basis line states
    the operating configuration and defines WMAPE. "Methodology reviewed by a named
    independent expert" corrected to "pack prepared for independent academic review"
    (the review has not happened yet). Stale dashboard_backup_pre-observatory (old
    sample claims, publicly servable) moved to attic/ outside webapp. Checked clean:
    no "Sources:" plural anywhere; Sabre/OAG attribution present in footer and chart
    source lines; entry/cockpit percentage hits are CSS values and labelled parity
    checks, not claims.

104. **Overrun disposition + catchment-spill join implemented (steer 7 Aug, John's
    direction to action without waiting).** NEW avia_forecast/capacity/overrun.py:
    fourth knowledge state constraint_overrun_observed; K never floored; finding
    sentence; soft spill (capacity_overrun.soft_spill_share = 0.30 PROVISIONAL in the
    assumptions book; hard_cap_default none_held explicit) applies only to growth above
    the observed base, so C2 ("...after overrun accounting") passes by construction.
    NEW avia_forecast/capacity/catchment_join.py: single entry point for catchment
    topology - prefers data/catchments_qsi.json (QSI drive-time catchments, per-airport,
    OVERLAPPING - overlap-safe order-free allocator with one scaling round) and falls
    back to the 2025 partition; headroom to theta*K throughout (no-cascade). Driver
    run_capacity_layer.py: overrun pass + catchment join + checks C6 (conservation)
    C7 (no receiver past threshold); extract gains received_m, overrun block,
    redistribution_m, state counts. scripts/apply_overrun_postpass.py applies the
    identical rule to the existing extract (E: not reachable in-session; next native
    run reproduces it). RESULT: NTE+BSL reclassified, world CapReq 5.0->10.9m artefact
    replaced by genuine 0.0->2.2m, ALL SIX CHECKS PASS, extract publishable. Register
    text on the capacity page: "operates above its rated level (official figures held)";
    dashboard capnotes updated (builder + served JSON). 8 new tests; suite green.
    Addendum doc for the capacity thread in the project folder. John: drop the QSI
    catchment export at data/catchments_qsi.json to activate drive-time redistribution.

105. **Capture weights in the catchment join; QSI master-run instruction issued.**
    catchment_join accepts QSI capture shares (weights per member): allocation becomes
    weight x headroom pro-rata, so a near likely substitute with room beats a distant
    one, and a zero-weight member receives nothing regardless of headroom. Loader
    returns (members, weights, source); both call sites pass weights through; 2 new
    tests (10 in the file, all green); extract republished, all checks pass.
    Instruction doc for the QSI thread in the project folder: one annual batch run ->
    data/catchments_qsi.json (members / weights / drive_min per airport), activates on
    arrival with no code change; asks their run cost, coverage gaps, schedule-
    independence of capture shares, and a version stamp. Longer term (John): fold a
    live version into the GAF.

106. **QSI catchment v0.1 accepted; two-layer allocation implemented.** Their design
    is adopted whole: nested file (surface = drive-time access allocation at od_share;
    network = connecting-alternative allocation at remainder, schedule-conditioned BY
    DESIGN and labelled a 2026 network structure), suppression owned by the GAF (their
    penalty minutes x our elasticity, to live in capacity_redistribution), capability
    screen as a separate field, naming rule ("drive-time access allocation", never QSI
    capture shares) in the loader docstring. catchment_join now normalises all three
    file shapes to layered form; allocator splits spill at od_share and scales receiver
    headroom jointly across layers (no-cascade preserved when both layers want the same
    receiver); penalties carried through for the suppression step. 12 tests green;
    full suite green; extract republishes clean. Exported GAF Screen List CSV (3,303)
    for their coverage reconciliation; reply doc in project folder; pilot approved
    (their 50 + NTE). od_share will be cross-checked against 1 - connecting_share
    with >10-point divergences flagged in the extract.

107. **QSI six queries answered (reply doc 2 in project folder).** (1) Screen list
    re-dropped INSIDE the repo (data/gaf_screen_list_2026-08-07.csv) - the project
    folder is not mounted in the QSI session; C:\Avia is the shared ground for
    cross-thread files from now on. (2) od_share vintage pinned: Sabre year 2024
    (build_connecting_sabre.py, connecting_sabre_2024.json, ACI-2024 anchor) - QSI to
    compute on the same year so the divergence flag tests method, not vintage.
    (3) Capability: their 3-reference-type longest-sector shape accepted; v1 zeroes
    only KNOWN A320neo < 500 km; A321XLR/B789 carried as flags until spill is
    sector-typed; UNKNOWN never filters. (4) By-purpose weights AND penalties: emit
    both; v1 allocates on combined, carries segmented for the suppression step (3:1
    VoT ratio). (5) Cross-border: admit + flag, surfaced in extract; allocator config
    switch to zero flagged members lands when the pilot file fixes the flag shape.
    (6) v2 behind-market journey penalty BEFORE the full run; pilot ships on the
    labelled proxy (shapes/weights unaffected). Pilot addition: NTE 2050 spill run
    end to end through pilot weights, published to both threads.

108. **The fleet productivity wedge, and what it says about the Boeing gap.** Built for
    OGF deck pages 24 and 25, against the OAG schedule store. Three new scripts, all
    check-only, none of which changes a forecast number: `scripts/guard_oag_wedge.py`,
    `scripts/build_fleet_wedge.py`, `scripts/gap_decomposition.py`, plus
    `config/aircraft_body_types.yaml` mapping all 245 aircraft codes in the store to an
    aisle count and a class, so Boeing's single aisle, regional jet and widebody
    segments can each be cut from the same data.

    The identity holds to zero residual: ASK = departures x seats per departure x stage
    length. World single aisle, 2015-2019, ASK 6.9% a year = departures 5.0% x gauge
    1.2% x stage length 0.6%. Gauge splits by shift-share into up-gauging 0.5% and
    densification 0.6%. Over 2015-2025 the single aisle wedge is ASK 4.5% = departures
    2.7% x gauge 0.9% x stage 0.8%. Boeing's window is 2004-2023 and ours cannot be,
    because the store holds 2015-2019 and 2023-2025 with 2020-2022 excluded by policy;
    the window difference is stated on the output and must be stated on the slide.
    Boeing's fourth term, flights per aircraft per day, is not produced: it needs a
    count of aircraft in service, and deriving it from the dashboard's PROD_NB = 330
    and PROD_WB = 1,050 constants would return whatever was typed in.

    **The finding that matters.** `compare_regions_boeing.py` states in its header that
    a constant stage length cancels in a CAGR. It cancels between our RPK and our own
    passengers, which is why our RPK CAGR equals our passenger CAGR to the decimal
    place. It does NOT cancel against Boeing, whose RPK CAGR carries their stage length
    growth inside it, and that comparison is the only thing the script is for. Measured
    stage length growth from the schedule is 0.6% a year at world level over 2015-2025.
    Applied as a test, the world gap against Boeing goes from -0.9pp to -0.2pp, Eurasia
    from -1.1pp to -0.1pp, Southeast Asia from -1.4pp to -0.2pp and North America from
    -0.8pp to -0.3pp, while China stays at -1.8pp, Africa -1.2pp and the Middle East
    -1.1pp. Two thirds of the headline gap is a conversion convention; what is left
    sits in the regions where affordability is the mechanism we do not model. Nothing
    is changed: `gap_decomposition.py` measures, it does not write. A mechanical
    extrapolation over-corrects Oceania and Northeast Asia, so the fix is a stated
    stage length path per region, not a single historic rate. Owner: John.

109. **Two defects the guard caught before any number was published.**
    (a) The Heathrow 2019 anchor in `avia_forecast/ingest/oag_store.py` is a TWO-WAY
    figure: 477,954 movements and 100.4m seats count arrivals and departures together,
    as an airport publishes them. The store holds one row per departure, so a
    departures-only query returns exactly half and reads as a store missing half its
    data. The docstring did not say so and now does, with the one-way figures beside
    it: 238,978 departures and 50.2m departing seats.
    (b) **1,503 departure airports in the OAG store carry no record in
    `data/global_airport_meta_2025.json`, and among them are Beijing Daxing and Chengdu
    Tianfu.** PKX went from 1.85m departing seats in 2019 to 31.87m in 2025 and TFU
    from nil to 33.34m, while PEK fell from 62.65m to 45.28m and CTU from 32.87m to
    19.91m. The Beijing system grew 19.6% between 2019 and 2025 and the Chengdu system
    62%; the forecast, seeing only PEK and CTU, reads them as -27.7% and -39.4%. China
    is our largest gap against Boeing at -1.9pp and this is the first candidate for it.
    Also absent: Mexico Felipe Angeles, Astana Nursultan Nazarbayev, Dakar Blaise
    Diagne, Goa Mopa, Yogyakarta International, Medan Kualanamu, Warsaw Modlin. Sizing
    the effect on the China forecast is the next measurement. Owner: John.

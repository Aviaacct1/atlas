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

## 6 July 2026 - ACI per-airport throughput ingest + hub calibration (Phase 3, before 3b)

24. **ACI annual traffic ingest** (scripts/ingest_aci.py). Decrypted the password-locked ACI
    datasets (2015-2020, 2022) and parsed the annual per-airport panel 2013-2024 by name-matched
    columns (layout/order shifts between years): iata, year, region, country_code, city, terminal
    pax, domestic/international split, direct transit, total pax, movements, cargo. 27,015 rows,
    1,762 (2013) -> 2,557 (2024) airports; world terminal pax 5.96bn (2013) -> 8.87bn (2024) with
    the correct COVID collapse to 3.25bn in 2020. Data on E:\Avia\Global (off OneDrive). ACI is
    subscription data: internal base-year calibration/history only, never redistributed (class C).
    Monthly ACI 2004-2012 now also on E: (pre-2013 gap-fill + seasonality) for later.

25. **Base-year hub calibration from ACI vs Sabre** (data/aci_hub_calibration_2024.json). Connecting/
    transfer per airport = ACI terminal minus Sabre O&D both ends. Result is textbook: DOH 84%, PTY
    80%, CLT/IST 68%, FRA/ATL 64%, DXB 57%; pure-O&D airports (LTN, STN, ORY, BGY, ALC) 0-4%. This
    gives 3b its hub identification and connecting magnitude to calibrate against - the reason ACI
    was sequenced before 3b.

## 6 July 2026 - Phase 3b: terminal passengers with transfers (ACI-anchored)

26. **Global terminal forecast** (avia_forecast/global_terminal.py + scripts/run_global_terminal.py;
    global_demand.py extended to return per-airport O&D + international growth indices). Terminal =
    local O&D + connecting, base year anchored to ACI 2024 true throughput: each airport's terminal
    splits into Sabre O&D (both ends) and connecting (ACI terminal minus that). Forward, local O&D
    grows at the airport's O&D demand rate, connecting at its international O&D rate (transfer volume
    tracks the international feed). Result (Baseline): world terminal 8,896m (2024, = ACI published
    ~8.9bn) -> 20,017m (2050), 3.30%/yr; within 0.10pp of the ACI World Airport Traffic Forecast
    (3.4%). Regional: Asia Pacific 4.64%, Africa 6.60%, Other Europe 2.79%, mature North America
    1.78% / EU+UK 1.45%. Extract data/global_terminal_2024_2050.json. This is region-based connecting
    v1 (grows the ACI base-year connecting mass on the real hub split); the per-hub final-to-next M
    matrix from OAG route structure is the next refinement. Full suite 139 green.

## 6 July 2026 - Per-hub final-to-next M from OAG (3b refinement)

27. **OAG final-to-next M matrix** (data/oag_final_to_next_M.json from oag.duckdb, 12.9m schedule
    rows). Per airport, the destination-region distribution of departing seats (Domestic where arr
    country = dep country; else region_for_iso2). 3,952 airports. Textbook hub profiles: DXB 42%
    Asia Pacific/22% EU+UK, ATL 76% Domestic, SIN 78% Asia Pacific, ADD 30% Africa, LHR 33% North
    America. global_terminal now routes each hub's connecting across destination regions by its M row
    and grows each slice at that region's O&D rate (renormalised so the base year reproduces the ACI
    connecting anchor), replacing the single blended international rate. World terminal 8,896m ->
    20,290m (2050), 3.35%/yr, within 0.05pp of the ACI forecast (3.4%). Full suite 139 green.
    GDP: per-country history+forecast to come from the OEF world file (staging to E:); the World
    Bank API multi-country query does not return via the fetch tool, only country/all paginated.

## 6 July 2026 - Per-country OEF GDP wired; income-elasticity finding

28. **OEF GDP + population ingest** (scripts/ingest_oef_gdp.py -> data/oef_gdp_pop_by_iso2.json).
    Parsed the OEF world file (E:\Avia\Global\OEF), GDP constant prices + population per country
    1980-2050, mapped 197 countries to ISO2 (pycountry + overrides). OEF licensed = internal only.

29. **Per-country GDP wired into the demand driver** (global_demand._gdp_index). Each airport now
    grows on its home country's own OEF GDP path (history+forecast), falling back to the regional
    assumption only where OEF is missing (0.7% of O&D). Scenario GDP delta applied as a cumulative
    growth shift. Effect: world O&D/terminal CAGR moves from 3.35% to 3.05% - OEF forward GDP is
    more conservative than the earlier regional guesses, and a bottom-up econometric build runs a
    little below the top-down ACI/OEM figures (3.05% terminal vs ACI 3.4%). Model now real data end
    to end: Sabre O&D + ACI throughput + OAG routing + OEF GDP + propensity. Suite 139 green.

30. **Income-elasticity regressions - FINDING, not wired** (scripts/estimate_country_bG.py ->
    data/estimated_bG_by_country.json). Regressed ln(ACI terminal) on ln(OEF GDP) per country
    2013-2024 with COVID/supply dummies. Result: mature markets show implausibly high elasticities
    (US 3.06, GB 4.21, JP 5.63) because over a short window their small GDP growth is swamped by
    autonomous traffic growth (recovery, LCC, tourism), loading it onto the GDP slope. The
    reliability filter pools most; only some emerging markets (IN 2.47, TR 1.94, CN 1.37, ID 1.21)
    identify cleanly. This CONFIRMS the design's choice of propensity-based maturity over short-window
    regressions, so the estimated bG are NOT wired in; the maturity/literature defaults stand.
    Fix = the longer trend John wanted (ACI 2011/2012 + 1991-2002 + monthly 2004-2012) for real
    per-airport identification. global_drivers.gdp_growth_by_region is now only a fallback.

## 6 July 2026 - ACI long panel (1991-2024) rescues the elasticities

31. **ACI long panel** (scripts/build_aci_long_panel.py -> data/aci_panel_long.json). Parsed the
    1991-2002 long-format file and the 2010-2012 two-row files, merged with 2013-2024; country
    backfilled by IATA. 39,172 rows, 1991-2024 (2003-2009 gap), 529 (1991) -> 2,430 (2024) airports.

32. **Elasticities re-estimated over 1991-2024 - now identify cleanly.** With the long trend the
    contamination clears: US 0.81 (was 3.06), GB 1.84, CN 1.72, IN 1.80, TR 2.25; 137 of 163 reliable
    (was 51). Japan still pools (tourism boom on flat GDP, genuine outlier). Confirms John's long-trend
    instinct.

33. **Elasticity/propensity interaction surfaced as a toggle.** Three configs bracket the forecast:
    literature bG + propensity 3.05% (-0.35pp vs ACI); estimated bG + propensity 4.07% (+0.67pp);
    estimated bG no propensity 4.73%. Estimated elasticities embed non-repeating structural gains
    (deregulation, LCC, catch-up), so raw use over-projects. New book flag
    global_drivers.use_estimated_elasticities (default FALSE = conservative ACI-aligned 3.05%; TRUE =
    empirical 4.07%). A modelling decision for Jess. Suite 139 green.

## 6 July 2026 - Team viewer (localhost + static deploy)

34. **Web viewer** (webapp/: serve.py stdlib server, index.html Chart.js dashboard, data bundle,
    Run Avia Forecast.bat, README). scripts/build_webapp_data.py runs the engine across Baseline/
    High/Low and emits webapp/data/{world,airports,meta}.json (2,430 airports). Dashboard: world +
    regional terminal to 2050 with scenario toggle, KPIs, region CAGR table, airport explorer
    (search -> per-airport 3-scenario forecast + connecting share + OAG hub network bars), top-120
    table. Zero-dependency (Chart.js via CDN). Runs at localhost:8000; listens on all interfaces for
    LAN sharing; fully static so deployable to a test domain (avia-analytics) as static hosting.
    Verified serving + endpoints in-sandbox. Suite 139 green.

## 6 July 2026 - Detailed Dashboard mockup wired to the engine

35. **Global Dashboard mockup now engine-driven** (webapp/dashboard.html + scripts/build_dashboard_data.py).
    The v8 dashboard's synthetic data layer (RG/CTY/APT/FLOWS/series) replaced by a real engine extract
    (webapp/data/dashboard.json): per-airport pax series with ACI history 2015-2024 spliced into the
    engine forecast 2025-2050 across Baseline/High/Low, real airport names, country metadata (dom share
    from ACI, GDPpc/pop from OEF/WB), region-pair O&D flows from Sabre, region growth. Mapped to the
    dashboard's 6-region scheme. The full UI (metric switch pax/RPK/ASK/ATM/CO2, index views, CAGR
    windows, region/country/airport drill-down, fleet split, comparator overlays) now derives from real
    pax. Verified: dashboard rollups reproduce the engine exactly (world 8,896m->18,865m 3.05%; ACI
    history continuous, 2024=8,868m). JS syntax-checked, serves clean. index.html now lands on the
    dashboard; simple viewer kept at viewer-simple.html. NEXT: wire the analyst Cockpit similarly.

## 6 July 2026 - Forecast horizon = base year + 35 (rolling), GDP extended beyond OEF

36. **Horizon base+35 (2060 this vintage), rolls forward.** meta.horizon_years: 35 (OEMs do 20, Avia
    does 30-35). global_demand years = base..base+35; every extract, the dashboard span and its spot/
    CAGR windows now derive from base/horizon so next year they roll to 2061 with no code change.
    OEF GDP ends ~2050, so _gdp_index now EXTENDS each country's GDP beyond the OEF horizon at its own
    terminal growth rate (last OEF year-on-year), rather than letting growth flatten - matches how the
    team extends GDP by hand for 30-35yr manual forecasts. World terminal now 8,896m (2025) -> 24,497m
    (2060). Dashboard, viewer and data bundles regenerated to 2060. Suite 139 green.

## 6 July 2026 - Dashboard growth-markets table wired to real Sabre O&D

37. **Growth-markets (OUT-19) fixed.** Was showing the same fastest-growing small markets (Myanmar,
    Cambodia) for every airport because it distributed traffic across all countries by a synthetic
    rule. Now build_dashboard_data emits each airport's real destination markets from Sabre O&D 2024
    (country-grouped, domestic collapsed), and growthMarkets() ranks those by absolute growth. Verified:
    SOU -> Domestic UK, Ireland, Netherlands, Spain; LHR -> USA, India, Germany, UAE, Canada.

## 6 July 2026 - Analyst Cockpit wired to the engine + landing page

38. **Cockpit base + picker engine-driven** (webapp/cockpit.html + scripts/build_cockpit_data.py ->
    webapp/data/cockpit.json). The cockpit's synthetic base is replaced by real engine data: airport
    picker now covers all 2,430 modelled airports; bcSeries('base') = the real engine per-airport
    forecast (2019-2060, ACI history + engine forecast), and overrides/overlays/scenarios scale that
    real base by the mockup's delta ratio (base=engine, edits=override effect). Sandbox ENT entities
    (Global/region/country/airport) read real engine rollups; assumption edits apply as growth deltas.
    Per-airport inputs (base pax, dom share, connecting share, income elasticity) are real (LHR ge 1.84,
    DXB 3.15). Verified: Global rolls up to the engine exactly (8,896->24,497m); LHR 84->182m. JS
    syntax-checked, serves clean. New landing index.html links the Dashboard and Cockpit under Avia
    Cortex. STILL SYNTHETIC (deeper integration later): the BUM route lists and QSI candidate routes
    (would come from real OAG schedules + the QSI tool), the delta LOGIC of some overrides (fast JS
    what-if approximations by design; the governed promote path re-runs the engine).

## 6 July 2026 - Adaptive units for small airports (thousands vs millions)

39. **Adaptive demand units** (dashboard fmD). Sub-million values were rounding to "0.0m" for small
    airports (SOU destination markets). fmD shows millions for >=1m (integer >=10m) and thousands for
    smaller (263k, 19k), <1k below. Applied to the growth-markets table (OUT-19) and the traffic-mix
    panel. SOU now reads Domestic UK 263k->447k, Ireland 32k->47k, Netherlands 19k->37k; hubs unchanged.

## 6 July 2026 - Adaptive units + cockpit picker fix

39. **Adaptive demand units (dashboard).** Sub-million values rounded to "0.0m" for small airports.
    New fmD: millions for >=1m (integer >=10m), thousands below (263k, 19k). Applied to growth-markets
    (OUT-19) and traffic-mix. SOU now reads Domestic UK 263k->447k, Netherlands 19k->37k; hubs unchanged.
40. **Cockpit airport picker fix.** pickApt matched airport NAME as a substring of the option text, so
    picking "SOU - Southampton (United Kingdom)" matched a tiny airport coded TED ("ted" inside "uniTED"),
    whose zero base gave all-zero/NaN outputs. Now matches the leading IATA code token exactly. SOU
    resolves to its real base (0.86m) and forecast.

## 6 July 2026 - Adaptive units across the cockpit

41. **Cockpit adaptive units.** Sub-million airports (e.g. SOU 0.86m) showed 0.00 everywhere in the
    bespoke view. Added fmM (millions >=1m, integer >=10m, thousands below) and applied it to the impact
    table (m rows, label unit dropped since inline), the bespoke KPIs, the overlay waterfall, the scenario
    deliverable table and the BUM base reconciliation. Small airports now read in k, hubs in m.

## 6 July 2026 - Cockpit BUM blend: level-anchored + persistent (John)

42. **BUM merge reverts fixed.** The blend was growth-anchored with a ramp-OUT: it lifted BY+1 with the
    new routes then decayed the effect back to the old model path over N years, so a successful route
    reverted (invisible at a hub, an odd spike-and-return at a small airport). Now LEVEL-anchored and
    PERSISTENT: the BUM sets the near-term level (ratio = BUM BY+1 total / model BY+1), ramped in over
    N years, then held - the model long-run growth compounds on the elevated base. Symmetric, so removing
    routes or an airline failure lowers the level and holds it. This is the analyst primitive John wants
    for refining individual engine forecasts (new routes raise it and stay; failures lower it). Verified:
    x1.34 uplift ramps in over 3 yrs then persists, blended grows at the model rate on the higher base.
    Legend/note updated. JS clean.

## 6 July 2026 - BUM route bridges + launch-year (3-year build-up)

43. **Route additions bridge (BUM tab).** New mkBridge waterfall. Added routes (ticked QSI candidates +
    custom SCHED-GAP lines) now shown route by route: base forecast + each route to the year total, so the
    routes are not lost in client presentations.
44. **Launch year per added route + 3-year build-up (John).** Each added route (QSI candidate and custom
    SCHED-GAP line) gets a launch-year selector: current year (BY), next (BY+1) or the year after (BY+2).
    New addedRoutes() carries the launch year; bumTotalK counts only routes launched by BY+1 so a later
    route does not spike the near-term anchor. The bridge is now three phased panels (Current / Year 1 /
    Year 2): each route appears in its launch year and persists, grown at the model rate. Supports a
    three-year bottom-up. JS clean.

## 6 July 2026 - BUM candidate routes from the QSI tool (drop-in)

45. **BUM QSI candidates wired to a real feed.** The cockpit's QSI candidate routes were hardcoded
    samples; they now load webapp/data/bum_candidates.json ({airport:[candidate routes]}), falling back
    to samples for airports not in the feed. scripts/build_bum_candidates.py produces it: default QUICK
    mode = each airport's largest UNSERVED Sabre O&D markets (real new-route opportunities with market
    size + placeholder capture); --optimise mode runs the QSI tool route_forecast.forecast() per candidate
    for the OPTIMISED route demand + QSI share (run on the machine with the QSI databases; the 16GB Sabre
    DB makes it too slow elsewhere - confirmed by a >45s timeout here). Seeded 14 demo airports: SOU ->
    Geneva/Paris/Malaga (real unserved), DXB -> Malta/Trabzon. This matches John: run ~10 optimised
    routes and drop them in for the analyst to select. cockpit qsiCands reads the feed; launch-year +
    3-year bridges now sit on real candidate routes. JS clean.

## 6 July 2026 - QSI candidates from the real tool (incremental runner + live cockpit)

46. **Runner: real QSI tool, 10 routes, incremental** (scripts/run_qsi_bum.py). Calls the existing
    route_forecast.forecast() per candidate route and rewrites bum_candidates.json after EACH one (with a
    _status line), so the cockpit shows the first routes while the rest compute. Runs on the machine with
    the QSI tool + 16GB Sabre DB, in the background. ENVIRONMENT NOTE: the full forecast() cannot run in
    the Cowork sandbox - a single command caps at 45s and background jobs do not survive between commands
    (each is a fresh isolated session) - so the heavy optimiser must run on John's machine (no cap there).
    The lighter route_qsi scorer DID run here (real QSI shares), used as the interim in build_bum_candidates.
47. **Cockpit: scrollable QSI list + live poll (John's design).** QSI candidate table is now a scrollable
    box (~5 rows visible, rest below), with a "Running the QSI tool: X of N optimised, more loading" line;
    the cockpit polls bum_candidates.json every 4s while the BUM tab is open and the run is active, so routes
    appear as the tool finishes them. JS clean.

## 6 July 2026 - On-demand QSI service (the proper fix for laptop analysts)

48. **QSI route service** (webapp/qsi_service.py). The real fix for "Jess on a laptop needs SOU's BUM
    now": a small server run on the machine with the QSI tool + databases (the box behind the Cloudflare
    tunnel), serving the cockpit AND exposing GET /api/bum?airport=SOU, which runs the real optimiser
    (run_qsi_bum -> route_forecast.forecast) in a BACKGROUND THREAD and writes each route into
    bum_candidates.json as it finishes. The cockpit's 4s poll streams them into the scrollable list.
    Analysts install nothing - browser + tunnel. New cockpit button "Run QSI candidates for <airport>"
    calls the service; graceful message when running static-only (serve.py). Threaded server so it is not
    bound by the one-shot/45s limits that stopped the tool running inside the sandbox. Deploy: run
    qsi_service.py instead of serve.py on the QSI box, expose via the same tunnel. JS + Python clean.

## 6 July 2026 - Forecast adjustment ledger, cockpit recovery, dashboard fixes

49. **Forecast adjustment ledger (recreatable record).** The global sandbox now carries a declarative,
    net-final ledger: forecast = engine(vintage) + the ledger. One row per target, so 20 tweaks to a
    variable collapse to its final value; it is not a keystroke history. "Record this forecast" commits the
    current edits (author, reason, date, engine base per target); "Add airport/route adjustment" captures
    level shifts (new route up, airline failure down). "Export reproducible record" writes the vintage, the
    data inputs, the assumptions snapshot and the adjustment set as JSON, so a run can be rebuilt: re-run the
    engine at that vintage, reapply the adjustments. "Simulate corrected engine re-run" moves an engine base
    and the ledger flags every adjustment whose base drifted, for review - the restore/correct workflow for
    the day an error is found. Session-scoped in the mockup; production persists it server-side, append-only.

50. **Cockpit tail recovered.** An Edit-tool write to cockpit.html truncated the file mid-renderBC (the
    OneDrive/mount write-sync trap). Reconstructed from the session transcript and the original mockup: the
    deliverable card, the bcSeries engine-blend wrapper, pickApt (exact IATA match), setMode, runQSI, CK_BOOT
    (loads cockpit.json + bum_candidates.json) and the 4s BUM poll. node --check clean. Lesson re-learned:
    edit these files via bash, not the Edit tool.

51. **Interregional matrix is now true RPK; South America long-haul visible.** region_pair_flows() weighted
    each region pair by a representative one-way stage length (RPK_bn = pax_m x km / 1000) instead of
    reporting grown passenger millions under an "RPK" title. South America to Africa/Asia/Middle East were
    real but thin (0.07-0.09m O&D pax, one-stop-dominated) and rounded to zero; they now show as ~1-2 bn RPK
    rather than blank. Rebuilt dashboard.json.

52. **Illustrative capacity restores the constraint line.** Every airport read cap=0 (register pending Jol),
    so the constrained series equalled the unconstrained one and no constraint line showed. Added a grade-C
    illustrative practical capacity per airport (tiered by size: hubs 1.35x base, down to 2.8x for small
    fields), creeping up 1.8%/yr (densification, ATM efficiency), with a smooth spill. World capacity
    requirement now circa 7% by 2045 and 16% by 2060; 340 airports capacity-bound by 2045. All airports kept
    in and flagged illustrative; the airport chart draws the growing capacity line. Jol's register replaces
    the illustrative values when it lands.

## 7 July 2026 - Acting on Fable's adversarial review (safe unblocking package)

53. **Central data-root resolver (review #3, critical).** avia_forecast/paths.py resolves the
    Global data root, the database root and the QSI tool from environment variables, then the
    Windows working locations, then the sandbox mount; first existing wins. All 14 files that
    carried hard-coded /sessions/... paths now import from it. The engine regenerates on any
    machine, not only the session that wrote it. Tests green (no import breakage).
54. **GDP-tail and elasticity clamps (review #7 and #1).** global_demand._gdp_index extends
    beyond OEF on the trailing 5-year CAGR, not one spiky final year, clamped to [0, 4%].
    Applied income elasticity is clamped to a documented book bound (global_drivers.
    bG_applied_bounds [0.6, 2.2]) via _clamp_bG, so out-of-band country estimates (UAE 3.15,
    Latvia 3.48) cannot compound over 35 years. Re-estimating on Sabre O&D is left for John.
    New tests: no applied bG outside the bound; a spiky-tail GDP fixture stays clamped.
55. **QSI service hardened (review #6 and #12).** /api/bum validates the airport as ^[A-Z]{3}$,
    caps n at 15, and enqueues to a single worker so runs serialise (no concurrent whole-file
    rewrites). run_qsi_bum writes bum_candidates.json atomically (tempfile + os.replace) so the
    cockpit poll never reads a half file, and warns when forecast() returns an unrecognised
    result shape instead of silently guessing. Docstring default path aligned. Validation and
    atomic write unit-tested.
56. **Honesty labels (review #5, #10, #11).** Dashboard banner and export headers now describe
    an engine build on licensed data with illustrative elements labelled, not "synthetic".
    What's New bridge and tracking cards marked LAYOUT DEMO with a header note. The RPK matrix
    carries its basis and three caveats. Builder note reads the vintage horizon (2060, not
    2050). A fixtures[] list of placeholders travels in the extract meta and the served
    dashboard.json.

NOT DONE (need John's decision or the E: drive): converge the global path onto the identity
engine and move grossing into the engine (#2, #4); per-airport dom/cx and applied ge in the
cockpit extract (#8); re-estimate elasticities on O&D (#1); stage the Excel parity gate into CI
(#9). The E: portable drive (E:\Avia\Global) was not attached this session, so the full data
rebuild could not be re-run here; the resolver returns the same location when it is present.

## 7 July 2026 - Converging the global path (review #2 and #4, first increment)

57. **Adding-up discipline on the global build; grossing out of the browser.** New
    avia_forecast/global_checks.py ports the identity discipline to the global levels: country =
    sum(modelled airports) x coverage_country; region = sum(countries) x coverage_region;
    world = sum(regions); reconcile_levels + assert_adds_up flag missing or non-positive coverage
    and assert the world reconciles. Unit-tested on a synthetic hierarchy. The two grossing
    constants that lived in dashboard.html (country x1.12, the per-region map up to Africa 3.4)
    are now documented data: coverage_country and coverage_region in the extract and the served
    dashboard.json; the front end reads them (identical totals, verified: world 2045 unchanged at
    39,051m). build_dashboard_data emits the factors and runs the adding-up check, printing world
    base-year and any issues, with the result in the extract meta. Validated on the served data:
    base-year world grosses to 20,906m, all levels reconcile, zero issues.
    STILL OPEN (needs the E: drive to run the global build): replace the placeholder coverage with
    engine-computed real coverage (ACI country total / modelled), run per-airport T-B on the global
    terminal, and merge global_terminal.py onto the pilot identity pipeline so one method serves both.

## 7 July 2026 - BUM apply regression fixed

58. **Apply BUM merge was cratering the forecast.** The level-anchored merge set the level to
    (bottom-up total / model). The bottom-up route list is a SAMPLE that sums to far less than the
    airport's full base, so the ratio fell below 1 and applying BUM collapsed the forecast (SOU
    -46% to -52%), worse for smaller airports. Replaced with an ADDITIVE net-change shift: applying
    BUM moves the level only by the analyst's changes - the edited existing schedule versus its
    engine-default baseline (new bumBaselineK), plus added routes from their launch year - ramped
    over N years and persisted. The sample's absolute size cancels. Verified headless: apply with
    nothing ticked leaves 2.888m unchanged; a 120k route adds +0.12m; a 40k route adds +0.04m;
    never craters. Refresh the cockpit to load it.

## 7 July 2026 - Cockpit: Econometrics (regression diagnostics) tab

59. **New Econometrics tab in the bespoke cockpit (John's request).** Shows, per airport, what the
    model assumed and on what regressions. Three cards plus a fit chart: (a) "How this airport is
    driven" - states that demand is built market by market, each destination on its OWN country GDP,
    but a single estimated income elasticity per airport (not per-market regressions); shows the
    estimated elasticity, the applied value, and the book bound, and flags when the estimate sits
    outside the bound and is capped. (b) A ln(pax) vs ln(GDP) line-of-best-fit chart with the real
    slope; scatter points and R2/t are labelled illustrative until the estimation extract ships them.
    (c) The key-markets table - each destination and the GDP series driving it - which answers "does
    the hub use key-market GDP or just national": the driver is per-market, the elasticity is one
    value. (d) Segment fare terms (locked). Real data: the eight estimated UK airports carry their
    actual bG (Heathrow 1.33, Stansted 2.97 shown capped to 2.20, Manchester 3.02, ...) and the real
    segment fare terms; markets come from real Sabre O&D. The page also surfaces Fable issue #8: the
    APPLIED elasticity (GB default 1.84) differs from Heathrow's estimate (1.33), visible side by side.
    Front end reads a per-airport regress block from CKBYI; build_cockpit_data emits it on rebuild.
    Verified headless for LHR, STN, SOU. Refresh the cockpit to see it.

## 7 July 2026 - Persist the regression diagnostics the engine already computes

60. **Econometrics page wired to real regression stats (John: "hasn't the engine done this?").**
    It has: estimate.level1.fit_cell_restricted already returns the full fit - bG, R2, t, standard
    errors, residuals, n - on every run; we had only persisted the bG scalar (uk_estimated_bG.json).
    Added scripts/estimate_airport_diagnostics.py: runs that same, tested restricted fit over the long
    ACI panel and writes data/airport_regress.json = {IATA: bG, r2, t, n, window, reliable, points}
    (points = the GDP partial-regression scatter). build_cockpit_data now attaches the FULL diagnostics
    where present, falling back to bG-only. The Econometrics tab already renders points/R2/t when they
    arrive. Reader matches the authoritative panel format (list of records, country_code/terminal_pax/
    year) and OEF GDP under "gdp"; UK airports use uk_real_gdp_oef. Self-test proves the path without the
    drive: recovers a known bG (1.25 -> 1.238, R2 0.99, 34 points). Also confirmed the short 2015-2024
    window inflates elasticities (LHR 3.79 vs the long-panel 1.33), so the run must use the long panel.
    One-command rebuild: "Rebuild engine data (full estimation).bat" -> estimation, dashboard, cockpit.
    Runs on the machine where E:\Avia\Global is attached (the sandbox cannot reach E:).

## 7 July 2026 - Income vs GDP elasticity; chart axis labels

61. **Income (per-capita) elasticity added, not just GDP (John's catch).** The fit drives off TOTAL
    GDP, so the headline elasticity is a GDP elasticity that absorbs population growth (total GDP =
    population x GDP per head). estimate_airport_diagnostics now also runs the restricted fit on
    passengers PER CAPITA vs GDP PER CAPITA (population from the OEF pop series), giving the true
    income elasticity, saved under regress.income {bY, r2, t, points}. The Econometrics page shows
    both, relabelled: "GDP elasticity (total GDP)" and "Income elasticity (per capita)", with a note
    that passengers = population x propensity(income). Populates on the next full-estimation rebuild.
62. **All display charts carry axis titles.** Dashboard main chart (y = selected metric, x = Year)
    and history chart (y = Passengers log scale, x = Year); cockpit global/bespoke chart (y =
    Passengers (m), x = Year) used across the sandbox and bespoke tabs; bridge charts carry the pax
    unit; the econometrics scatter already labelled ln(pax)/ln(GDP). viewBox extended by a small band
    so the plot area is unchanged.

## 7 July 2026 - Econometrics: calculated vs applied on one page (sign-off)

63. **Sign-off basis card + real-points fix (for Nick and Jess, airport by airport).** Fixed the
    scatter mislabel: the "illustrative" tag checked the trimmed BC.apt, not the full CKBYI record,
    so real computed points always read illustrative; now estimated airports read "Observed". Added
    a "Forecast basis - what was actually used (sign-off)" card at the top of the Econometrics tab,
    two columns: APPLIED (the income/GDP elasticity that actually drove this airport's forecast, with
    its source - country-level - plus fare elasticity, near-term growth, terminal growth, maturity)
    versus CALCULATED (the airport's own regression bG, R2, t, n, reliability, and the per-capita
    income elasticity). A status line resolves the case: uses the airport's own estimate; or the
    airport fit fails the reliability filter so it falls back to the country default (OK); or - amber
    Review - the airport has a reliable own estimate that DIFFERS from the country value applied, so
    the basis must be confirmed before sign-off (this surfaces Fable #8 per airport). Verified headless
    across all three cases.

## 7 July 2026 - Run QSI on the BUM page fixed (poll never started)

64. **BUM "Run QSI" produced nothing even with the service running.** The streaming poll gated on
    CKCAND._status.running already being true, but that flag is only set by the poll itself, so the
    first request was never read back. Reworked: runQSI opens a 10-minute poll window (pollBUM) and
    fires an immediate refresh; the poll streams candidates as they land and stops once the run
    reports finished. run_qsi_bum now writes an immediate "finding candidate routes" status so the UI
    confirms receipt within a second; qsi_service writes any run failure as _status.error, and the
    BUM tab shows it (plus a pointer to the console) instead of sitting silent. node --check clean.

## 7 July 2026 - BUM QSI candidates: route forecast, not market total

65. **Run QSI pulled total market demand, not the two-way route forecast (John's catch).** The runner
    read the forecast result's `total_demand` (point-to-point capture PLUS all the connecting feed
    routed through the destination hub), which for hub destinations like Toronto inflates to the whole
    market (SJC-YYZ showed 4,770k). Fixed _pax to take `captured_demand` - the two-way point-to-point
    demand the route actually wins - with `carried_forecast` (capacity-bounded) as the fallback, ahead
    of total_demand/natural_market. Same fix in build_bum_candidates.py --optimise. Restart the QSI
    service and re-run; the est-pax figures drop to realistic route demand.

## 7 July 2026 - BUM route forecast includes connecting pax

66. **Route est-pax now includes connecting feed (John's call).** Switched the runner's headline
    figure to `carried_forecast` - the passengers the route actually carries, point-to-point PLUS its
    connecting feed, realistically bounded (unlike total_demand, which is unbounded and balloons to the
    whole market at a hub). Each candidate row also carries the split (p2p_000, conx_000, carried_000,
    demand_000), and the cockpit candidate table shows "P2P x + conx y" under the est so the make-up
    is visible. build_bum_candidates --optimise aligned. Restart the QSI service and re-run.

## 7 July 2026 - BUM candidates as optimised routes (airline + aircraft + frequency)

67. **QSI candidates now optimise the operating plan, not a fixed A321 with spill (John's call).**
    New guarded _optimise_route in run_qsi_bum: takes the candidate's demand, computes the sector,
    calls the QSI tool's aircraft_select (profit-best, range-feasible gauge matched to demand), tags
    the origin's largest OAG carrier as the suggested operator (optionally restricting the gauge to
    that airline's fleet), sizes frequency to clear the spill, then re-forecasts at that plan so the
    route carries its demand. est-pax is the carried figure; each row carries plan {airline, aircraft,
    freq}. Cockpit candidate rows now read e.g. "SJC-JFK / B6 A320 7x/wk" with the P2P+connecting split
    beneath. Fully guarded: any failure falls back to the plain carried forecast, and the service
    surfaces errors. Restart the QSI service and re-run.

## 7 July 2026 - Atomic writes + parse-back; real coverage; repo gate (critical)

68. **Served JSON corruption fixed at the source (dashboard/cockpit/bum_candidates were unparseable).**
    Root cause: non-atomic json.dump(open(...,"w")) in every builder, plus qsi_service's error write
    racing the runner. New avia_forecast/io_safe.dump_atomic writes to a temp file, fsyncs, PARSES IT
    BACK, then os.replace - an interrupted or invalid write can never truncate the served file (the
    good file is left in place). Routed all builders, the BUM runner and the service error write
    through it. Verified: valid write publishes; a failed write leaves the original intact; no temp
    leftovers. Needs a full rebuild with E: attached to regenerate the three corrupt files.
69. **Coverage factors now real, not a magic 1.12.** build_dashboard_data computes coverage_country
    and coverage_region from the ACI panel (country/region total over the modelled set, grossing up
    only, floored at 1.0, capped), with the documented placeholder as fallback only when the panel is
    absent; the coverage source is stamped in the extract meta. Populates on rebuild.
70. **Repo validity gate + git hook.** scripts/validate_repo.py fails on any invalid served JSON or
    any absolute sandbox path (paths.py exempt); githooks/pre-commit runs it; .gitignore excludes the
    large regenerated extracts and binaries. Confirmed the gate flags the three corrupt files today.
    git init must be run natively on the Windows box (the sandbox mount cannot manage .git locks).
    STILL OPEN: the Excel parity gate against Jess's template has never run (needs the template staged).

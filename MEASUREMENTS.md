# Atlas: measurements behind the open decisions

Version 1.0, 9 August 2026. Avia Solutions.

Numbers produced to settle a specific question, with the run that produced them named,
so a decision is taken against evidence rather than against a recollection. Add a section
when a question is measured; do not delete one when it is answered, record the answer.

---

## 1. What turning on the estimated country elasticities would do

**Question.** `global_drivers.use_estimated_elasticities` is off, so the 137 reliable
country income elasticities in `estimated_bG_by_country.json` are loaded on every run and
discarded. Should it be turned on?

**Run.** `avia_forecast.global_demand.run_global`, Baseline scenario, on the tree of
9 August 2026, with the switch forced on and off and nothing else changed.

| | World O&D departing pax 2060 | CAGR 2025-2060 |
|---|---|---|
| Switch off, as shipped | 9,644m | 3.26% |
| Switch on | 11,894m | 3.88% |
| Difference | +2,249m | +0.62pp |

That is **23.3% on the world 2060 figure**, roughly twice the size of the 8 August
correction and in the opposite direction. By region:

| Region | Off, 2060 | On, 2060 | Change |
|---|---|---|---|
| Domestic | 5,943m | 7,694m | +29.4% |
| Asia Pacific | 1,441m | 1,552m | +7.7% |
| EU+UK | 1,052m | 1,308m | +24.4% |
| Middle East | 395m | 397m | +0.3% |
| North America | 296m | 335m | +13.2% |
| Other Europe | 234m | 295m | +26.1% |
| Africa | 210m | 228m | +8.6% |
| South America | 73m | 86m | +17.9% |

**Recommendation: leave it off until the country fits are re-estimated.** The estimates
themselves say why. Across the 137 countries the median is 1.70 and the distribution runs
from 0.48 to 3.48, against an applied bound in the assumptions book of 0.6 to 2.2. **45 of
the 137, a third of them, sit at or beyond the upper bound and are clamped on the way in.**
The highest are Latvia 3.48, Brazil 3.48, the Bahamas 3.45, Iceland 3.40 and Peru 3.36.

A long-run income elasticity above 3 says a country's air travel grows more than three
times as fast as its real income, indefinitely. That is a plausible reading of a short
catch-up history and is not a credible forecast parameter. A third of the set being pinned
at the clamp is the tell: the fits are picking up something other than income response,
most likely liberalisation, low-cost entry and network build in the estimation window.

The clamp is doing its job, which is also the problem. A parameter set that only behaves
because a bound catches a third of it is not ready to carry a client forecast.

**What would let it be turned on.** Re-estimation on O&D rather than terminal traffic, so
hub development and network build are not read as income response; then this measurement
repeated, with the expectation that the clamped share falls well below a third and the
world effect is a fraction of 23%. Owner: John.

---

## 2. Where the 12.2% correction of 8 August came from

**Question.** Three staged data files began reaching the engine at once when the rebound
`DATA` name in `global_demand.py` was fixed. Which one moved the forecast?

**Run.** As above, each input switched in and out at its loader.

| Input | World 2060 | CAGR | Effect |
|---|---|---|---|
| None, as it had been running | 10,983m | 3.64% | |
| Oxford Economics country GDP only | 9,906m | 3.34% | **-9.8%** |
| ACI connecting share only | 10,749m | 3.58% | **-2.1%** |
| Estimated country elasticities only | 10,983m | 3.64% | **0.0%** |
| All three | 9,644m | 3.26% | -12.2% |

**Answer.** Almost all of it is the GDP driver. The engine had been running on seven
regional default growth rates, 1.5% for EU+UK up to 4.0% for Africa, against per-country
Oxford Economics paths with a median real CAGR of 2.19% for 2025-2050. The hand-set
regional figures were the more generous once weighted by where the traffic sits.

The connecting share is not a growth driver. It is the screen that decides whether an
airport keeps its own fitted elasticity. Without it every one of the 111 airports with a
reliable own fit kept theirs; with it, 68 of them are above the 25% connecting threshold
and fall back to the country value. Those 68 are the hubs, and their terminal-panel fits
were measuring hub development.

The country elasticities changed nothing because of the switch in section 1.

---

## 3. What the airports missing from the base are worth

**Question.** Beijing Daxing and Chengdu Tianfu carry no record in
`data/global_airport_meta_2025.json` and therefore none in `global_base_od_2025.json`,
the base the forecast is built on. How much traffic is outside the base, where is it,
and does it explain China being 1.9 points behind Boeing?

**Run.** `scripts/measure_missing_airports.py`, 9 August 2026, against `preagg.duckdb`
`od_p2p` for the base year O&D, the OAG store for country and seats, and
`data/airport_regress.json` for the fits.

**Where they go missing.** Not in the data. `od_p2p` holds 20.4m outbound O&D for PKX
in 2025 and 23.5m for TFU. They are dropped at one line of
`scripts/ingest_global_base.py`, where an origin absent from the Meridian airport to
country reference table is added to `pax_origin_unmapped` and abandoned. The total is
reported, at 3.22% of world outbound O&D. It is not silent, it is aggregated, and 3.22%
reads as acceptable noise. The two largest new airports in China are inside it.

| | 2025 outbound O&D |
|---|---|
| World, `od_p2p` | 3,346.1m across 5,235 origins |
| Absent from the forecast base | 107.7m across 2,002 origins, **3.22%** |
| Of which PKX and TFU | 43.9m, 41% of everything absent |

**Concentrated in one region.** Absent traffic as a share of the base it belongs to:

| Region | In the base | Absent | Absent as % of base |
|---|---|---|---|
| **China** | 491.7m | **60.0m** | **12.2%** |
| South Asia | 172.8m | 6.6m | 3.8% |
| Southeast Asia | 255.9m | 9.3m | 3.6% |
| Africa | 90.9m | 3.2m | 3.5% |
| Latin America | 275.7m | 6.1m | 2.2% |
| Eurasia | 878.5m | 13.8m | 1.6% |
| Middle East | 112.2m | 1.5m | 1.3% |
| Northeast Asia | 214.9m | 1.7m | 0.8% |
| Oceania | 72.7m | 0.3m | 0.4% |
| North America | 574.4m | 1.8m | 0.3% |

Every region except China is inside 4%. China is 12.2% short, and China is where we sit
furthest from Boeing.

**The growth reading is the damage, not the level.** Departing seats, millions, one way,
from the OAG store:

| System | 2015 | 2019 | 2025 | 2019 to 2025 |
|---|---|---|---|---|
| Beijing, all airports | 66.7 | 75.6 | 82.9 | **+9.7%** |
| Beijing, as the base sees it | 63.3 | 70.7 | 50.1 | **-29.2%** |
| Chengdu, all airports | 24.3 | 33.8 | 54.3 | **+60.8%** |
| Chengdu, as the base sees it | 24.3 | 33.8 | 19.9 | **-41.0%** |
| Mexico City, all airports | 30.7 | 38.5 | 39.2 | +1.6% |
| Mexico City, as the base sees it | 30.7 | 38.5 | 34.6 | -10.2% |

A city whose new airport is outside the base reads as a market in steep decline. PEK
carries its own fitted income elasticity of 1.089 estimated over 1994-2024 and CTU 1.5
over 1999-2024, so both windows run through the transfer and read a reallocation
between airports as a fall in demand.

## 3a. What correcting it does, measured

**Question.** Does restoring the missing airports raise China's forecast growth? Two
effects pull opposite ways: the depressed incumbent fits pull growth down and correcting
them pulls it up, while adding traffic to the base raises trips per capita and moves a
country up its propensity curve, which pulls growth down.

**Run.** `scripts/measure_missing_airports_effect.py`, 9 August 2026.
`global_demand.run_global` accepts `base_od` and `airport_meta` as arguments, so both
bases exist only in memory and no file on disk was touched. The control rebuilds the
shipped base from `od_p2p` using only the airport to country pairs the shipped meta
implies, and reproduces it to 0.00007% of world O&D, so what follows measures the
correction and not the rebuild. 1,012 of the 2,281 absent codes resolve to a country
from the OAG store; the rest have no scheduled service and stay out.

| | Shipped | Corrected |
|---|---|---|
| Airports in the base | 3,207 | 4,185 |
| Origin country unmapped | 107.7m | 3.4m |
| Destination region unmapped | 98.7m | 1.3m |
| **World O&D 2025** | **3,140m** | **3,341m, +6.42%** |
| World CAGR 2025-2045 | 3.37% | 3.39% |

| Boeing region | CAGR shipped | CAGR corrected | Change | Base RPK change |
|---|---|---|---|---|
| Eurasia | 1.87% | 1.97% | **+0.10pp** | +3.4% |
| Africa | 4.98% | 5.02% | +0.03pp | +5.7% |
| Northeast Asia | 2.61% | 2.64% | +0.03pp | +2.0% |
| North America | 1.65% | 1.65% | 0.00pp | +0.7% |
| Middle East | 2.62% | 2.61% | -0.01pp | +3.1% |
| Oceania | 2.24% | 2.23% | -0.01pp | +0.8% |
| Southeast Asia | 6.03% | 6.01% | -0.02pp | +7.6% |
| Latin America | 2.82% | 2.79% | -0.03pp | +4.3% |
| South Asia | 8.43% | 8.38% | -0.06pp | +7.2% |
| **China** | **3.34%** | **3.19%** | **-0.16pp** | **+22.8%** |

**Answer, and it is the opposite of the hypothesis.** This is a LEVEL defect, not a
growth defect. The world base year is understated by 6.4% and China's by 22.8%, and
correcting it moves world growth by 0.02 points and China's growth the WRONG WAY, from
3.34% to 3.19%, which widens the gap against Boeing rather than closing it. The
propensity channel dominates: restoring 60m passengers to China raises its trips per
capita and moves it up its own curve. The hypothesis on 9 August was that this was the
first candidate for the China gap. On the base channel it is not.

**What is still not measured, and it is the channel the hypothesis was really about.**
This run leaves `data/airport_regress.json` untouched, so PEK keeps a fitted income
elasticity of 1.089 estimated over 1994-2024 and CTU 1.5 over 1999-2024, both windows
running through a transfer that reads as a collapse in demand. Correcting that means
re-estimating the airport regressions on a combined city system panel, Beijing as
PEK plus PKX plus NAY and Chengdu as CTU plus TFU, and it is the channel that would push
China up. Until it is run, the total effect is unknown and only the sign of the base
channel is established. Owner: John.

**The level finding stands on its own and is larger than the growth one.** A published
world O&D of 3,140m for 2025 is 6.4% below what Sabre `od_p2p` supports once every
airport in it is carried. That figure is on the dashboard, in the OGF deck and in the
comparator table.

**Doing it for real** means adding the missing codes to the Meridian
`airport_city_country.csv`, re-running `scripts/ingest_global_base.py` and
`scripts/scope_global.py`, and re-running the reconciliation and the dashboard build.
That moves the base year and every figure built on it, so it is done deliberately and
once, and ideally in the same pass as the stage length path.

**The code fix that stops it recurring** is separate and smaller. The ingest already
counts the dropped traffic; it should name the largest dropped origins and fail above a
threshold, so an aggregate of 3.22% cannot again hide a 23m passenger airport.

Copyright Avia Solutions Limited. All rights reserved.

---

## 4. The propensity ceiling is inert for a fifth of world traffic

**Question.** Astana comes out of the rebuilt dashboard at 4.76m terminal in 2015 growing
to 80.38m in 2060, 6.48% a year for 45 years, and Ulaanbaatar at 12.23% a year. Neither
is credible. Is the propensity ceiling binding?

**Run.** Read directly, 9 August 2026, after the base rebuild.

**Answer: it cannot bind, because the data it needs is not there.**
`global_demand.country_headroom` returns None when a country has no population and GDP
per capita record, and `data/worldbank_pop_gdppc.json` **holds 30 countries**. Every
other country compounds at its regional GDP growth rate with no saturation applied at
all.

| | Outbound O&D 2025 |
|---|---|
| Countries where the ceiling can bind | 2,607m, **78.0%** |
| Countries where it cannot | 734m, **22.0%** |

The 30 with a record: AE, AU, BR, CH, CN, DE, EG, ES, FR, GB, GR, HK, ID, IE, IN, IT,
JP, MA, MX, NG, NL, NO, PL, PT, SA, SG, TH, TR, US, ZA. The largest without: Russia 64m,
Korea 61m, Vietnam 46m, Canada 41m, Malaysia 39m, Philippines 36m, Colombia 31m, Taiwan
27m.

**A correction to the handover of 9 August**, which named the propensity ceilings of 2.2
trips per capita for Africa and 2.6 for Asia Pacific as the second suspect for the
emerging market gap and said they "bind in the same places". They do not bind in most
places. Where the gap against Boeing is largest the position is mixed: China, India,
Indonesia, Thailand, Brazil, Mexico, Saudi Arabia, Egypt, Nigeria and South Africa all
have a record and are ceilinged; Vietnam, the Philippines, Malaysia, Colombia, Argentina
and Chile do not and are not.

**Direction of the error.** A missing ceiling lets a country grow without saturation, so
it inflates those forecasts rather than depressing them. It therefore cannot explain our
shortfall against Boeing and, on the countries affected, works against it. What it does
explain is a set of individual airport numbers that will not survive a client reading
them: Vietnam at 7.11% a year to 1,217m passengers by 2060, the Philippines at 6.77% to
934m, Astana seventeen times its 2015 self.

**A note on how this was nearly got wrong.** The first read was of the dashboard's own
`cty` payload, where 227 of 231 countries carry a zero population, and that would have
supported a far larger claim. The dashboard payload is not what the engine reads. The
figures above come from `worldbank_pop_gdppc.json`, which is.

**What would fix it.** Extend the World Bank population and GDP per capita ingest to
every country in the base, which is a data pull rather than a method change, then re-run
and measure. Until then no airport-level number in a country outside the 30 should go in
front of a client. Owner: John.

Copyright Avia Solutions Limited. All rights reserved.

---

## 5. What extending the World Bank ingest to every country does

**Question.** Section 4 established that `data/worldbank_pop_gdppc.json` holds 30
countries, so the propensity ceiling cannot bind on 734m of 3,341m outbound O&D. What
does filling it do to the forecast, region by region, and in which direction?

**Run.** `scripts/measure_worldbank_coverage.py`, 9 August 2026, against the World Bank
pull staged at `E:\Avia\Global\data\worldbank_pull_20260809.json`
(SP.POP.TOTL and NY.GDP.PCAP.PP.CD, most recent non-empty observation per country,
population 2025 and GDP per capita PPP 2025 for 182 of 199). `global_demand._load` is
redirected for the World Bank file alone, so every case runs on the same base, the same
meta and the same assumptions book and only the country record differs. Nothing was
written to a shipped file.

Three cases. SHIPPED, the 30 as they ship. COVERAGE, those same 30 records untouched plus
every further country the pull can fill, which isolates coverage because no existing
number moves. REFRESHED, every country taken from the new pull at one vintage.

| | Countries | Base countries covered | O&D the ceiling can bind on |
|---|---|---|---|
| Shipped | 30 | 30 | 2,607m, 78.0% |
| Coverage | 199 | 199 | 3,306m, 98.9% |

**The vintage is not the story.** COVERAGE and REFRESHED differ by 0.01pp on the world
CAGR, so moving the 30 existing records to the current observation at the same time costs
nothing and the file can be rebuilt whole.

**World O&D departing passengers, Baseline, full horizon:**

| | 2025 | 2050 | 2060 | CAGR 2025-2060 |
|---|---|---|---|---|
| Shipped | 3,341m | 7,582m | 10,278m | 3.26% |
| Coverage | 3,341m | 7,020m | 9,125m | **2.91%** |

**By Boeing region, RPK CAGR 2025-2045 on the fixed stage lengths.** Read the change and
not the level: this runs the demand model directly over its own window while the
published figures come off the dashboard over 2024-2044.

| Region | Shipped | Coverage | Change |
|---|---|---|---|
| Southeast Asia | 6.01% | 4.97% | **-1.04pp** |
| Northeast Asia | 2.64% | 1.85% | **-0.79pp** |
| Oceania | 2.23% | 1.66% | -0.57pp |
| Middle East | 2.61% | 2.10% | -0.51pp |
| Latin America | 2.79% | 2.43% | -0.36pp |
| Eurasia | 1.97% | 1.65% | -0.32pp |
| Africa | 5.02% | 4.88% | -0.14pp |
| North America | 1.65% | 1.60% | -0.05pp |
| South Asia | 8.38% | 8.34% | -0.04pp |
| China | 3.19% | 3.16% | -0.03pp |
| **World** | **3.48%** | **3.16%** | **-0.32pp** |

**The direction is as expected and the size is larger than expected.** A third of a point
off the world growth rate, and it widens the gap against Boeing rather than closing it.
It does almost nothing where the gap is largest: China moves 0.03 points and South Asia
0.04, because both already carried a record. What it moves is Southeast Asia and
Northeast Asia, and Southeast Asia was already 1.4 points behind Boeing.

**Two channels move, not one.** The record sets the propensity ceiling and it also sets
maturity in `global_demand._maturity`, where a country without one takes its region's
default. **39 countries carrying 284m outbound O&D flip from emerging to mature**, Russia,
Korea, Malaysia, Argentina, Chile, Kazakhstan and New Zealand among them, so they move to
the lower mature elasticity as well as acquiring a ceiling. Both channels pull the same
way here, which is why the effect is as large as it is.

**The airport numbers that prompted this.** Astana went from 3.18m base O&D to 32.63m in
2060, ten times its base, and comes out at 9.61m. Ulaanbaatar goes from 8.75m to 6.15m.
Vietnam's country total halves, 544m to 276m by 2060, and the Philippines 390m to 242m.
Seoul Incheon 158.83m to 61.54m and Kuala Lumpur 127.01m to 41.74m.

**It does not fix everything it was supposed to fix.** Hanoi still reaches 104.98m
departing O&D in 2060 from a 12.20m base, 6.3% a year for 35 years, which is not a number
to put in front of a client either. The remaining driver there is the Oxford Economics
GDP path and the applied elasticity, not the ceiling.

**A distortion the wider coverage exposes, and it is bounded.** The model compares a
country's departing O&D against its resident population, so a tourism economy counts
visitors as residents' trips. Ten countries carrying 51.4m, 1.5% of world O&D, start at
or above their regional ceiling on that measure: Aruba at 9.98 trips per capita against a
3.5 ceiling, Malta 7.70 against 3.2, Iceland 6.37, Macau 4.54, Cyprus 5.45, the Maldives
4.36, French Polynesia, the Bahamas, Singapore and Belize. Each is pinned to the 0.7%
mature floor for the whole horizon. It is a real defect and it is 1.5% of the world, so
it is a note against the ingest rather than a reason to hold it.

**A consequence for a parameter, not a data question.**
`propensity.income_elasticity_tpc` is 1.30 and the book records it as the fitted world
curve slope from 30 countries. The same pull that fills the ceiling makes that curve
re-fittable on 199. Until it is re-fitted, a parameter estimated on 30 countries is being
applied to 199. Owner: John.

**Still uncovered after the pull: 30 countries, 35.4m, 1.1% of world O&D.** Taiwan is
27.0m of it and the World Bank does not publish it. The rest are French overseas
departments and territories the World Bank reports inside their sovereign, Cuba, and
small Pacific and Caribbean islands. Naming them is deliberate: an aggregate of 1.1% is
exactly the shape of the 3.22% that hid Beijing Daxing.

## 6. Candidate stage length paths for the RPK conversion

**Question.** A flat extrapolation of the measured 2015-2025 stage length growth closes
two thirds of the world gap against Boeing but over-corrects Oceania and Northeast Asia.
What path should replace it?

**Run.** `scripts/stage_length_path.py`, 9 August 2026, reading the measured stage length
by Boeing region from `fleet_wedge.json` and the reconciliation from `regions_boeing.json`.
The flat case reproduces `gap_decomposition.py` exactly, which is the control.

**The decay is measured, not chosen.** World stage length growth was 0.75% a year over
2015-2019 and 0.52% over 2019-2025, five years apart on the window midpoints. One
exponential through both is a half-life of 9.6 years. That is the rate at which the
measured deceleration is running, and both stated paths use it.

| Path | World applied rate | World km per seat 2044 | World gap after |
|---|---|---|---|
| Flat, the measured rate held | 0.61% | 2,121 | -0.2pp |
| Decay to zero, half-life 9.6 years | 0.23% | 1,974 | -0.6pp |
| Converge on a common 0.31%, half-life 9.6 years | 0.38% | 2,031 | -0.5pp |

Oceania is the test the flat path fails: 1.26% a year held for twenty years puts an
average Oceania sector at 3,390 km by 2044 and turns a 0.7 point deficit into a 0.6 point
surplus. The decay path applies 0.48% and lands at 2,714 km, and the converge path 0.63%
and 2,792 km. The km per seat column is the claim each path makes about network shape and
is the number a client will query.

Owner: John. The path needs signing off before it goes into the conversion.

## 7. How far people fly, over the longest history we hold

**Question.** Section 6 offered three stage length paths and each was a shape somebody
chose. Is there a relationship in the history that can carry the path instead?

**Run.** `scripts/journey_length_history.py`, 9 August 2026. Sabre `od_p2p` passengers by
year from `C:\Avia\preagg.duckdb`, great circle distance from the airport coordinates in
`E:\Avia\Global\data\airports.csv`, origin country from the Meridian reference table,
real GDP per head from the Oxford Economics country file. Ten usable years, 2013-2019 and
2023-2025; 2020 is absent from the store and 2021 and 2022 are excluded, the same policy
the OAG store carries and, separately, because the Sabre 2021 slice reports more
passengers than 2022.

**Guards first.** Both endpoints located for 98.1% to 99.8% of passengers in every year.
18,055 O&D pairs are present in all ten years and carry 83.1% to 91.5% of located
passengers, so the series is shown on all pairs and on that fixed panel and the two move
together. A first version of the region table dropped Eurasia entirely, because the Boeing
scheme's default region IS Eurasia and the code excluded the default as though it were an
unassigned bucket. It read as a data gap and was neither.

**World average journey length rose from 1,519 km in 2013 to 1,651 km in 2025**, 0.70% a
year on all pairs and 0.63% on the fixed panel. The OAG flown stage length over 2015-2025
is 0.61% a year against 0.83% for Sabre O&D over the same window, a 0.21pp difference
between two different measures of distance from two different sources.

**The trend, estimated rather than read off two endpoints.** An endpoint CAGR throws away
eight of the ten observations. Regressing ln(journey length) on a year term with a region
fixed effect uses all of them and gives a standard error:

| Region | Trend 2013-2025 | se | Shrunk | 2013-2019 only |
|---|---|---|---|---|
| Latin America | 1.44% | 0.19 | 1.30% | 1.97% |
| Oceania | 1.19% | 0.19 | 1.10% | 2.06% |
| Southeast Asia | 1.03% | 0.19 | 0.97% | 0.55% |
| Northeast Asia | 0.89% | 0.19 | 0.86% | 2.26% |
| Eurasia | 0.71% | 0.19 | 0.71% | 0.22% |
| Middle East | 0.65% | 0.19 | 0.66% | 0.46% |
| China | 0.64% | 0.19 | 0.66% | 1.10% |
| Africa | 0.33% | 0.19 | 0.40% | -0.34% |
| North America | 0.17% | 0.19 | 0.27% | 0.78% |
| South Asia | 0.04% | 0.19 | 0.16% | -1.16% |
| **Common** | **0.71%** | **0.07** | | |

**One rate for every region is rejected**, F(8,72) = 5.65, p below 0.0001, so the regional
differences are real on this window. **They are not stable across sub-windows**: South Asia
is -1.16% before 2019 and 0.04% on the full window, Northeast Asia 2.26% and 0.89%. That
instability is why each region's estimate is pulled towards the common rate in proportion
to its precision, at a weight of 0.83 read from the spread of the estimates against their
own standard error rather than chosen.

**The income relationship is not identified, and that is the honest answer.** Regressing
ln(journey length) on ln(real GDP per head) with region fixed effects gives an elasticity
of 0.158 with an R2 of 0.156. Add a common year term and the income coefficient turns
NEGATIVE, -0.105, while the year term takes 0.90% a year and the R2 rises to 0.386. Over
2013-2019 alone the same thing happens more sharply, -0.207 against a 1.29% trend. Income
and time are collinear across ten years in which every region got richer, so a panel this
short cannot separate an income effect from everything else that lengthened a journey:
longer range narrowbodies, low cost long haul and route liberalisation. An income-driven
stage length path would therefore be a number with a story attached rather than a measured
relationship, and it is not proposed.

**What is proposed is the estimated regional trend, shrunk, held over the window.** It is
measured on the longest series we hold, on every observation rather than two, with a
standard error against it and a stated shrinkage, and it is cross-checked against an
independent OAG measurement of a different distance. Applied, the world gap against the
2025 Boeing CMO closes from -0.9pp to -0.1pp before the World Bank change and to -0.5pp
after it. Owner: John.

## 8. The three channels behind the China gap, sized

**Question.** China is our largest gap against Boeing. Section 3a ruled out the base
channel and section 5 showed the World Bank ingest moves China by 0.03 points. What is
left, and how large is each piece?

**Run.** Read directly from `data/airport_regress.json`, the ACI calibration and the
assumptions book on 9 August 2026, with `global_demand.run_global` used in memory for the
elasticity test. Nothing was written.

**Channel one, and it is the largest: half of China runs on no airport fit at all.**
China's base is 583.3m outbound O&D across 263 airports.

| | Airports | O&D | Share |
|---|---|---|---|
| Own fitted elasticity applied | 15 | 210.6m | 36.1% |
| Fit exists but is not reliable, falls back to the country value | 17 | 78.7m | 13.5% |
| No fit at all, runs on the country value | 231 | 294.0m | **50.4%** |

**And the country value for China is the MATURE one.** China's GDP per head is 29,333
international dollars against a maturity threshold of 25,000, so half of China's traffic
carries a domestic income elasticity of 1.0 rather than the emerging 1.5. China sits near
0.4 trips per capita. It is a mature market on the income measure and on no other.

| | World 2060 | World CAGR 2025-2060 | China CAGR 2025-2060 |
|---|---|---|---|
| As applied | 9,050m | 2.89% | 2.66% |
| China classed emerging | 9,398m | 3.00% | **3.29%** |
| Threshold raised to 35,000, 18 countries move | 9,486m | 3.03% | 3.29% |

**0.63 points on China from one threshold.** The threshold is a cliff at 25,000 and China,
Mexico at 25,868 and Thailand at 26,250 all sit just the wrong side of it while Brazil at
23,433 and Indonesia at 17,660 sit the right side. A binary switch on income deciding
whether a country's domestic elasticity is 1.0 or 1.5 is a judgement, not a measurement,
and the model already computes a continuous behavioural measure of maturity in the
propensity saturation.

**Channel two, the city system panels, is smaller than it looked.** PEK carries a fit of
1.089 over 1994-2024 that is already marked NOT reliable, so Beijing falls back to the
country value today and a combined Beijing panel changes nothing unless it makes the fit
reliable. CTU carries 1.5 over 1999-2024 and IS applied, on 14.0m of O&D, 2.4% of China.
PKX, TFU and NAY carry no fit. The whole city system channel is worth 14.0m of applied
elasticity today against 294.0m running on the country default.

**Channel three, Beijing Daxing in the terminal model, is a level defect and now has a
sourced record.** ACI does not publish Daxing: `aci_monthly` in the ACI store, from
"MONTH_ACI Monthly Time Series(NO).xlsx" modified 8 April 2026, returns no PKX row and no
airport whose name contains Daxing. It is not filed under another code.

The ACI calibration file's `od_both_ends_2024` column is not ACI at all: it reproduces
Sabre `od_p2p` exactly, ratio 1.000 for TFU, CTU, PEK, PVG, CAN and SZX. So the only
genuinely ACI-sourced fields are terminal, movements and the domestic and international
split. Sabre holds PKX at **42.45m O&D at both ends in 2024**, 39.74m of it domestic.
Published Chinese airport throughput for 2024 puts Daxing at 49.42m, and the same source
gives PVG 76.79m, CAN 76.34m, PEK 67.36m and SZX 61.46m against the ACI file's 76.76m,
76.37m, 67.36m and 61.48m, agreeing to within 0.05%. Terminal 49.42m less O&D 42.45m
gives a connecting share of **0.141**, which lands on Tianfu's 0.1413. The record is
coherent from three directions. Movements and the terminal-side domestic and
international split still need the OAG store and a workstation run.

Owner: John, on all three.

## 9. The city system re-estimation, and why it is not applied

**Question.** PEK carries a fitted elasticity of 1.089 over 1994-2024 and CTU 1.5 over
1999-2024, both windows running through the opening of a second airport that took traffic
off them. Does re-estimating on the city system, Beijing as PEK plus PKX plus NAY and
Chengdu as CTU plus TFU, raise China?

**Run.** `scripts/measure_city_system_fits.py`, 9 August 2026. Sabre `od_p2p` outbound,
2013-2019 and 2023-2025, flows between the airports of a system excluded, against Oxford
Economics country GDP, through `estimate/od_reest.estimate_od_bG`, which is the restricted
covid-dummy fit the assumptions book already carries.

**It has to run on O&D and not on the ACI panel.** ACI does not publish Beijing Daxing at
all, checked by code and by airport name against the ACI monthly store, so a Beijing system
panel cannot be built from ACI at any window. Estimating on O&D is separately what the book
has carried as a [P1] since July.

| City | Incumbent alone | System | Shipped, ACI terminal |
|---|---|---|---|
| Chengdu | 0.027, R2 0.19, t 0.02, clamps to 0.6 | **1.319, R2 0.995, t 13.60, reliable** | 1.500, reliable |
| Beijing | -0.447, R2 0.62, t -0.58 | 0.246, R2 0.91, t 2.05, clamps to 0.6 | 1.089, not reliable |
| Shanghai, two airports, no transfer | 0.530 | 0.331 | 2.224, not reliable |
| Guangzhou, one airport | 0.395 | identical by construction | 1.143, reliable |

**The transfer defect is real and the hypothesis is still wrong.** Chengdu's incumbent
alone returns 0.027, which is not a number, and the system returns 1.319 with an R2 of
0.995. Against the Shanghai control at -0.199, the +1.292 is the transfer and not the
method. But the SHIPPED Chengdu fit of 1.5 is HIGHER than the system fit, so applying the
re-estimation would lower Chengdu rather than raise it, and Beijing's system fit clamps to
0.6, below the elasticity it effectively runs on now.

**Beijing's low elasticity is capacity, not income.** Beijing's outbound O&D went 40.2m in
2013 to 46.1m in 2025, 1.1% a year, against GDP per head at 5% to 6%. That is a slot-capped
airport and a GDP regression cannot tell a capacity constraint from a weak income response.
Applying the fit would write the constraint into a demand elasticity. `od_reest.py` records
the same trap at Manchester in the other direction, where capacity-led growth inflated the
elasticity.

**Not applied.** The measurement stands as the answer to the question rather than as a
change. Owner: John.

**What shipped instead.** `global_drivers.maturity_basis` moves to `saturation`, so a
country's elasticity interpolates on how far up its own propensity curve it already sits
rather than jumping at 25,000 international dollars per head. World O&D CAGR 2025-2060
goes 2.89% to 3.05%, China 2.61% to 3.13%. The open objection is recorded in the book: the
same saturation drives the propensity headroom, so maturity is now monotone in it twice and
the combined effect has not been measured.

**Where the forecast stands after all of it.** World O&D 3,341.3m in 2025 to 7,331.5m in
2050, a compound 3.19%. World RPK 2024-2044 of 3.80% against the Boeing 2025 CMO at 4.2%,
a gap of -0.4pp, and 3.15% on the constant stage length basis the conversion used before
today. China closes from -2.0pp to -1.0pp, Oceania to -0.0pp, Latin America to -0.4pp,
Eurasia to -0.3pp and North America to -0.3pp. Against the editions a client will hold this
autumn, Boeing CMO 2026 at 4.0% and Airbus GMF 2026 at 3.9%, we sit 0.2 and 0.1 points
behind.

## 10. Beijing Daxing is in ACI. The absence was ours, and it was not only Daxing

**Question.** Section 8 recorded that ACI does not publish Beijing Daxing. Why not?

**Answer: they do, and the finding in section 8 was wrong.** The ACI ANNUAL dataset, which
is what the hub calibration and the airport panel are built from, carries Beijing Daxing
International Airport at **49,441,029 passengers and 325,246 movements for 2024**. Section 8
checked the ACI MONTHLY store, which has no PKX row, and the monthly store is not the file
the code reads. That is the same error as the propensity work on 9 August, which was nearly
published off the dashboard payload rather than the file the engine opens, and it was not
learned the first time.

**Where it was lost.** `scripts/ingest_aci.py` required the "Passenger Terminal" column and
skipped any row where it was blank. ACI leaves that column blank for a large minority of
airports and fills "Passengers" instead. The skip is one `continue`.

| Year | Airports kept | Dropped for a blank terminal cell | Traffic dropped |
|---|---|---|---|
| 2019 | 2,301 | 201 | 490.3m |
| 2023 | 2,445 | 221 | 496.5m |
| **2024** | **2,557** | **189** | **544.0m** |

Every year from 2013 loses between 174 and 221 airports. The 2024 list is led by Beijing
Daxing at 49.44m, Changsha 31.22m, Zhengzhou 28.51m, Urumqi 27.77m, Harbin 23.80m, Guiyang
22.31m, Jinan 20.01m and Dalian 19.29m. It is overwhelmingly Chinese, which is the third
time in two days that a data defect has landed on the region we sit furthest from Boeing in.

**The fallback is not the passengers column on its own.** Passengers includes direct transit
and terminal does not. On the 2,557 airports of the 2024 dataset that carry both, terminal =
passengers less direct transit holds exactly, 2,557 times out of 2,557, while terminal =
passengers holds only 1,709 times and would overstate Los Angeles by 2.3m. None of the 189
blank-terminal rows carries a direct transit figure, so for them the two are the same number,
but the identity is what is applied.

**The calibration had no builder, which is why this survived.**
`aci_hub_calibration_2024.json` anchors the entire terminal forecast and nothing in the tree
produced it. `scripts/build_aci_hub_calibration.py` now does, and it reproduces the shipped
file exactly before it is allowed to write: 2,430 airports, same set, zero difference on
every terminal and O&D field. The screen it had to reproduce is presence of traffic and not a
size floor, read off the shipped file rather than assumed; the smallest airport in production
carries 2 passengers.

**Measured before it was applied**, with both calibrations in memory:

| | Airports | Base terminal | 2050 | World terminal CAGR |
|---|---|---|---|---|
| Shipped | 2,431 | 8,946m | 19,084m | 2.95% |
| Corrected | 2,614 | 9,412m | 20,193m | 2.96% |

**A level defect and not a growth defect, for the third time today.** The base rises 5.2% and
the world growth rate moves 0.01 points. China gains 0.07pp and no other region moves more
than 0.03pp. Re-estimating the airport regressions on the corrected panel takes the airports
with a fit from 1,624 to 1,780 and China's own-fit coverage from 36.1% to 37.2% of its O&D,
one airport, Changchun. Beijing Daxing and Chengdu Tianfu still carry no fit, correctly:
their history is too short.

**The admission rule stays and its only entry is gone.** `config/terminal_admissions.yaml`
now has an empty list and records why. Rule 2 names the file to check, because the reason
Daxing was admitted at all was that the wrong file was checked.

## 11. What is behind each regional difference, and it is one difference

**Question.** Our regional growth rates differ from Boeing's by more than a point in several
places. Are we choosing different winners and losers?

**Run.** `scripts/regional_defence.py`, 10 August 2026. Every regional rate decomposed into
the inputs it was built from: the Oxford Economics income and population paths, the position
on the propensity curve, the elasticity actually applied to that region's traffic on the
engine's own rules, and the stage length carried into the conversion.

**No. The ranking is broadly the same and the level of income response is not.** Boeing's
implied elasticity to regional real GDP is higher than ours in nine regions out of ten:

| Region | Avia implied | Boeing implied | Gap |
|---|---|---|---|
| Northeast Asia | 2.55 | 4.49 | 1.94 |
| Middle East | 0.96 | 2.08 | 1.13 |
| Latin America | 1.20 | 2.19 | 0.99 |
| Eurasia | 1.09 | 1.88 | 0.79 |
| Southeast Asia | 1.11 | 1.86 | 0.75 |
| China | 0.99 | 1.67 | 0.68 |
| North America | 0.88 | 1.48 | 0.60 |
| Africa | 1.75 | 2.33 | 0.57 |
| Oceania | 0.77 | 1.33 | 0.56 |
| South Asia | 1.41 | 1.38 | -0.03 |

That is one systematic difference and not ten regional disagreements, and it has two possible
causes that cannot be separated from what we hold: Boeing assume more GDP than Oxford
Economics, or a stronger response to it. Our world real GDP is 2.21% a year for 2025-2044.
Boeing's GDP assumption is in the CMO workbook and is the next thing to read off it.

**Northeast Asia is the one to look at first.** Oxford Economics give the region 0.5% real
GDP growth a year, against a falling population, and Boeing's 2.4% RPK implies traffic
growing four and a half times the economy for twenty years. That is a position to put to
them, not one to concede.

**The forecast is running on country defaults, not on airport fits.** The share of each
region's traffic carrying an airport's own fitted elasticity: South Asia 44%, China 37%,
Northeast Asia 13%, Middle East 11%, Southeast Asia 8%, Eurasia 5%, North America 4%, Africa
2%, Latin America 1%, Oceania 0%. Our regional differences come from the income paths and
the saturation positions, not from airport-specific estimates.

**Against the other houses, and Boeing is not the closest on drivers.**

| Comparator | Basis | Their rate | Avia | Difference |
|---|---|---|---|---|
| Boeing CMO 2026, 2025-2045 | RPK | 4.0% | 3.8% | -0.2pp |
| Boeing CMO 2025, 2024-2044 | RPK | 4.2% | 3.8% | -0.4pp |
| Airbus GMF 2026, 2026-2045 | RPK | 3.9% | 3.8% | -0.1pp |
| Airbus GMF 2025, 2025-2044 | RPK | 3.6% | 3.8% | **+0.2pp** |
| IATA, 2024-2044 | RPK | 3.6% | 3.8% | **+0.2pp** |
| ACI WATF, 2024-2043 | terminal pax | 3.4% | 3.06% | not like for like |

IATA is produced with Oxford Economics, the same GDP source we use, and we sit 0.2 points
ABOVE it. We are inside the range the industry publishes and at the top of the half of it
that shares our drivers. That is the answer to whether the position is defensible.

## 12. What else is stale or unproduced

**Run.** `scripts/check_freshness.py`, 10 August 2026, which compares every published and
staged file against what it is built from and names anything with no builder at all.

**One file the engine reads has no builder.** `oag_final_to_next_M.json`, the per-airport
destination-region seat shares, dated 6 July 2026. Coverage is good, 2,342 of 2,614 airports,
and the 272 without a row carry 15m of terminal traffic, 0.2%, whose connecting element grows
on the world international index instead of its own mix. Low impact and the same class of
defect as the calibration: a file nothing produces cannot be rebuilt when its inputs move.

**Two files older than an input.** `bum_candidates.json` from 29 July, a diagnostic that does
not reach the deck. `estimated_bG_by_country.json` from 6 July, which is older than the panel
it is estimated from; the switch that would apply it is off, so nothing published depends on
it, and MEASUREMENTS section 1 already says it should not be turned on until it is
re-estimated on O&D.

**Everything else in the served bundle was rebuilt today** and now agrees: dashboard, cockpit,
world, airports, meta and capacity all carry 2,614 airports and a world terminal base of
9,412m.

## 13. The three open items, closed, and what the third one was hiding

**1. The destination mix file now has a builder.**
`scripts/build_oag_final_to_next_M.py`, on the same basis as every other read of the OAG
store in this tree: service type J, departures only, one preferred tiling per region and
year, each airport read from its home region file. The control is a comparison and not an
equality, because the shipped file was built from an earlier store on an unrecorded basis:
median mix difference 0.000 and 84% of the 3,774 airports in both files within 0.05, which
says the method matches. Applied on the 2025 schedule the world 2050 terminal moves 20,193m
to 20,215m, 0.1%, and the CAGR does not move. 280 of the 2,614 calibration airports carry
no mix row and grow their connecting traffic on the world international rate instead of
their own; they carry 11.2m of terminal traffic, 0.12%, led by Chisinau at 4.14m and Adana
at 3.09m, both airports whose traffic has moved to a new field. `run_terminal` now reports
that count and its traffic rather than leaving it silent.

**2. The country elasticities are current and the verdict does not change.**
Re-estimated on the corrected panel: 163 countries, 137 reliable, median 1.70 to 1.67, and
still **45 of 137, a third, at or beyond the applied bound of 2.2**. Section 1 said leave
`use_estimated_elasticities` off until the fits are re-estimated on O&D rather than terminal
traffic, and nothing here changes that. China moves 1.72 to 1.93.

**3. The BUM candidates could not be rebuilt at all, and the reason took four defects.**
`bum_candidates.json` was dated 29 July. Re-running it revealed, in order:

  a. `_bt2_pending` was never initialised. Every candidate raised a NameError on the append
     INSIDE the try, was caught by a bare except and recorded as "qsi share failed", and the
     script then died on the same name outside the try. **The file on disk was produced by a
     version of the script that no longer exists and could not be regenerated.**
  b. `airportsdata` was absent from requirements.txt. Meridian's `load_airport_coords`
     returns an EMPTY dictionary without it, so `pair_metrics` raised "gcd unsourceable" for
     every route, and separately the circuity filter in `_components` was running with no
     coordinates and passing everything, silently.
  c. `scikit-learn` was absent from requirements.txt, so the pickled BT2 model could not be
     loaded on a machine installed from it. The pickle records the version it was trained
     with, 1.7.2, and that is now the pin.
  d. A candidate with no measured same-country market is `log(0)`, which took the whole
     build down with a bare "math domain error".

With all four repaired the BT2 path ran for the first time, and **the first run is why it is
now switched off by default.** It puts Southampton to Heathrow at 41.8k passengers against a
measured market of 0.1k, and Southampton to Paris at 41.4k against 3.3k, and returns tier B
rather than a refusal. The model is being extrapolated far below the markets it was trained
on. It needs a stated minimum market, read off the training cohort rather than chosen, before
its output goes anywhere. `--bt2` scores anyway; the default writes the QSI share, which is
real and correct on all 136 routes, and says on each row why the model was not applied.

**The error message was pointing at the wrong thing for two weeks.** Every row said "qsi
share failed" while carrying a working QSI share, because one bare except covered the QSI
call and everything after it. It now names which stage failed and carries the message.

**A question for John, not a change.** The model card in `bt2_model_v1_2.pkl` describes the
88.8% as "fitted (light-reg)" against a blind leave-one-carrier-out result of 53.7% on the
Sabre basis and 50.1% for US routes against DOT. The claim-language ruling of 5 August,
CHANGELOG entry 90, publishes 89% within plus or minus 20% as the calibrated figure and keeps
the single-route blind numbers internal. Whether "calibrated" and "fitted" are the same thing
is the track record question that has been carried forward twice, and it is now sitting on a
client-facing string. The string has been left exactly as ruled and the point is recorded
here. Owner: John.

Copyright Avia Solutions Limited. All rights reserved.

---

## 14. What the connecting-split disagreement is worth

**Question.** The publication watchpoint flags 314 airports where the Sabre leg-measured
and ACI-residual connecting shares disagree by more than 30 points, 10.9% of world
terminal traffic. The band was raised to 12% on 23 August 2026 as a recorded interim.
How much does the disagreement actually move published totals?

**Run.** `scripts/measure_connecting_divergence.py`, 23 August 2026, on the tree at
commit 5d6d627. The terminal forecast run three times in memory with
`connecting_share_method` forced to blend, sabre and residual; nothing written.

| Method | World 2060 terminal | CAGR |
|---|---|---|
| Blend (shipped) | 26,142m | 2.962% |
| Sabre leg-measured | 25,909m | 2.935% |
| ACI residual | 26,725m | 3.027% |

**The bound: 816m at 2060, 3.12% of the blended figure, 0.09pp on the CAGR**, and it is
a bound on the method choice across every airport with both sources, so the flagged set
alone contributes less. The terminal LEVEL is ACI-anchored under all three; what moves
is the split between the O&D-driven and connecting-driven growth paths. The band note in
the assumptions book stands with this measurement written beside it.

**The finding that was not the question.** The largest absolute spreads are at hubs
BELOW the 30-point flag threshold: BLR 101m on a blended 843m, DEL 67m on 601m, SVO 26m
on 88m (30% of its own level), SIN 28m on 123m. The flag is keyed on share disagreement,
which catches small leisure airports and misses the airports where the split matters
most in absolute terms. The improvement is a second caveat dimension keyed on absolute
2060 spread, not a tighter band. Owner: John, on return; candidate for Jess to size.

Copyright Avia Solutions Limited. All rights reserved.

---

## 15. The maturity architecture, tested and settled for now

**Question.** John asked on 23 August 2026 whether the whole maturity architecture,
the mature/emerging elasticity split, its basis and its level, could be settled on
data in one pass before the testing period. Three measurements, in the order run.

**Case C in production, and its reversal.** `maturity_basis: headroom_only` (the
split dropped, every country on the emerging elasticity) was adopted, verified at
world O&D CAGR 2025-2060 of 3.16% exactly as measured, and reversed the same evening:
on the comparison basis it put world RPK 2024-2044 at 4.0%, equal to the Boeing CMO
2026, 0.1pp above the Airbus GMF 2026 and 0.4pp above IATA on shared drivers, past
the band MEASUREMENTS 11 defends. The move was +0.2pp on the near window against
+0.11pp on the long horizon, single-cause (this session's two compare runs differ in
nothing else), and larger near-term because case C silently set the single elasticity
at the emerging value, the top of the old range.

**The discriminator, tested four ways, supported by none.** Fitted country
elasticities regressed on income gave R2 0.057 (CHANGELOG 119, terminal fits); on
saturation position, slope +0.058, t 0.40, R2 0.001 (this session, terminal fits,
n=134, and the tertile medians RISE with saturation: 1.35 / 1.99 / 1.84); and on the
clean O&D-based fits below, income t +1.40 and saturation t +1.19. Nothing we hold
says the income elasticity falls as markets mature. The split is a stated judgement.

**The O&D re-estimation, the [P1] open since July, run at last.**
`scripts/estimate_country_bG_od.py`: Sabre od_p2p outbound by origin country
(unmapped 0.16%, from 3.22% before the reference supplement), OEF GDP, the restricted
covid-dummy fit, ten usable years. 195 countries fitted, 42 reliable, and the
reliable set is CLEAN: median 1.672, ZERO at either applied bound, against 45 of 137
(33%) clamped in the terminal-based set. The contamination diagnosis of MEASUREMENTS
1 is confirmed from the other side. But the instrument is underpowered for
level-setting: ten observations with a covid dummy fail the heavyweights (China 0.79,
Japan 3.95, Italy 5.05, Mexico 4.47, the short-window trap of the 7 July review), and
the reliable 42 skew to small markets, so their traffic-weighted 1.794 is a selected
level that would over-impose emerging response on mature markets.

**The settlement.** The split stays, recorded as tested-and-unreplaced rather than
assumed: no discriminator is supported, and no evidenced replacement level exists.
External coherence holds the configuration (world 3.8%, IATA +0.2 on shared drivers,
behind both OEMs). The candidate file `data/estimated_bG_by_country_od.json` is the
starting point for the instrument that can settle it: a pooled panel fit with country
effects over the O&D window, or the affordability-conditioned estimation once the
fare levels of `data/fare_levels_exhibit.json` join the income paths. September, and
it should be one weighing with the propensity slope re-fit (candidate 1.422).
Owner: John.

Copyright Avia Solutions Limited. All rights reserved.

---

## 16. The architecture completed: the pooled panel fit and package B

**Question.** John asked on 23 August 2026 that Block 2 finish before his leave, so
Jess reviews a complete methodology. MEASUREMENTS 15 had settled the architecture
provisionally for want of a powered instrument; this section records the instrument,
its results, and the decision.

**The instrument.** `scripts/estimate_pooled_panel.py`: every country's O&D history
in one regression, ln(pax) on ln(GDP) with country fixed effects and a post-covid
dummy, 1,890 country-years across 189 countries. Validated on synthetic panels
before touching data: recovers a true 1.8/1.1 split at t 35, finds nothing on a true
single slope. Decision rules stated in the script header before any result.

**Results.** Pooled bG 1.544 (se 0.089, t 17.3); covid level shift -14.4%;
traffic-weighted sensitivity 1.161 (se 0.142). The split test, with power at last:
emerging 1.508, mature 1.948, difference not significant (t -1.74) and in the WRONG
order, the fifth and final failure of the split's discriminator. The fare term,
world real fare from `data/fare_levels_exhibit.json` as a within-country covariate:
-0.292 (se 0.099, t -2.95), significant with the sane sign, against the stated
expectation of weak identification. The 2018 fare kink has a single source file per
year, so vintage and market cannot be separated; 2018 stays flagged.

**The package, measured** (`scripts/measure_architecture_package.py`, four cases in
memory): shipped A gives world 2060 9,565m, CAGR 3.05%; package B (single bG at the
pooled 1.544 with segment relativities preserved, slope 1.422, bF re-anchored to
-0.292) gives 9,252m, 2.95%, China 3.08%, comparison position circa 3.7% RPK
(-0.3 Boeing CMO26, -0.2 Airbus GMF26, +0.1 IATA); the traffic-weighted alternative
C gives 2.47% and falls below the whole published range.

**Decision: package B applied (John, 23 August 2026).** The split is retired after
five failed tests; every bG and bF in the book now traces to a named regression; the
propensity slope applies at its re-fitted value. The unweighted pooled level was
chosen over the traffic-weighted on the pre-stated ground that it is the
better-identified structural parameter (the weighted estimate has 60% more error
and is dominated by the two largest country series); the resulting band position is
reported, not selected for. Reversal is one book block. What the panel still cannot
do, and September can: separate the fare term from other common year shocks with a
longer window, and give the heavyweights reliable own fits.

Copyright Avia Solutions Limited. All rights reserved.

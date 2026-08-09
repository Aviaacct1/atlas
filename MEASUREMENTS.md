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

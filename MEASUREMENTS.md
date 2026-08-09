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

Copyright Avia Solutions Limited. All rights reserved.

# The Observatory OGF deck: slide inventory against Boeing's Market Overview

Version 1.0, 9 August 2026. Avia Solutions. Working document.

Source deck: "Market Overview 2025, European Consultant Conference", Boeing, March 2025,
28 pages, Wendy Sowers. Held in the project folder; the fuller CMO decks and the
forecast-on-a-page workbooks are on Egnyte at `02 Knowledge / 2 Industry Reports /
d International Industry Bodies / Boeing / Boeing Current Market Outlook`.

Purpose. Build the same deck on Avia data and assumptions, as The Observatory would
present it. Two things come out of that. A deck the team and third parties can use to
understand and challenge the forecast. And, from every slide we cannot fill, a list of
where the forecast is thinner than the people we are being compared with.

The test is deliberately unforgiving: a slide we cannot publish is a gap, not a
formatting problem.

---

## Verdict at a glance

| Section | Slides | Can produce | Partial | Cannot |
|---|---|---|---|---|
| 1. Passenger air travel demand | 9 | 3 | 3 | 3 |
| 2. Air cargo demand | 4 | 0 | 1 | 3 |
| 3. Airline trends | 4 | 2 | 1 | 1 |
| 4. Fleet dynamics | 5 | 1 | 2 | 2 |
| **Total** | **22 content slides** | **6** | **7** | **9** |

Six of 22 outright. That is the honest starting position and it is the point of the
exercise.

---

## 1. Passenger air travel demand

| p | Boeing slide | Avia | What it needs |
|---|---|---|---|
| 3 | Leisure travel spending as a share of consumer spending, world, China, EU, US | **Cannot** | Tourism Economics consumer spending series. We hold no consumer spending data. Buy or drop. |
| 4 | Passenger air fare share of travel and tourism spending, 1999-2024 | **Cannot** | Absolute fare levels and total travel spend. Our fare series is an INDEX, base 100; absolute levels are the F15 data-sourcing item still open in the assumptions book. |
| 5 | Regional unemployment against the 2010-2019 average | **Cannot** | S&P Global labour market data. Not held, and not a driver in our method. |
| 6 | Air travel affordability: average fare as a share of per-capita GDP, by region, 2015 against 2024 | **Partial** | We have GDP per capita by country from OEF. We do NOT have absolute fares. The single most valuable gap on this list: affordability is the mechanism behind emerging-market growth, and we cannot show it. |
| 7 | RPK recovery against 2019, total, domestic, international, to 2027 | **Can** | We hold the history and the forecast, and the domestic and international split is in the engine. Straightforward. |
| 8 | Annual forecast by airline region of domicile, RPK indexed to 2019 | **Partial** | Ours is by AIRPORT, so we produce region of origin, not airline region of domicile. Different cut of the same traffic. State the difference on the slide rather than imply equivalence. |
| 9 | Top five international route areas: intra-APAC, intra-Europe, APAC-Europe, APAC-NAM, Europe-NAM | **Can** | The region-pair flow matrix already produces this; the dashboard carries 21 flows. Boeing's five are a subset. |
| 10 | Tariff impact on GDP and on US inbound visits | **Cannot** | A scenario overlay we do not run. Could be built as a named scenario if it matters commercially. |
| 11 | World economy rebalancing: GDP growth by major economy | **Can** | Straight from the OEF country GDP that drives the forecast, which is the honest thing to show since it is our input. |

## 2. Air cargo demand

| p | Boeing slide | Avia | What it needs |
|---|---|---|---|
| 13 | World CTK index since 2000 with shocks marked | **Partial** | We have the shock framework and the resilience module, applied to passengers. No CTK series. |
| 14 | De minimis e-commerce driving air cargo | **Cannot** | US customs bills-of-lading data. Not held. |
| 15 | Containership schedule reliability against freighter reliability | **Cannot** | Maritime data. Not held and not our field. |
| 16 | Air cargo flows reconfiguring, US imports from East Asia | **Cannot** | Trade flow data. Not held. |

**Cargo is the weakest section and the decision is strategic, not technical.** Atlas
forecasts landed tonnage at airport level, so we can speak to airport cargo. We cannot
speak to the world air cargo market. Either acquire the data, or scope the OGF explicitly
as passenger and airport cargo and say so, which is a defensible position for an airport
forecaster and a poor one for anyone claiming a full market outlook.

## 3. Airline trends

| p | Boeing slide | Avia | What it needs |
|---|---|---|---|
| 18 | 25 years of traffic and network: airport pairs, RPK, departures, each with its CAGR | **Can** | Airport pairs and departures come from the OAG store, RPK from the engine. This is a strong slide for us and arguably stronger than theirs, because ours is built from the schedule rather than sampled. |
| 19 | Competition against consolidation: cumulative ASK share by market, HHI | **Partial** | OAG gives carrier-level ASK, so the calculation is available. Nothing in the engine computes it today. A day's work. |
| 20 | LCC share of intra-regional capacity, 2009 to 2024 | **Can** | OAG carrier categories plus the LCC classification already used in the configured-airport work. |
| 21 | Premium segmentation: international RPK by booking class, premium economy share | **Partial** | The Sabre cabin work behind `build_history.py` and the shock resilience module gives premium against economy. The premium-economy seat share by market is not built. |

## 4. Fleet dynamics

| p | Boeing slide | Avia | What it needs |
|---|---|---|---|
| 23 | Share of fleet at typical retirement age, single-aisle and widebody | **Cannot** | Fleet age data, Cirium or Ascend. Avia holds Ascend FlightGlobal and IBA, so this is an acquisition question rather than a capability gap. |
| 24 | Single-aisle productivity: ASK, seats and fleet growth, and what drives the gap between them | **Partial** | We derive implied fleet from ASK and seats, and the dashboard already reports implied narrowbody and widebody fleet at 2045. The breakdown into densification, up-gauging, stage length and flights per day is not built. **This slide is where our 3.5% against their 4.0% would have to be explained**, because it is the same arithmetic seen from the fleet side. |
| 25 | Widebody versatility, same breakdown | **Partial** | As above. |
| 26 | Single-aisle seat capacity by business model since 2004 | **Can** | OAG gives seats by carrier and the business-model classification exists. |
| 27 | Fleet productivity to 2043: load factor, utilisation, average seats | **Cannot** | We assume a load factor path; we do not forecast utilisation or average seats as outputs. Currently front-end derivation factors, which the dashboard already flags as pending a move into the engine. |

---

## What the inventory says about the forecast

**Three gaps are about data we do not hold**: consumer and travel spending, cargo market
data, and fleet age. Each is a buy-or-scope decision, not an engineering one.

**One gap is already on our own risk list and this makes it client-visible.** Absolute
fare levels, the F15 item. Without them we cannot draw the affordability slide, and
affordability is the mechanism Boeing uses to explain emerging-market growth. We forecast
with a fare index and we cannot show what a fare costs anyone. That is the gap to close
first.

**Two gaps are classification, not capability.** Airline region of domicile against
airport region, and Boeing's ten regions against our six. Ours is built airport by
airport so we can cut it any way we choose; we simply have not built their cut. See the
region mapping note below.

**One gap is the interesting one.** The fleet productivity breakdown, pages 24 and 25.
Boeing shows ASK growing 5.7% while seats grow 4.8% and the fleet grows 3.1%, and names
the difference: densification, up-gauging, longer stages, more flights per day. Our
forecast produces the ASK and implies the fleet, but does not explain the wedge between
them. Since the whole gap between 4.0% and 3.5% has to live somewhere in that wedge, this
is the slide that would either explain our number or expose it.

## Region mapping

Boeing forecasts ten regions: Africa, China, Eurasia, Latin America, Middle East, North
America, Northeast Asia, Oceania, South Asia, Southeast Asia. We forecast six: Africa,
Asia Pacific, Europe, Middle East, North America, South America.

Our Asia Pacific covers five of theirs, and their spread across those five is enormous:
Northeast Asia 2.4% against Southeast Asia and South Asia at 7.0%. A single Asia Pacific
number cannot be reconciled against that, and cannot be defended in a room where somebody
holds their deck.

Because Atlas is built airport by airport, adding their classification is a mapping table,
not a modelling change: every airport already carries a country, and their ten regions are
a partition of countries. Build it as a second region scheme alongside ours, selectable in
the tool, and every comparison after that is like for like.

Copyright Avia Solutions Limited. All rights reserved.

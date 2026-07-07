# Global terminal-passenger forecast v0.1
**6 July 2026 | Avia Solutions | Phase 3b. The O&D world turned into terminal passengers with transfers, anchored to ACI true throughput. Base year 2024, horizon 2050.**

## The headline
World terminal passengers grow from 8,896m in 2024 to 20,017m in 2050, a 3.30% annual rate. The base year matches ACI's own published figure of circa 8.9bn almost exactly, because it is anchored to it. The growth rate sits 0.10 percentage points below ACI's World Airport Traffic Forecast of 3.4%, inside the coherence band. So the tool now produces the headline number airports and investors actually use, terminal throughput, and it agrees with the industry reference both on level and on growth.

## How the transfer traffic gets in
The O&D forecast counts journeys once. Terminal throughput counts every passenger each time they touch an airport, so a hub also carries the connecting passengers who change planes. The base-year split between the two is real, not assumed: at each airport, local O&D comes from Sabre, and connecting is what ACI terminal throughput shows over and above that O&D. That split picks out the hubs cleanly, Doha at 84% connecting, Atlanta and Frankfurt at 64%, Dubai at 57%, while Luton and Stansted sit near zero. Forward, local O&D grows at the airport's own demand rate and connecting grows at the international rate of the markets it feeds.

## The regional shape
| Region | 2024 (m) | 2050 (m) | CAGR |
|---|---|---|---|
| Asia Pacific | 2,893 | 8,980 | 4.64% |
| North America | 2,410 | 3,749 | 1.78% |
| EU+UK | 1,841 | 2,638 | 1.45% |
| Other Europe | 612 | 1,219 | 2.79% |
| South America | 456 | 1,171 | 3.85% |
| Africa | 245 | 1,210 | 6.60% |
| Middle East | 441 | 1,050 | 3.53% |

Asia Pacific becomes the clear centre of gravity, Africa grows fastest off a small base, and the mature Western markets grow slowly, the standard long-run picture. The Middle East grows more slowly on terminal than on O&D, correctly: its throughput is dominated by transfer traffic at Dubai and Doha, which tracks international feed rather than the fast local-market rates.

## What this is and is not
This is the region-based version of connecting. It grows the observed base-year connecting mass on the real ACI hub split, which is why hub-heavy airports carry their transfers forward and O&D airports do not. It does not yet route each individual flow through an explicit per-hub matrix built from the OAG schedules. That per-hub routing is the next refinement and will let the model answer which specific markets feed which hub, rather than growing the hub's transfer total as a block. For a world and regional terminal forecast, the block approach is sound and it reconciles to ACI.

Two data refinements still stand behind the numbers: regional rather than per-country GDP, and propensity saturation only for the thirty countries where we hold population. Both close as the OEF world file and global population are staged, and the ACI panel back to 2011 (and monthly to 2004) is now on disk for the airport-level regressions and seasonality.

## Artefacts
`data/global_terminal_2024_2050.json`, reproducible via `scripts/run_global_terminal.py`. Built on the ACI panel and hub calibration on E:. Full suite 139 green. Everything now runs off local and E: disk, not OneDrive.

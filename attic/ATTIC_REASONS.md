# Attic: what is here and why

Working scratch and superseded steps, committed rather than deleted. A deletion is a
loss; a gitignored file is a file that exists on one machine only, which is the fault
the repository exists to end. Nothing here is imported by the engine, the webapp or the
build scripts; the capability audit confirms it.

One line per file, added when the file arrives.

Author: Avia Solutions. Version 1.0, 8 August 2026.

| File | Where it came from | Why it is here rather than in the tree |
|---|---|---|
| `dashboard_backup_pre-observatory_20260718_1812.html` | `webapp/` | The dashboard as it stood before the Observatory restyle on 18 July 2026. Kept as the visual reference for what changed. |
| `peakhour_workbook_unfilter.py` | project `build\scripts\`, 4 August 2026 20:32 | Cleared Jess Rowden's saved AutoFilters outright. Superseded the same evening by `scripts/peakhour_workbook_refilter.py`, which hides only the rows a power trendline cannot fit: clearing the filter outright put zeros and blanks back into the plotted range and killed the trendlines. Kept because the reasoning is the record of why neither state was right. |
| `addsheet_draft_20260804_2012.py` | project `build\scripts\addsheet.py`, 4 August 2026 20:12 | First draft of the Avia comparison sheet writer. Superseded by `scripts/peakhour_workbook_addsheet.py` (21:59), which added the BEG.xlsx convention finding and the like-for-like comparison block. |
| `fill_draft_20260804_2012.py` | project `build\scripts\fill.py`, 4 August 2026 20:12 | First draft of the Data-sheet fill. Superseded by `scripts/peakhour_workbook_fill.py`, which records the convention confirmed from BEG.xlsx: the summary links to row 7 throughout, so every figure headed "30th BHR" is in fact the absolute peak hour. |

## Not in the attic, and why

`scripts/peakhour_workbook_addsheet.py` arrived from the same place as the three files
above but went into `scripts/`, not here. It is the script that produced the delivered
workbook `2025 Peak Hour and 30th BHR - Avia complete - 4 August 2026.xlsx`: the file
timestamps match to the minute, and it existed in exactly one place on the estate before
8 August 2026. A copy made on 6 August moved four of the peak-hour scripts into the
engine tree and missed this one.

"""outputs/chart_format - the exact Avia chart format (Cockpit build update F2/F4).

From "Avia Chart Format and Chart Catalogue": Arial/Ebrima, heading 20pt bold
centred, a Source line (never "Sources"), 18pt axes, legend at the bottom, data
labels 18pt bold matching the line colour, dedicated chart sheets, no
borders/gridlines. The Office palette is pinned per vintage (the current Office
2024 accents) so engine charts match hand-made ones. Files are author-stamped
"Avia Solutions" and verified. Author: Avia Solutions.
"""
from __future__ import annotations

AUTHOR = "Avia Solutions"
FONT = "Arial"                                   # or Ebrima
OFFICE_2024_PALETTE = ["156082", "E97132", "196B24", "0F9ED5", "A02B93", "4EA72E"]
OFFICE_PRE2024_PALETTE = ["4472C4", "ED7D31", "A5A5A5", "FFC000", "5B9BD5", "70AD47"]
PINNED_PALETTE = OFFICE_2024_PALETTE

SIZES = {"heading": 20, "source": 16, "axis": 18, "axis_title": 18, "legend": 18,
         "data_label": 18, "in_chart": 18, "marker": 10}
GAP_WIDTH = 50                                    # circa 25-75 on columns


def source_line(sources: str = "OAG, AviaSolutions analysis") -> str:
    """The Source line, singular 'Source:' by house rule."""
    return f"Source: {sources}"


def validate_source_line(line: str) -> bool:
    """Reject the common 'Sources' error; require the singular form."""
    return line.startswith("Source:") and not line.startswith("Sources")


def year_label(year: int, base_year: int) -> str:
    """FY-style label with A/F suffix relative to the base year."""
    return f"{year}{'A' if year <= base_year else 'F'}"

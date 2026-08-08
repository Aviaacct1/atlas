"""outputs/licence - export licence filter. Author: Avia Solutions.

The product redistributes forecasts and assumption metadata, never licensed source data (Sabre,
ACI, OEF, OAG are internal/base-year only). licence_filter walks an export and blocks it if it
embeds raw source records; naming a source ("OAG", "MIDT true O&D") in assumption metadata is fine,
carrying its rows is not.
"""
from __future__ import annotations

FORBIDDEN = ("itinerary", "itineraries", "sabre_rows", "sabre_records", "aci_history_rows",
             "aci_rows", "midt_records", "midt_rows", "oag_rows", "raw_records", "source_records",
             "raw_rows")


def licence_filter(obj, path: str = "$"):
    """Return (ok, findings). ok is False when the export embeds raw licensed source data."""
    findings = []

    def walk(o, p):
        if isinstance(o, dict):
            for k, v in o.items():
                if any(f in str(k).lower() for f in FORBIDDEN):
                    findings.append(f"{p}.{k}: raw licensed source data must not be exported")
                walk(v, f"{p}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{p}[{i}]")

    walk(obj, path)
    return (not findings, findings)

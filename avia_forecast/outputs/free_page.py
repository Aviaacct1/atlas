"""outputs/free_page - the per-airport free page generator (O-15). Author: Avia Solutions.

The distribution wedge: a one-page, watermarked, current-vintage headline view for any modelled
airport, generated from the global extract. Honest by construction - residual pseudo-airports are
stamped as country aggregates, illustrative capacity is labelled, and the error record says so when
there is not one yet.
"""
from __future__ import annotations

WATERMARK = "Avia Global Forecast - free view (current vintage)"


def _cap_requirement_date(years, term_u, term_c):
    """First year the constrained path falls below the unconstrained by more than a rounding margin."""
    for i, y in enumerate(years):
        if i < len(term_u) and i < len(term_c) and term_c[i] < term_u[i] * 0.999:
            return y
    return None


def per_airport_page(extract: dict, iata: str) -> dict:
    years = extract.get("years", [])
    ap = (extract.get("airports") or {}).get(iata, {})
    meta = extract.get("meta", {})
    term_u = ap.get("term_u") or []
    term_c = ap.get("term_c") or []
    pseudo = bool(ap.get("pseudo")) or str(iata).startswith("_")
    cap_source = ap.get("capacity_source")

    stamps = []
    if pseudo:
        stamps.append("residual pseudo-airport: country aggregate, not an individual airport")

    cap_date = None
    if cap_source == "register" and term_u and term_c:
        cap_date = _cap_requirement_date(years, term_u, term_c)
        cap_stmt = (f"capacity requirement from {cap_date}" if cap_date
                    else "no capacity constraint before the horizon (registered)")
    elif cap_source == "illustrative":
        cap_stmt = "capacity illustrative (grade C; register pending)"
        stamps.append(cap_stmt)
    else:
        cap_stmt = "no capacity constraint modelled"
        stamps.append("capacity not registered")

    error_record = meta.get("error_record") or "no published error record yet (backtest pending)"

    return {"airport": iata, "name": ap.get("name", iata), "watermark": WATERMARK,
            "vintage": meta.get("vintage"), "years": years, "traffic_path": term_u,
            "capacity_statement": cap_stmt, "capacity_date": cap_date,
            "error_record": error_record, "stamps": stamps, "pseudo": pseudo}

"""outputs/persona - persona translations carried in the extract (O-16). Author: Avia Solutions.

Three per-airport translations computed engine-side so the front end never derives them:
fleet-equivalents by region, a P-band downside case, and the DDFS date-of-constraint. Definitions
travel in extract.meta.persona so a reader can see exactly what each number means.
"""
from __future__ import annotations


def fleet_equivalents(rpk_series: dict, rpk_per_aircraft: float) -> dict:
    """Aircraft-equivalents = annual RPK / a representative annual RPK per aircraft for the region
    (seats x stage x utilisation x load factor, documented per region). Jess J5: an equivalence, not a
    fleet plan."""
    if not rpk_per_aircraft:
        return {}
    return {y: v / rpk_per_aircraft for y, v in rpk_series.items()}


def p_band_downside(central_series: dict, band) -> dict:
    """Downside case = central x (1 - band). band is a {year: fraction} (widening with horizon) or a
    scalar. A surfaced downside on the central path, not a new forecast."""
    def b(y):
        if isinstance(band, dict):
            return float(band.get(y, band.get(str(y), 0.0)))
        return float(band)
    return {y: v * (1.0 - b(y)) for y, v in central_series.items()}


def date_of_constraint(years, term_u, term_c):
    """DDFS date-of-constraint: first year the constrained path falls below the unconstrained."""
    for i, y in enumerate(years):
        if i < len(term_u) and i < len(term_c) and term_c[i] < term_u[i] * 0.999:
            return y
    return None


def attach_persona(extract: dict, rpk_per_aircraft_by_region: dict, p_band=0.15, region_of=None) -> dict:
    """Attach the three persona translations to every airport in the extract, engine-side. region_of
    (iata) -> region maps an airport to its region's productivity when the airport record has no
    region field. Returns the extract."""
    years = extract.get("years", [])
    for iata, ap in (extract.get("airports") or {}).items():
        region = ap.get("region") or (region_of(iata) if region_of else None)
        rpa = rpk_per_aircraft_by_region.get(region) if region else None
        constrained = ap.get("rpk_c_bn") is not None
        rpk_list = ap.get("rpk_c_bn") or ap.get("rpk_u_bn") or []
        rpk_series = {years[i]: rpk_list[i] for i in range(min(len(years), len(rpk_list)))}
        ap["fleet_equiv"] = fleet_equivalents(rpk_series, rpa) if rpa else None
        ap["fleet_equiv_basis"] = ("constrained" if constrained else "unconstrained") + \
            " RPK / region aircraft-equivalent"
        term = ap.get("term_c") or ap.get("term_u") or []
        term_series = {years[i]: term[i] for i in range(min(len(years), len(term)))}
        ap["p_downside"] = p_band_downside(term_series, p_band)
        ap["ddfs_date"] = date_of_constraint(years, ap.get("term_u") or [], ap.get("term_c") or [])
    extract.setdefault("meta", {})["persona"] = {
        "rpk_per_aircraft_by_region": rpk_per_aircraft_by_region, "p_band": p_band,
        "definition": ("fleet-equivalent = annual RPK / representative annual RPK per aircraft (region); "
                       "P-band downside = central x (1 - band); DDFS date = first year constrained < unconstrained")}
    return extract

"""stage_length - the distance per passenger the RPK conversion applies.
Author: Avia Solutions.

One place, read from config/stage_length.yaml, because until 9 August 2026 the same
per-region constant was written into scripts/compare_regions_boeing.py and copied by hand
into two measurement scripts. Three copies of one number is three chances for them to
stop agreeing, and a comparison against Boeing that quietly used a different distance in
one script than in another would look exactly like a finding.

Two parts, and they come from different sources:

  LEVEL   base_km_per_passenger, keyed on the ENGINE's regions, which is what an airport
          record carries. Representative averages, still [P1].
  GROWTH  growth_by_boeing_region, keyed on BOEING's regions, estimated from Sabre O&D
          journey length over 2013-2025. See MEASUREMENTS.md section 7.

The growth term is why this module exists. A constant stage length cancels inside our own
CAGR and does not cancel against a counterparty whose RPK carries their stage length
growth, which is the only comparison the conversion is for.
"""
from __future__ import annotations

from .config import _load as cfg_load

_CFG = None


def _cfg():
    global _CFG
    if _CFG is None:
        _CFG = cfg_load("stage_length.yaml")
    return _CFG


def base_year():
    return int(_cfg().get("base_year", 2025))


def base_km(engine_region):
    """Distance per departing O&D passenger in the base year, thousand km."""
    tbl = _cfg()["base_km_per_passenger"]
    return float(tbl.get(engine_region, tbl["_G"]))


def growth(boeing_region):
    """Annual stage length growth for a Boeing region. A region absent from the table
    takes the common world rate rather than zero: zero is a claim that a region's network
    shape is frozen, and it is not the neutral choice it looks like."""
    tbl = _cfg()["growth_by_boeing_region"]
    return float(tbl.get(boeing_region, tbl["World"]))


# The growth rates are estimated on Boeing's ten regions; the webapp works on the
# engine's six. This fold is the stated mapping between the two, added 23 August 2026
# when the dashboard's RPK basis moved off its typed constants: until then the page
# converted passengers to RPK with a constant stage length, so its RPK CAGR equalled
# its passenger CAGR while every comparator's carried stage length growth inside it,
# and the reconciliation table's "matched basis" claim did not hold for RPK rows.
BOEING_TO_ENGINE = {
    "China": "Asia Pacific", "Northeast Asia": "Asia Pacific",
    "Southeast Asia": "Asia Pacific", "South Asia": "Asia Pacific",
    "Oceania": "Asia Pacific", "Eurasia": "Europe",
    "Middle East": "Middle East", "Africa": "Africa",
    "North America": "North America", "Latin America": "South America",
}


def growth_engine(engine_region, weights=None):
    """Stage length growth for an ENGINE region: the weighted mean of the Boeing
    regions that fold into it. `weights` maps Boeing region to a weight (the dashboard
    build uses airport counts from regions_boeing.json, the same file the applied
    rates come from); equal weights when None. A region with no members takes the
    common world rate."""
    members = [b for b, e in BOEING_TO_ENGINE.items() if e == engine_region]
    if not members:
        return growth("World")
    w = [(weights or {}).get(b, 1.0) for b in members]
    tot = sum(w)
    if tot <= 0:
        w, tot = [1.0] * len(members), float(len(members))
    return sum(wi * growth(b) for wi, b in zip(w, members)) / tot


def factor(boeing_region, year, base=None):
    """Stage length index, 1.0 in the base year."""
    b = base_year() if base is None else base
    return (1.0 + growth(boeing_region)) ** (year - b)


def km(engine_region, boeing_region, year, base=None):
    """Distance per passenger in `year`, thousand km, level and growth together."""
    return base_km(engine_region) * factor(boeing_region, year, base)


def rpk(pax_m, engine_region, boeing_region, year, base=None):
    """RPK in billions from passengers in millions."""
    return pax_m * km(engine_region, boeing_region, year, base)

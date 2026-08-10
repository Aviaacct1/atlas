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

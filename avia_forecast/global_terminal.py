"""global_terminal - Phase 3b: terminal passengers with transfers. Author: Avia Solutions.

Turns the O&D world forecast (global_demand) into terminal-passenger throughput per
airport by adding connecting traffic, anchored to ACI true throughput.

Base year anchored to ACI (aci_hub_calibration_2024): each airport's terminal splits
into local O&D (Sabre, both ends) and connecting (ACI terminal minus that O&D). Forward,
local O&D grows at the airport's own O&D demand rate. Connecting is routed across
destination regions by the airport's OAG final-to-next M (share of departing seats by
region), and each region slice grows at that destination region's O&D rate, so a hub
feeding Asia grows its transfers faster than one feeding mature markets. Airports without
an M row fall back to the world international rate; airports without a modelled O&D series
fall back to the world index.

The ACI 2024 anchor vs the 2025 O&D base is a one-year offset, immaterial over the
horizon [P1].
"""
from __future__ import annotations
from .paths import DATA, OEF_DIR, ACI_DIR, ACI_DECRYPT, SABRE_DB, OAG_DB, QSI_REF, PREAGG, QSI_APP, OEF_GDP_XLSX
from dataclasses import dataclass
import json, os

from . import global_demand as gd
from .geo.regions_iso2 import region_for_iso2

DATA = DATA


@dataclass
class TerminalResult:
    years: list
    world: dict
    by_region: dict
    world_cagr: float
    base_terminal_m: float
    by_airport: dict
    meta: dict


def _load(name):
    return json.load(open(os.path.join(DATA, name)))


def run_terminal(scenario="Baseline"):
    cal = _load("aci_hub_calibration_2024.json")
    try:
        M = _load("oag_final_to_next_M.json")     # per-airport destination-region seat shares
    except FileNotFoundError:
        M = {}
    g = gd.run_global(scenario=scenario)
    years = g.years
    ap_idx = g.meta["by_airport_index"]
    ap_intl = g.meta["by_airport_intl_index"]

    w0 = g.world[years[0]]
    world_od_index = [g.world[y] / w0 for y in years]
    intl0 = sum(s[years[0]] for r, s in g.by_region.items() if r != "Domestic")
    world_intl_index = [sum(s[y] for r, s in g.by_region.items() if r != "Domestic") / intl0
                        for y in years]
    # per destination-region O&D growth index (base year = 1.0)
    region_index = {r: [s[y] / s[years[0]] for y in years] for r, s in g.by_region.items()}

    def connecting_series(iata, conn_base):
        row = M.get(iata)
        if not row:
            return [conn_base * world_intl_index[i] for i in range(len(years))]
        tot = sum(row.values()) or 1.0            # renormalise so base year reproduces conn_base (anchor preserved)
        out = [0.0] * len(years)
        for r, share in row.items():
            idx = region_index.get(r, world_intl_index)
            w = share / tot
            for i in range(len(years)):
                out[i] += conn_base * w * idx[i]
        return out

    world = {y: 0.0 for y in years}
    by_region = {}
    by_airport = {}
    base_terminal = 0.0

    for iata, c in cal.items():
        od_base = c["od_both_ends_2024"] or 0.0
        conn_base = c["connecting_est"] or 0.0
        if od_base <= 0 and conn_base <= 0:
            continue
        od_i = ap_idx.get(iata, world_od_index)
        conn_s = connecting_series(iata, conn_base)
        region = region_for_iso2(c.get("country_code")) or "Other"
        reg = by_region.setdefault(region, {y: 0.0 for y in years})
        base_terminal += (od_base + conn_base)
        ap = []
        for i, y in enumerate(years):
            term_m = (od_base * od_i[i] + conn_s[i]) / 1e6
            world[y] += term_m
            reg[y] += term_m
            ap.append(round(term_m, 3))
        by_airport[iata] = {"region": region, "country": c.get("country_code"),
                            "connecting_share": c.get("connecting_share"),
                            "series": ap}

    y0, y1 = years[0], years[-1]
    cagr = (world[y1] / world[y0]) ** (1.0 / (y1 - y0)) - 1.0
    return TerminalResult(years, world, by_region, cagr, base_terminal / 1e6, by_airport,
                          meta={"scenario": scenario, "n_airports": len(cal),
                                "hubs_with_M": sum(1 for a in cal if a in M),
                                "base_anchor": "ACI 2024 terminal; O&D growth from Sabre 2025 base; "
                                               "connecting routed on OAG final-to-next M"})

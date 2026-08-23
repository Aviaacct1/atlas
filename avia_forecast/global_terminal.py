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

from .config import get
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


def _admissions(cal):
    """Airports the base holds and ACI does not, from config/terminal_admissions.yaml.

    This iteration is over the ACI file, so an airport ACI does not publish carries no
    terminal forecast and reaches no published figure however much traffic the base holds.
    Beijing Daxing was 20.4m of outbound O&D and absent from the dashboard, the
    reconciliation and the deck for exactly that reason.

    The admitted records live in configuration and never in the ACI file, so a published
    airport can always be told from an admitted one, and an airport ACI already carries is
    refused rather than overridden.
    """
    from .config import _load as cfg_load
    try:
        cfg = cfg_load("terminal_admissions.yaml") or {}
    except FileNotFoundError:
        return {}, []
    out, notes = {}, []
    for iata, rec in (cfg.get("admissions") or {}).items():
        if iata in cal:
            notes.append(f"{iata} refused: ACI already publishes it, so the ACI record stands")
            continue
        term = rec.get("terminal_pax_2024")
        od = rec.get("od_both_ends_2024")
        if not term or od is None or not rec.get("country_code") or not rec.get("terminal_source"):
            notes.append(f"{iata} refused: terminal_pax_2024, od_both_ends_2024, "
                         f"country_code and terminal_source are all required")
            continue
        if od > term:
            notes.append(f"{iata} refused: O&D at both ends {od:,.0f} exceeds terminal "
                         f"{term:,.0f}, so one of the two is on a different basis")
            continue
        out[iata] = {"od_both_ends_2024": float(od),
                     "connecting_est": float(term) - float(od),
                     "country_code": rec["country_code"],
                     "admitted": True, "admission_source": rec["terminal_source"]}
        notes.append(f"{iata} admitted: terminal {term / 1e6:,.2f}m, O&D both ends "
                     f"{od / 1e6:,.2f}m, connecting share "
                     f"{(float(term) - float(od)) / float(term):.3f}")
    return out, notes


def run_terminal(scenario="Baseline"):
    cal = _load("aci_hub_calibration_2024.json")
    admitted, admission_notes = _admissions(cal)
    for note in admission_notes:
        print("terminal admissions: " + note)
    cal = {**cal, **admitted}
    # Per-airport destination-region seat shares. Absent, every airport falls back to the
    # region average, which is a different forecast and used to happen in silence.
    M = gd._load_external("oag_final_to_next_M.json",
                          "no airport carries its own destination-region seat shares and "
                          "each falls back to the region average") or {}
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

    from .global_checks import reconcile_connecting, tb_check
    _repo_data = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    try:
        conn_sabre = json.load(open(os.path.join(_repo_data, "connecting_sabre_2024.json")))   # leg-MEASURED connecting
    except Exception:
        conn_sabre = {}
    discrepancies, n_floored, tb_fail, n_measured, n_residual = [], 0, 0, 0, 0
    flagged_terminal = 0.0
    _cshare_method = get('global_drivers.connecting_share_method', 'blend')
    for iata, c in cal.items():
        od_both = c["od_both_ends_2024"] or 0.0
        conn_est = c["connecting_est"] or 0.0
        aci_terminal = od_both + conn_est          # ACI actual terminal - the LEVEL truth (Sabre is only a sample)
        if aci_terminal <= 0:
            continue
        measured = conn_sabre.get(iata)
        sabre_share = (measured / (od_both + measured)) if (measured and (od_both + measured) > 0) else None
        resid_share = (conn_est / aci_terminal) if aci_terminal > 0 else None
        if _cshare_method == "sabre" and sabre_share is not None:
            share, source = sabre_share, "sabre_legs"; n_measured += 1
        elif _cshare_method == "residual" and resid_share is not None:
            share, source = resid_share, "aci_residual"; n_residual += 1
        elif sabre_share is not None and resid_share is not None and resid_share > 0:
            share = (sabre_share * resid_share) ** 0.5              # BLEND: geomean reconciles the two sources
            source = "sabre_aci_blend"; n_measured += 1
        elif sabre_share is not None:
            share, source = sabre_share, "sabre_legs"; n_measured += 1
        else:
            share, source = (resid_share or 0.0), "aci_residual"; n_residual += 1
            if conn_est < 0:
                n_floored += 1
        # flag only where the two sources still disagree materially (review), gated on size
        if sabre_share is not None and resid_share is not None:
            flag = "aci_sabre_share_divergence" if (aci_terminal > 5e5 and abs(sabre_share - resid_share) > 0.30) else None
        else:
            flag = "negative_residual" if (source == "aci_residual" and conn_est < -0.02 * (od_both or 1.0) and aci_terminal > 5e5) else None
        # Second caveat dimension (MEASUREMENTS 14, 23 August 2026): the share-based flag
        # catches small leisure airports and misses the hubs where the split matters most
        # in absolute terms (BLR, DEL, SVO, SIN in the divergence run). Material = the two
        # sources disagree by more than 2m passengers of base-year split, a stated
        # threshold; caveat only, it does not feed the publication band.
        material = (sabre_share is not None and resid_share is not None
                    and aci_terminal * abs(sabre_share - resid_share) > 2e6)
        share = max(0.0, min(0.9, share))                           # keep the split sane
        conn_base = aci_terminal * share            # LEVEL anchored to ACI, split by the (Sabre-measured) connecting share
        od_anchor = aci_terminal * (1.0 - share)
        if flag:
            flagged_terminal += aci_terminal
            discrepancies.append({"iata": iata, "aci_terminal": round(aci_terminal), "share": round(share, 3),
                                  "source": source, "flag": flag})
        if not tb_check(aci_terminal, od_anchor, conn_base):        # T-B: terminal(ACI) = O&D + connecting (by construction)
            tb_fail += 1
        od_i = ap_idx.get(iata, world_od_index)
        conn_s = connecting_series(iata, conn_base)
        region = region_for_iso2(c.get("country_code")) or "Other"
        reg = by_region.setdefault(region, {y: 0.0 for y in years})
        base_terminal += aci_terminal
        ap = []
        for i, y in enumerate(years):
            term_m = (od_anchor * od_i[i] + conn_s[i]) / 1e6
            world[y] += term_m
            reg[y] += term_m
            ap.append(round(term_m, 3))
        by_airport[iata] = {"region": region, "country": c.get("country_code"),
                            "connecting_share": round(share, 3), "conn_source": source,
                            "cx_flag": bool(flag),        # >30-point share disagreement between the sources
                            "cx_material": bool(material),  # >2m pax of base-year split between the sources
                            "admitted": bool(c.get("admitted")), "series": ap}

    y0, y1 = years[0], years[-1]
    cagr = (world[y1] / world[y0]) ** (1.0 / (y1 - y0)) - 1.0
    return TerminalResult(years, world, by_region, cagr, base_terminal / 1e6, by_airport,
                          meta={"scenario": scenario, "n_airports": len(cal),
                                "admitted": sorted(admitted),
                                "admission_notes": admission_notes,
                                # An airport with no destination mix row grows its
                                # connecting traffic on the world international rate,
                                # which is a different forecast for that airport. The
                                # count alone reads as small; the traffic behind it is
                                # what decides whether it matters.
                                "no_M_row": sum(1 for a in cal if a not in M),
                                "no_M_row_terminal_m": round(sum(
                                    (c.get("od_both_ends_2024") or 0.0)
                                    + (c.get("connecting_est") or 0.0)
                                    for a, c in cal.items() if a not in M) / 1e6, 1),
                                "hubs_with_M": sum(1 for a in cal if a in M),
                                "tb_base_pass": tb_fail == 0, "tb_fail": tb_fail,
                                "connecting_measured": n_measured, "connecting_residual": n_residual,
                                "connecting_flagged_traffic_share": round(flagged_terminal / base_terminal, 4) if base_terminal else 0.0,
                                "connecting_floored": n_floored, "connecting_flagged": len(discrepancies),
                                "connecting_discrepancies": discrepancies[:20],
                                "base_anchor": "ACI 2024 terminal; O&D growth from Sabre 2025 base; "
                                               "connecting routed on OAG final-to-next M"})

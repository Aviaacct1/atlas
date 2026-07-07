"""outputs/derive - engine-driven demand outputs (Cockpit E/B2 wiring).

Computes the impact-table rows from the pipeline run itself, not from standalone
assumptions: dom/int/transfer/O&D from the region-resolved flows and terminal,
commercial ATMs from segment seats/LF, cargo tonnage (GDP-linked) and freighter
ATMs, GA pax/ATMs, total ATMs and the design-day schedule. Units: pax and cargo in
m and kt; ATMs in thousands of movements. Author: Avia Solutions.
"""
from __future__ import annotations
from .. import fixtures as fx
from ..config import get
from ..aggregate import atm

METRICS = ["total_pax", "unconstrained", "od_pax", "transfer_pax", "dom_pax", "int_pax",
           "cap_requirement", "commercial_atm", "cargo_tonnage", "cargo_atm", "ga_pax",
           "ga_atm", "total_atm", "ddfs"]


def derive_demand_outputs(results, pilot, scenario="Baseline") -> dict:
    t = results.tidy
    years = results.summary["years"]
    seats = get("atm_conversion.seats_per_movement")
    lf = get("atm_conversion.load_factor")
    gdp = fx.gdp_index(scenario)
    cargo0 = get("cargo_base.tonnage_kt")
    ga_pax = atm.ga_series(get("general_aviation_base.pax_m"), get("general_aviation_base.growth"), years)
    ga_atm = atm.ga_series(get("general_aviation_base.atm_k"), get("general_aviation_base.growth"), years)

    def flow(r, y):
        return float(t[(t.metric == "flow_u") & (t.region == r) & (t.year == y)]["value"].sum())

    def gsum(metric, y):
        return float(t[(t.metric == metric) & (t.iata != "-") & (t.year == y)]["value"].sum())

    out = {m: {} for m in METRICS}
    for y in years:
        od_by_region = {r: flow(r, y) for r in pilot.regions}
        od_total = sum(od_by_region.values())
        term = gsum("term_u", y)
        transfer = term - od_total                       # transfer + O&D = terminal
        dom = od_by_region.get("Domestic", 0.0)
        intl = od_total - dom                            # dom + int = O&D

        pax_seg = {"Domestic": 0.0, "International Short Haul": 0.0, "Long Haul": 0.0}
        for r, v in od_by_region.items():
            pax_seg[fx.SEGMENT[r]] += v
        commercial_atm = sum(pax_seg[s] * 1000.0 / (seats[s] * lf[s]) for s in pax_seg)  # k movements
        cargo_t = cargo0 * (gdp[y] / gdp[years[0]]) ** get("cargo.gdp_elasticity")
        cargo_a = atm.cargo_freighter_atm(cargo_t)       # k movements (kt basis)
        total_a = commercial_atm + cargo_a + ga_atm[y]

        out["total_pax"][y] = term
        out["unconstrained"][y] = term
        out["od_pax"][y] = od_total
        out["transfer_pax"][y] = transfer
        out["dom_pax"][y] = dom
        out["int_pax"][y] = intl
        out["cap_requirement"][y] = gsum("cap_requirement", y)
        out["commercial_atm"][y] = commercial_atm
        out["cargo_tonnage"][y] = cargo_t
        out["cargo_atm"][y] = cargo_a
        out["ga_pax"][y] = ga_pax[y]
        out["ga_atm"][y] = ga_atm[y]
        out["total_atm"][y] = total_a
        out["ddfs"][y] = atm.design_day(total_a)
    return out

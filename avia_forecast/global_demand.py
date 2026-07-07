"""global_demand - Phase 3a multi-country unconstrained demand run. Author: Avia Solutions.

Runs the per-airport, per-region O&D recursion (Method Spec 4.1) for every modelled
airport in the global base year, driven by the airport's home-country GDP growth and
segment fare index, with the elasticity's maturity set by country GDP per head and
income growth damped by propensity saturation where population is known. Aggregates to
region and world and reports the whole-horizon CAGR against an external OEM reference.

This is the demand core scaled worldwide; it does NOT yet add the connecting overlay or
the capacity constraint (Phase 3b / register). "Terminal" here is O&D departing pax.
Regional GDP growth and a shared segment fare index are v1 [P1]; per-country OEF GDP and
per-country population complete the picture as they are staged.
"""
from __future__ import annotations
from .paths import DATA, OEF_DIR, ACI_DIR, ACI_DECRYPT, SABRE_DB, OAG_DB, QSI_REF, PREAGG, QSI_APP, OEF_GDP_XLSX
from dataclasses import dataclass, field
import json, os

import numpy as np

from .config import get
from .demand import core as demand
from .estimate import propensity as pr

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
SEGMENT = {r: ("Domestic" if r == "Domestic" else
              ("International Short Haul" if r in ("EU+UK", "Other Europe") else "Long Haul"))
           for r in ["Domestic", "EU+UK", "Other Europe", "Africa", "Middle East",
                     "Asia Pacific", "North America", "South America"]}


def _load(name):
    return json.load(open(os.path.join(DATA, name)))


E_DATA = DATA
_OEF_GDP = None
_EST_BG = None


def _est_bG():
    """Per-country estimated income elasticity (reliable only), or {} if not staged."""
    global _EST_BG
    if _EST_BG is None:
        try:
            raw = json.load(open(os.path.join(E_DATA, "estimated_bG_by_country.json")))
            _EST_BG = {k: v["bG"] for k, v in raw.items() if v.get("reliable")}
        except FileNotFoundError:
            _EST_BG = {}
    return _EST_BG


def _oef_gdp():
    """Per-country OEF GDP (constant prices) history+forecast, or {} if not staged."""
    global _OEF_GDP
    if _OEF_GDP is None:
        try:
            _OEF_GDP = json.load(open(os.path.join(E_DATA, "oef_gdp_pop_by_iso2.json")))["gdp"]
        except FileNotFoundError:
            _OEF_GDP = {}
    return _OEF_GDP


def _scenario_delta(scenario):
    return (get(f"scenarios.{scenario}", {}) or {}).get("gdp_delta_pp", 0.0) / 100.0


def _gdp_index(region, years, country=None, scenario="Baseline"):
    """GDP level index (base year = 100). Uses the country's own OEF path where staged,
    else the regional assumption. A scenario GDP delta is applied as a cumulative shift to
    the growth rate."""
    delta = _scenario_delta(scenario)
    oef = _oef_gdp().get(country) if country else None
    if oef and str(years[0]) in oef and oef[str(years[0])]:
        base = oef[str(years[0])]
        oyrs = sorted(int(k) for k in oef if oef[k])
        omax = oyrs[-1]
        # terminal GDP growth to extend beyond OEF's horizon (OEF ends ~2050; we forecast further).
        # Use the trailing 5-year CAGR, not one spiky final year, and clamp to a plausible band.
        gterm = 0.02
        _lo = omax - 5
        if str(_lo) in oef and oef[str(_lo)] and oef[str(omax)]:
            gterm = (oef[str(omax)] / oef[str(_lo)]) ** (1.0 / (omax - _lo)) - 1.0
        elif str(omax - 1) in oef and oef[str(omax - 1)]:
            gterm = oef[str(omax)] / oef[str(omax - 1)] - 1.0
        gterm = max(0.0, min(0.04, gterm))
        lvl_by = {}
        for y in range(years[0], years[-1] + 1):
            if str(y) in oef and oef[str(y)]:
                lvl_by[y] = oef[str(y)] / base * 100.0
            else:
                lvl_by[y] = (lvl_by[y - 1] * (1.0 + gterm)) if (y - 1) in lvl_by else 100.0
        return [lvl_by[y] * ((1.0 + delta) ** i) for i, y in enumerate(years)]
    g = get("global_drivers.gdp_growth_by_region").get(region, 0.02) + delta
    idx, lvl = [], 100.0
    for i, _ in enumerate(years):
        if i > 0:
            lvl *= (1.0 + g)
        idx.append(lvl)
    return idx


def _fare_index(years):
    """Shared cost-driven segment fare index (v1 [P1]), rebased to base=100 over the
    horizon; fuel is global so the cost-driven trend is a reasonable global first pass."""
    raw = _load("fare_index_constructed.json")
    out = {}
    base_y = years[0]
    for seg, series in raw.items():
        b = series.get(str(base_y)) or series[min(series, key=lambda k: int(k))]
        out[seg] = [(series.get(str(y), series[max(series, key=lambda k: int(k))]) / b) * 100.0 for y in years]
    return out


def _maturity(country, region, wb):
    thr = get("global_drivers.maturity_gdppc_threshold_usd")
    rec = wb.get(country)
    if rec and rec.get("gdp_pc_ppp"):
        return "mature" if rec["gdp_pc_ppp"] >= thr else "emerging"
    return "mature" if region in get("global_drivers.mature_regions_default") else "emerging"


def _bG(segment, maturity):
    d = get("level3_defaults")[segment]
    return d["bG_mature"] if maturity == "mature" else d["bG_emerging"]


def _clamp_bG(bG):
    """Applied income elasticity stays inside the book bound (Method Spec 4.3); defends
    against out-of-band country estimates until they are re-estimated on O&D [P1]."""
    lo, hi = get("global_drivers.bG_applied_bounds", [0.6, 2.2])
    return max(lo, min(hi, bG))


def _bF(segment):
    return get("level3_defaults")[segment]["bF"]


@dataclass
class GlobalResult:
    years: list
    world: dict                      # year -> world O&D (m pax)
    by_region: dict                  # region -> {year: m pax}  (destination region of travel)
    by_airport_last: dict            # iata -> last-year terminal O&D (m)
    world_cagr: float
    meta: dict = field(default_factory=dict)


def run_global(scenario="Baseline", base_od=None, airport_meta=None, years=None, use_propensity=True):
    base_od = base_od or _load("global_base_od_2025.json")
    meta = airport_meta or _load("global_airport_meta_2025.json")
    wb = _load("worldbank_pop_gdppc.json")["data"]
    base_year = get("meta.base_year")
    years = years or list(range(base_year, base_year + get('meta.horizon_years', 35) + 1))
    fare = _fare_index(years)
    term_log = np.log(1.0 + get("propensity.terminal_tpc_growth"))
    pop_growth = get("population.growth_by_region")

    # country totals for propensity (trips per capita)
    country_od = {}
    for iata, regs in base_od.items():
        c = meta[iata]["country"]
        country_od[c] = country_od.get(c, 0.0) + sum(regs.values())

    # per-country propensity headroom series (only where population known)
    head_cache = {}
    def country_headroom(country, region):
        if country in head_cache:
            return head_cache[country]
        rec = wb.get(country)
        if not (rec and rec.get("pop") and rec.get("gdp_pc_ppp")):
            head_cache[country] = None
            return None
        g = get("global_drivers.gdp_growth_by_region").get(region, 0.02)
        pg = pop_growth.get(region, 0.005)
        pop = {y: rec["pop"] * ((1 + pg) ** (y - base_year)) for y in years}
        gdp_pc = {y: (100.0 * (1 + g) ** (y - base_year)) * pop[years[0]] / pop[y] for y in years}
        base_total_pax = country_od[country] * 1e6
        path = pr.evolve(base_total_pax, pop, gdp_pc, pr.asymptote_for(region), years)
        h = [max(0.0, 1.0 - path.saturation[y]) for y in years]
        head_cache[country] = h
        return h

    by_region = {}
    world = {y: 0.0 for y in years}
    by_airport_last = {}
    by_airport_index = {}       # iata -> total O&D growth index (base year = 1.0)
    by_airport_intl_index = {}  # iata -> international O&D growth index (base year = 1.0)

    for iata, regs in base_od.items():
        m = meta[iata]
        country, a_region = m["country"], m["region"]
        maturity = _maturity(country, a_region, wb)
        G = _gdp_index(a_region, years, country, scenario)
        bG_est = _est_bG().get(country) if get("global_drivers.use_estimated_elasticities", False) else None
        head = country_headroom(country, a_region) if use_propensity else None
        term_last = 0.0
        ap_tot = [0.0] * len(years)
        ap_intl = [0.0] * len(years)
        for r, od0 in regs.items():
            if od0 <= 0:
                continue
            seg = SEGMENT[r]
            bG = bG_est if bG_est is not None else _bG(seg, maturity)
            bG = _clamp_bG(bG)   # applied elasticity stays inside the book bound (Method Spec 4.3)
            bF, F = _bF(seg), fare[seg]
            if head is not None:
                series = demand.od_recursion_damped(od0, G, F, bG, bF, head, term_log)
            else:
                series = demand.od_recursion(od0, G, F, bG, bF)
            br = by_region.setdefault(r, {y: 0.0 for y in years})
            for i, y in enumerate(years):
                br[y] += series[i]
                world[y] += series[i]
                ap_tot[i] += series[i]
                if r != "Domestic":
                    ap_intl[i] += series[i]
            term_last += series[-1]
        by_airport_last[iata] = round(term_last, 4)
        if ap_tot[0] > 0:
            by_airport_index[iata] = [v / ap_tot[0] for v in ap_tot]
        if ap_intl[0] > 0:
            by_airport_intl_index[iata] = [v / ap_intl[0] for v in ap_intl]

    y0, y1 = years[0], years[-1]
    world_cagr = (world[y1] / world[y0]) ** (1.0 / (y1 - y0)) - 1.0
    return GlobalResult(years, world, by_region, by_airport_last, world_cagr,
                        meta={"scenario": scenario, "n_airports": len(base_od),
                              "propensity": use_propensity,
                              "by_airport_index": by_airport_index,
                              "by_airport_intl_index": by_airport_intl_index})

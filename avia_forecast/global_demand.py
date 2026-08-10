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
from . import paths
from .paths import OEF_DIR, ACI_DIR, ACI_DECRYPT, SABRE_DB, OAG_DB, QSI_REF, PREAGG, QSI_APP, OEF_GDP_XLSX
from dataclasses import dataclass, field
import json, os, sys

import numpy as np

from .config import get
from .demand import core as demand
from .estimate import propensity as pr

# TWO data folders, named apart on purpose. This module imported DATA from paths (the
# Global folder on E:) and then, eleven lines later, rebound the same name to the repo's
# own data folder. E_DATA was set from the rebound name, so the three external files
# below were looked for inside the repository, were not there, and each load caught the
# error and returned an empty dictionary. Every country ran on the default income
# elasticity and the regional GDP default while the code read as though it did not.
# Found 8 August 2026. Do not collapse these two names back into one.
REPO_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
E_DATA = paths.DATA          # E:\Avia\Global\data, or AVIA_GLOBAL_ROOT\data

SEGMENT = {r: ("Domestic" if r == "Domestic" else
              ("International Short Haul" if r in ("EU+UK", "Other Europe") else "Long Haul"))
           for r in ["Domestic", "EU+UK", "Other Europe", "Africa", "Middle East",
                     "Asia Pacific", "North America", "South America"]}

ALLOW_MISSING = os.environ.get("AVIA_ALLOW_MISSING_DATA") == "1"
DEGRADED: list[str] = []


def _load(name):
    """A file that ships with the code, from the repository's own data folder."""
    return json.load(open(os.path.join(REPO_DATA, name)))


def _load_external(name, what):
    """A staged data file from the Global folder. Missing means the run is not the run
    the caller thinks it is, so say which file, where it was looked for and what is lost,
    and stop. Set AVIA_ALLOW_MISSING_DATA=1 for a deliberate degraded run; it is recorded
    in DEGRADED and printed, so no output leaves without it being visible."""
    fp = os.path.join(E_DATA, name)
    if os.path.isfile(fp):
        return json.load(open(fp))
    msg = (f"{name} not found at {fp}. Without it, {what}. "
           f"The Global root resolved to {paths.GLOBAL}; set AVIA_GLOBAL_ROOT if that is "
           f"not where the data is. Run check_env.py for the full list.")
    if not ALLOW_MISSING:
        raise FileNotFoundError(msg)
    DEGRADED.append(f"{name}: {what}")
    print("DEGRADED RUN: " + msg, file=sys.stderr)
    return None


_OEF_GDP = None
_EST_BG = None


def _est_bG():
    """Per-country estimated income elasticity, reliable countries only."""
    global _EST_BG
    if _EST_BG is None:
        raw = _load_external("estimated_bG_by_country.json",
                             "every country runs on the default income elasticity rather "
                             "than its own estimate")
        _EST_BG = {k: v["bG"] for k, v in raw.items() if v.get("reliable")} if raw else {}
    return _EST_BG


def _oef_gdp():
    """Per-country OEF GDP, constant prices, history and forecast."""
    global _OEF_GDP
    if _OEF_GDP is None:
        raw = _load_external("oef_gdp_pop_by_iso2.json",
                             "the forecast runs on the regional GDP growth default rather "
                             "than the Oxford Economics country forecast")
        _OEF_GDP = raw["gdp"] if raw else {}
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
    """Kept as the binary reading, for anything that wants the label rather than the
    weight. The forecast reads _maturity_weight."""
    return "mature" if _maturity_weight(country, region, wb) >= 0.5 else "emerging"


def _maturity_weight(country, region, wb, trips_pc=None):
    """How mature a market is, on a 0 to 1 scale, where 1 takes the full mature
    elasticity and 0 the full emerging one.

    Two bases, and the choice is stated in the assumptions book rather than left to code.

    income_threshold, as it ran until 9 August 2026, is a cliff: at or above
    maturity_gdppc_threshold_usd a country takes the mature elasticity and below it the
    emerging one, with nothing in between. China sits at 29,333 international dollars
    against a threshold of 25,000 and roughly 0.4 trips per capita, so half of Chinese
    traffic, the 294m of O&D at airports with no fit of their own, carried a domestic
    income elasticity of 1.0 rather than 1.5. China is a mature air travel market on the
    income measure and on no other. Mexico at 25,868 and Thailand at 26,250 sit the same
    wrong side of the same cliff while Brazil at 23,433 sits the right side of it.

    saturation reads maturity off behaviour instead: how far up its own propensity curve
    a country already is, trips per capita against the regional asymptote the propensity
    module already applies. It is continuous, so there is no cliff, and it uses a quantity
    the model computes anyway. See MEASUREMENTS.md section 8.
    """
    basis = get("global_drivers.maturity_basis", "income_threshold")
    if basis == "saturation" and trips_pc is not None:
        asym = pr.asymptote_for(region)
        return max(0.0, min(1.0, trips_pc / asym)) if asym else 0.0
    thr = get("global_drivers.maturity_gdppc_threshold_usd")
    rec = wb.get(country)
    if rec and rec.get("gdp_pc_ppp"):
        return 1.0 if rec["gdp_pc_ppp"] >= thr else 0.0
    return 1.0 if region in get("global_drivers.mature_regions_default") else 0.0


def _bG(segment, maturity):
    """Income elasticity for a segment. `maturity` is either the label, for the binary
    reading, or a weight between 0 and 1, in which case the elasticity interpolates
    between the emerging and the mature value rather than jumping between them."""
    d = get("level3_defaults")[segment]
    if isinstance(maturity, str):
        return d["bG_mature"] if maturity == "mature" else d["bG_emerging"]
    w = max(0.0, min(1.0, float(maturity)))
    return d["bG_emerging"] + w * (d["bG_mature"] - d["bG_emerging"])


def _clamp_bG(bG):
    """Applied income elasticity stays inside the book bound (Method Spec 4.3); defends
    against out-of-band country estimates until they are re-estimated on O&D [P1]."""
    lo, hi = get("global_drivers.bG_applied_bounds", [0.6, 2.2])
    return max(lo, min(hi, bG))


_AIR_REG = None
_AIR_CX = None


def _airport_regress():
    """Per-airport regression. This file is excluded from the repository by .gitignore,
    so a fresh clone will not have it and the run must say so rather than proceed with
    nothing."""
    global _AIR_REG
    if _AIR_REG is None:
        fp = os.path.join(REPO_DATA, "airport_regress.json")
        if os.path.isfile(fp):
            _AIR_REG = json.load(open(fp))
        else:
            msg = (f"airport_regress.json not found at {fp}. Without it no airport uses "
                   f"its own fitted elasticity. The file is gitignored, so a clone does "
                   f"not carry it: regenerate it with scripts/estimate_airport_diagnostics.py "
                   f"or copy it from a machine that has it.")
            if not ALLOW_MISSING:
                raise FileNotFoundError(msg)
            DEGRADED.append("airport_regress.json: no airport uses its own fitted elasticity")
            print("DEGRADED RUN: " + msg, file=sys.stderr)
            _AIR_REG = {}
    return _AIR_REG


def _airport_cx():
    global _AIR_CX
    if _AIR_CX is None:
        cal = _load_external("aci_hub_calibration_2024.json",
                             "no airport carries a connecting share, so every airport is "
                             "treated as pure origin and destination")
        _AIR_CX = {k: v.get("connecting_share") for k, v in cal.items()} if cal else {}
    return _AIR_CX


def _airport_applied_bG(iata):
    """An airport's OWN estimate is applied only when it passes reliability AND its connecting share
    is low enough that terminal ~ O&D (so the terminal-panel fit is not hub-development contamination).
    Hubby airports fall back to the country value until the O&D re-estimation lands [P1]."""
    if not get("global_drivers.use_airport_elasticities", True):
        return None
    r = _airport_regress().get(iata)
    if not r or not r.get("reliable"):
        return None
    cx = _airport_cx().get(iata)
    if cx is not None and cx > get("global_drivers.airport_elasticity_max_cx", 0.25):
        return None
    return _clamp_bG(r["bG_est"])


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

    _RMAP = {"EU+UK": "Europe", "Other Europe": "Europe", "Africa": "Africa", "Middle East": "Middle East",
             "Asia Pacific": "Asia Pacific", "North America": "North America", "South America": "South America"}
    _both = get("global_drivers.both_ends_gdp", True)
    _reg_cache = {}
    def _reg_index(rr):
        if rr not in _reg_cache:
            _reg_cache[rr] = _gdp_index(_RMAP.get(rr, rr), years, None, scenario)
        return _reg_cache[rr]

    for iata, regs in base_od.items():
        m = meta[iata]
        country, a_region = m["country"], m["region"]
        # Trips per capita on the same basis the propensity ceiling uses, so the maturity
        # weight and the saturation damping cannot disagree about where a country sits.
        _pop = (wb.get(country) or {}).get("pop")
        _tpc = (country_od.get(country, 0.0) * 1e6 / _pop) if _pop else None
        maturity = _maturity_weight(country, a_region, wb, _tpc)
        G = _gdp_index(a_region, years, country, scenario)
        bG_est = _est_bG().get(country) if get("global_drivers.use_estimated_elasticities", False) else None
        air_bG = _airport_applied_bG(iata)   # airport-own elasticity where earned (reliable + low connecting share)
        head = country_headroom(country, a_region) if use_propensity else None
        term_last = 0.0
        ap_tot = [0.0] * len(years)
        ap_intl = [0.0] * len(years)
        for r, od0 in regs.items():
            if od0 <= 0:
                continue
            seg = SEGMENT[r]
            bG = air_bG if air_bG is not None else (bG_est if bG_est is not None else _bG(seg, maturity))
            bG = _clamp_bG(bG)   # applied elasticity stays inside the book bound (Method Spec 4.3)
            bF, F = _bF(seg), fare[seg]
            Gcell = G
            if _both and r != "Domestic":                       # gravity: grow on BOTH ends' GDP (per-direction driver)
                Gd = _reg_index(r)
                Gcell = [(G[i] * Gd[i]) ** 0.5 for i in range(len(years))]
            if head is not None:
                series = demand.od_recursion_damped(od0, Gcell, F, bG, bF, head, term_log)
            else:
                series = demand.od_recursion(od0, Gcell, F, bG, bF)
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

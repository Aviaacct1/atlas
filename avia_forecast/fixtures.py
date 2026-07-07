"""UK pilot fixture: a real UK airport set with real catchments, driving the
end-to-end orchestration. Numbers are illustrative until the CAA base-year O&D is
ingested (see build_base_od_from_caa, the real-data seam); the airport list,
catchments and structure are real.

LHR is the connecting hub; the other airports route a fixed share of their
long-haul finals via LHR, which generates LHR's connecting base so the base-year
identities (T-A row-stochastic, T-F off-diagonal mass = connecting base) hold by
construction. Author: Avia Solutions.
"""
from __future__ import annotations
from dataclasses import dataclass, field

REGIONS = ["Domestic", "EU+UK", "Other Europe", "Africa", "Middle East",
           "Asia Pacific", "North America", "South America"]
SHORT = {"EU+UK", "Other Europe"}
LONG = {"Africa", "Middle East", "Asia Pacific", "North America", "South America"}
YEARS = list(range(2025, 2051))
BASE = 2025
VIA_HUB_SHARE = 0.35                      # feeder long-haul share routed via LHR

SEGMENT = {r: ("Domestic" if r == "Domestic" else
               "International Short Haul" if r in SHORT else "Long Haul") for r in REGIONS}
DIST = {"Domestic": 400, "EU+UK": 800, "Other Europe": 1500, "Africa": 6000,
        "Middle East": 5000, "Asia Pacific": 9000, "North America": 6500, "South America": 9500}


@dataclass
class Airport:
    iata: str
    name: str
    hub: bool
    catchment: str
    K: float                              # terminal capacity (m pax)
    base_od: dict                         # region -> base-year outbound O&D (m pax)
    bG: float


@dataclass
class Pilot:
    airports: list
    catchments: dict
    regions: list = field(default_factory=lambda: list(REGIONS))
    years: list = field(default_factory=lambda: list(YEARS))
    base: int = BASE
    home_region: str = "EU+UK"
    dist: dict | None = None                # optional {iata: {region: km}} from OAG; else DIST
    bF: dict = field(default_factory=lambda: {"Domestic": -0.7,
                                              "International Short Haul": -0.7, "Long Haul": -0.5})

    def hub_iata(self):
        return next(a.iata for a in self.airports if a.hub)

    def feeders(self):
        return [a for a in self.airports if not a.hub]


# region order: Dom, EU+UK, OthEur, Africa, ME, AP, NA, SA
def _od(dom, eu, oe, af, me, ap, na, sa):
    return dict(zip(REGIONS, [dom, eu, oe, af, me, ap, na, sa]))


_UK = [
    # iata, name,          hub,  catchment,     K,   base_od,                                   bG
    ("LHR", "Heathrow",    True, "London",     52, _od(1.0, 14, 3.0, 2.0, 4.0, 6.0, 8.0, 2.0), 1.33),
    ("LGW", "Gatwick",     False,"London",     30, _od(1.0, 12, 3.0, 1.0, 1.0, 1.0, 3.0, 1.0), 1.25),
    ("STN", "Stansted",    False,"London",     22, _od(1.0, 12, 2.0, 0.3, 0.5, 0.2, 0.3, 0.1), 1.2),
    ("LTN", "Luton",       False,"London",     18, _od(0.5,  7, 1.5, 0.1, 0.2, 0.1, 0.2, 0.1), 1.2),
    ("LCY", "London City", False,"London",      6, _od(0.3, 2.5,0.3, 0.0, 0.1, 0.0, 0.2, 0.0), 1.3),
    ("MAN", "Manchester",  False,"Manchester",  30, _od(1.5,  9, 2.0, 0.5, 1.5, 1.0, 2.0, 0.3), 1.25),
    ("BHX", "Birmingham",  False,"Birmingham",  14, _od(1.0,  5, 1.0, 0.2, 0.7, 0.3, 0.3, 0.1), 1.2),
    ("EDI", "Edinburgh",   False,"Edinburgh",   16, _od(2.0,  5, 1.0, 0.1, 0.2, 0.2, 0.7, 0.1), 1.2),
]


def gdp_index(scenario: str = "Baseline") -> dict:
    """Home-market (UK) real GDP index from OEF March 2026; outbound demand uses
    home GDP (4.1). OEF Base/Low/High map to the scenarios; the last OEF rate is
    held beyond its horizon (long-run assumption)."""
    from .config import _load
    uk = _load("oef_gdp.yaml")["uk"]
    growth = uk.get(scenario, uk["Baseline"])
    last = growth[max(growth)]
    idx, lvl = {}, 100.0
    for y in YEARS:
        if y > BASE:
            lvl *= (1.0 + growth.get(y, last))
        idx[y] = lvl
    return idx


def fare_index() -> dict:
    """Cost-driven real fare index (Method Spec 4.2), constructed from the real EIA
    jet-fuel series; rebased to base year = 100 over the pilot horizon. Replaces the
    earlier 0.997^t placeholder. Author: Avia Solutions."""
    import json, os
    path = os.path.join(os.path.dirname(__file__), "..", "data", "fare_index_constructed.json")
    raw = json.load(open(path))
    out = {}
    for seg, series in raw.items():
        b = series[str(BASE)]
        out[seg] = {y: series[str(y)] / b * 100.0 for y in YEARS if str(y) in series}
    return out


def feeder_M(_iata) -> dict:
    """Feeder final-to-next: long-haul finals route VIA_HUB_SHARE via LHR (an
    EU+UK first leg); everything else direct. Rows sum to 1."""
    M = {r: {c: 0.0 for c in REGIONS} for r in REGIONS}
    for r in REGIONS:
        if r in LONG:
            M[r][r] = 1.0 - VIA_HUB_SHARE
            M[r]["EU+UK"] += VIA_HUB_SHARE
        else:
            M[r][r] = 1.0
    return M


def hub_M() -> dict:
    return {r: {c: (1.0 if r == c else 0.0) for c in REGIONS} for r in REGIONS}


def make_pilot(base_od_override: dict | None = None, k_override: dict | None = None,
               dist: dict | None = None) -> Pilot:
    """Build the UK pilot. base_od_override ({iata:{region: m pax}}, e.g. from Sabre
    GDD or CAA) replaces the illustrative base-year O&D; k_override ({iata: K})
    replaces capacities; dist ({iata:{region: km}}, e.g. from OAG schedules) sets
    per-airport region distances for RPK. Airport metadata is otherwise kept."""
    airports = []
    for (i, n, h, c, K, od, bG) in _UK:
        od_use = {r: float(base_od_override[i].get(r, 0.0)) for r in REGIONS} \
            if base_od_override and i in base_od_override else dict(od)
        K_use = float(k_override[i]) if k_override and i in k_override else K
        airports.append(Airport(i, n, h, c, K_use, od_use, bG))
    catchments = {}
    for a in airports:
        catchments.setdefault(a.catchment, []).append(a.iata)
    return Pilot(airports=airports, catchments=catchments, dist=dist)


def conx_base_hub(pilot: Pilot) -> dict:
    """LHR base-year connecting by onward region = feeders' long-haul routed via
    LHR, so the base-year T-F identity holds by construction."""
    out = {r: 0.0 for r in LONG}
    for a in pilot.feeders():
        for r in LONG:
            out[r] += VIA_HUB_SHARE * a.base_od[r]
    return out


def build_base_od_from_tidy(od_tidy, iatas, base_year: int = BASE, to_millions: bool = True):
    """Real-data seam: build {iata: {region: base-year outbound O&D}} from any tidy
    O&D source in the contract (metric od_pax, direction out), Sabre GDD or CAA.
    Sabre GDD is class C and used here only to seed base-year parameters
    (Data Architecture 4.2). Author: Avia Solutions."""
    df = od_tidy[(od_tidy["metric"] == "od_pax") & (od_tidy["direction"] == "out")
                 & (od_tidy["year"] == base_year)]
    scale = 1e6 if to_millions else 1.0
    return {iata: {r: float(df[(df["iata"] == iata) & (df["dest_region"] == r)]["value"].sum()) / scale
                   for r in REGIONS} for iata in iatas}


# backward-compatible alias
def build_base_od_from_caa(caa_tidy, iatas):
    return build_base_od_from_tidy(caa_tidy, iatas)


def population_series(iso2: str, years):
    """Real UN WPP 2024 medium-variant population (persons) for a country over
    `years`, from build/data/un_wpp_population.json. Years beyond the file hold the
    last value; missing countries return None. Author: Avia Solutions."""
    import json, os
    path = os.path.join(os.path.dirname(__file__), "..", "data", "un_wpp_population.json")
    pop = json.load(open(path))
    c = pop.get(iso2)
    if not c:
        return None
    ymax = max(int(y) for y in c)
    return {y: c[str(min(y, ymax))] for y in years}


def propensity_demand_path(base_total: float, scenario: str, years, iso2="GB", region="EU+UK"):
    """System demand multiplier path (vs base year) with propensity saturation
    (Cockpit B1 wired into demand). Uses real UN population, OEF GDP per capita and
    the fitted world-curve income elasticity; growth above the mature rate is damped
    by remaining headroom, so mature markets bend down over the horizon.
    Author: Avia Solutions."""
    from .estimate import propensity as pr
    pop = population_series(iso2, years)
    gdp = gdp_index(scenario)
    pop0 = pop[years[0]]
    gdp_pc = {y: gdp[y] * pop0 / pop[y] for y in years}      # real GDP per capita index
    path = pr.evolve(base_total * 1e6, pop, gdp_pc, pr.asymptote_for(region), years)  # m pax -> persons
    t0 = path.traffic[years[0]]
    return {y: path.traffic[y] / t0 for y in years}


def propensity_headroom_series(base_total: float, scenario: str, years, iso2="GB", region="EU+UK"):
    """Saturation headroom (1 - s) per year from estimate.propensity.evolve, at
    country grain (the documented fallback until per-catchment populations exist,
    Fable review). Used to damp the per-cell income growth. Author: Avia Solutions."""
    from .estimate import propensity as pr
    pop = population_series(iso2, years)
    gdp = gdp_index(scenario); pop0 = pop[years[0]]
    gdp_pc = {y: gdp[y] * pop0 / pop[y] for y in years}
    path = pr.evolve(base_total * 1e6, pop, gdp_pc, pr.asymptote_for(region), years)
    return {y: max(0.0, 1.0 - path.saturation[y]) for y in years}


# UK catchment-group populations (resident, for saturation). [P1] - the QSI catchment
# engine (app/catchment.py: locale population x propensity, allocated by generalised
# cost) supplies precise per-catchment populations for the real build.
UK_CATCHMENT_POP = {"London": 22.0e6, "Manchester": 7.0e6, "Birmingham": 6.0e6, "Edinburgh": 4.5e6}


def catchment_headroom_series(pilot, scenario, years, region="EU+UK"):
    """Per-catchment saturation headroom (1 - s) per year (Fable P1.3). Each
    catchment's trips per capita is its member airports' O&D over its resident
    population; growth above the mature floor is damped by that catchment's own
    headroom, so mature metros (London) decelerate faster than growth catchments
    (Manchester). Author: Avia Solutions."""
    from .estimate import propensity as pr
    pop_nat = population_series("GB", years); pop0 = pop_nat[years[0]]
    gdp = gdp_index(scenario)
    gdp_pc = {y: gdp[y] * pop0 / pop_nat[y] for y in years}
    out = {}
    for cname, iatas in pilot.catchments.items():
        base_od_m = sum(a.base_od[r] for a in pilot.airports if a.iata in iatas for r in pilot.regions)
        cpop0 = UK_CATCHMENT_POP.get(cname, 5.0e6)
        cpop = {y: cpop0 * (pop_nat[y] / pop0) for y in years}       # grow at national rate
        path = pr.evolve(base_od_m * 1e6, cpop, gdp_pc, pr.asymptote_for(region), years)
        out[cname] = {y: max(0.0, 1.0 - path.saturation[y]) for y in years}
    return out


# --- Residual pseudo-airport (Phase 1 scope; Method Spec airport-set rule) ---
def residual_airport(country: str, below: list, suffix: str | None = None) -> "Airport":
    """Collapse the below-scope airports of one country into a single residual
    pseudo-airport so national totals stay whole. Its base O&D is the element-wise
    sum of the members' base O&D; its bG is their pax-weighted average; it carries
    no capacity (K=0, always unconstrained) and its own catchment so it does not
    distort a real metro's saturation. Author: Avia Solutions."""
    from .config import get as _get
    suf = _get("scope.residual_pseudo_suffix") if suffix is None else suffix
    summed = {r: float(sum(a.base_od.get(r, 0.0) for a in below)) for r in REGIONS}
    tot = sum(sum(a.base_od.values()) for a in below)
    bG = (sum(sum(a.base_od.values()) * a.bG for a in below) / tot) if tot > 0 else 1.2
    return Airport(country + suf, "Residual " + country, False,
                   country + "_RES", 0.0, summed, bG)


def partition_by_scope(airports: list, country: str = "GB", **kw):
    """Apply John's airport-set rule to a country's airports (Phase 1). Returns
    (modelled, residual_or_None). pax per airport = sum of its base O&D across
    regions. Modelled airports are returned unchanged; the rest fold into one
    residual pseudo-airport. Author: Avia Solutions."""
    from .scope import selection as sc
    pax = [(a.iata, sum(a.base_od.values())) for a in airports]
    res = sc.select_country(country, pax, **kw)
    keep = {a.iata for a in res.modelled}
    modelled = [a for a in airports if a.iata in keep]
    below = [a for a in airports if a.iata not in keep]
    return modelled, (residual_airport(country, below) if below else None)


def apply_scope(pilot: "Pilot", country: str = "GB", **kw) -> "Pilot":
    """Return a new pilot whose airport set is scoped: below-scope airports replaced
    by one residual pseudo-airport, national totals preserved. Catchments (and dist,
    if present) are extended to carry the residual. Author: Avia Solutions."""
    modelled, residual = partition_by_scope(pilot.airports, country, **kw)
    airports = list(modelled) + ([residual] if residual else [])
    catchments = {}
    for a in airports:
        catchments.setdefault(a.catchment, []).append(a.iata)
    dist = None
    if pilot.dist is not None:
        dist = dict(pilot.dist)
        if residual is not None:
            dist[residual.iata] = {r: DIST[r] for r in REGIONS}   # residual uses default region distances
    return Pilot(airports=airports, catchments=catchments, dist=dist,
                 regions=list(pilot.regions), years=list(pilot.years),
                 base=pilot.base, home_region=pilot.home_region, bF=dict(pilot.bF))

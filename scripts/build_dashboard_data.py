"""Engine extract for the global Dashboard mockup. Produces real per-airport pax series
(ACI history 2015-2024 + engine forecast to the vintage horizon) across scenarios, country metadata,
region-pair O&D flows and region growth, mapped to the dashboard's 6-region scheme.
The dashboard derives RPK/ASK/ATM/CO2/fleet from these pax. Author: Avia Solutions."""
from __future__ import annotations
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from avia_forecast.global_checks import reconcile_levels, assert_adds_up
from avia_forecast.io_safe import dump_atomic
from avia_forecast.paths import DATA, OEF_DIR, ACI_DIR, ACI_DECRYPT, SABRE_DB, OAG_DB, QSI_REF, PREAGG, QSI_APP, OEF_GDP_XLSX
import csv, json, os, sys
from collections import defaultdict
import duckdb, openpyxl
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from avia_forecast import global_terminal as gt
from avia_forecast.geo.regions_iso2 import region_for_iso2

E = DATA
QSI = QSI_APP
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webapp", "data")
SCEN = ["Baseline", "High", "Low"]
HIST0, BASE = 2015, 2025
HORIZON = BASE + 35
YRS = list(range(HIST0, HORIZON + 1))
# 8-region engine -> 6-region dashboard
R6 = {"EU+UK": "Europe", "Other Europe": "Europe", "Asia Pacific": "Asia Pacific",
      "North America": "North America", "South America": "South America",
      "Middle East": "Middle East", "Africa": "Africa"}


def r6(iso): return R6.get(region_for_iso2(iso) or "", None)


def aci_names_and_history():
    names = {}
    hist = defaultdict(dict)          # iata -> {year: terminal_m}
    long = json.load(open(os.path.join(E, "aci_panel_long.json")))
    for r in long:
        if r["terminal_pax"] and HIST0 <= r["year"] <= 2024:
            hist[r["iata"]][r["year"]] = r["terminal_pax"] / 1e6
    try:
        wb = openpyxl.load_workbook(os.path.join(E, "aci_decrypted", "aci_2024.xlsx"), read_only=True, data_only=True)
        ws = wb["Annual 2024 dataset"]
        rows = ws.iter_rows(min_row=1, values_only=True)
        hdr = next(rows)
        idx = {str(h).strip().lower(): i for i, h in enumerate(hdr) if h}
        ic, ina = idx.get("iata code"), idx.get("airport name")
        for row in rows:
            code = str(row[ic]).strip().upper() if ic is not None and row[ic] else ""
            if len(code) == 3 and ina is not None and row[ina]:
                names.setdefault(code, str(row[ina]).strip())
        wb.close()
    except Exception as e:
        print("name extract skipped:", e)
    return names, hist


def region_pair_flows():
    con = duckdb.connect(os.path.join(QSI, "preagg.duckdb"), read_only=True)
    rows = con.execute("select o,d,pax from od_p2p where year=2024").fetchall(); con.close()
    apc = {}
    for row in csv.DictReader(open(os.path.join(QSI, "reference_tables", "airport_city_country.csv"), encoding="utf-8-sig")):
        apc[row["airport_code"].strip()] = row["country_code"].strip()
    flow = defaultdict(float)
    for o, d, pax in rows:
        ro, rd = r6(apc.get(o)), r6(apc.get(d))
        if ro and rd:
            flow["|".join(sorted([ro, rd]))] += pax / 1e6   # m O&D pax by region pair
    # Convert to RPK (bn) with a representative one-way great-circle stage length per region pair,
    # so the matrix reports what its title says (RPK, not pax) and thin long-haul markets (e.g. South
    # America to Asia/Africa/Middle East) are visible rather than rounding to zero. Distances are
    # representative averages [P1]; RPK_bn = pax_m * km / 1000.
    RD = {
        "Africa|Africa":1800,"Asia Pacific|Asia Pacific":2600,"Europe|Europe":1100,
        "Middle East|Middle East":1500,"North America|North America":1900,"South America|South America":2000,
        "Africa|Europe":5500,"Africa|Middle East":4500,"Africa|Asia Pacific":9000,
        "Africa|North America":11500,"Africa|South America":8000,
        "Asia Pacific|Europe":8500,"Asia Pacific|Middle East":5500,"Asia Pacific|North America":10500,
        "Asia Pacific|South America":17000,"Europe|Middle East":4500,"Europe|North America":6500,
        "Europe|South America":9500,"Middle East|North America":11000,"Middle East|South America":12000,
        "North America|South America":6500,
    }
    out = {}
    for k, pax_m in flow.items():
        km = RD.get(k)
        if km is None:
            continue
        out[k] = round(pax_m * km / 1000.0, 1)   # RPK bn, base year
    return out


def per_airport_dests(topn=14):
    """For each origin airport, its real destination MARKETS (countries) from Sabre O&D 2024,
    with base-year demand (m pax). Domestic collapsed to one 'Domestic <country>' market."""
    con = duckdb.connect(os.path.join(QSI, "preagg.duckdb"), read_only=True)
    rows = con.execute("select o,d,pax from od_p2p where year=2024").fetchall(); con.close()
    apc, name = {}, {}
    for row in csv.DictReader(open(os.path.join(QSI, "reference_tables", "airport_city_country.csv"), encoding="utf-8-sig")):
        apc[row["airport_code"].strip()] = row["country_code"].strip()
        name[row["country_code"].strip()] = row["country_name"].strip()
    agg = defaultdict(lambda: defaultdict(float))     # origin -> dest_iso -> pax
    for o, d, pax in rows:
        di = apc.get(d)
        if o and di:
            agg[o][di] += pax
    out = {}
    for o, dd in agg.items():
        oi = apc.get(o)
        items = []
        for di, pax in dd.items():
            reg = r6(di)
            if not reg and di != oi:
                continue
            dom = (di == oi)
            mkt = ("Domestic " + name.get(oi, oi)) if dom else name.get(di, di)
            items.append({"market": mkt, "iso": di, "region": reg, "dom": dom, "d": round(pax / 1e6, 4)})
        items.sort(key=lambda x: -x["d"])
        out[o] = items[:topn]
    return out


def run():
    names, hist = aci_names_and_history()
    qref = {}
    for row in csv.DictReader(open(os.path.join(QSI, "reference_tables", "airport_city_country.csv"), encoding="utf-8-sig")):
        qref[row["airport_code"].strip()] = (row["city_name"].strip(), row["country_name"].strip())

    # engine forecast per airport per scenario
    fc = {}
    fyears = None
    for sc in SCEN:
        r = gt.run_terminal(scenario=sc)
        fyears = r.years
        for iata, a in r.by_airport.items():
            fc.setdefault(iata, {"a": a})["a"] = a
            fc[iata].setdefault("scen", {})[sc] = dict(zip((int(y) for y in fyears), a["series"]))

    # domestic share + gdppc/pop from ACI + OEF/WB
    panel24 = [r for r in json.load(open(os.path.join(E, "aci_panel_2013_2024.json"))) if r["year"] == 2024]
    dom = defaultdict(lambda: [0.0, 0.0])
    for r in panel24:
        if r["country_code"] and r["terminal_pax"]:
            dom[r["country_code"]][0] += (r.get("domestic") or 0.0)
            dom[r["country_code"]][1] += r["terminal_pax"]
    wb = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "worldbank_pop_gdppc.json")))["data"]
    oefp = json.load(open(os.path.join(E, "oef_gdp_pop_by_iso2.json")))["pop"]

    DESTS = per_airport_dests()
    perAirport, CTY = {}, {}
    for iata, d in fc.items():
        a = d["a"]; iso = a["country"]; reg = R6.get(a["region"])
        if not reg:
            continue
        city, ctry = qref.get(iata, ("", iso))
        # full series per scenario: ACI history (shared) then engine forecast
        h = hist.get(iata, {})
        scen = {}
        for sc in SCEN:
            s = []
            for y in YRS:
                if y < BASE and y in h:
                    s.append(round(h[y], 3))
                elif y in d["scen"][sc]:
                    s.append(d["scen"][sc][y])
                else:
                    s.append(None)
            # fill leading gaps by back-projecting from first known point
            first = next((v for v in s if v is not None), None)
            s = [first if v is None else v for v in s]
            scen[sc] = s
        cap = 0
        perAirport[iata] = {"iata": iata, "name": names.get(iata, city or iata),
                            "country": ctry, "region": reg, "cap": cap,
                            "hub": ("Alliance hub" if (a.get("connecting_share") or 0) > 0.30 else ""),
                            "cnx": a.get("connecting_share"), "scen": scen,
                            "dests": DESTS.get(iata, [])}
        if ctry not in CTY:
            popser = oefp.get(iso, {})
            pv = [popser.get(str(y)) for y in (2024, 2050) if popser.get(str(y))]
            popg = ((pv[1] / pv[0]) ** (1 / 26) - 1) if len(pv) == 2 else 0.004
            b = perAirport[iata]  # placeholder; country g computed below
            CTY[ctry] = {"r": reg, "iso": iso,
                         "dom": round(dom[iso][0] / dom[iso][1], 3) if dom[iso][1] else 0.3,
                         "gdppc": round((wb.get(iso, {}).get("gdp_pc_ppp") or 0) / 1000, 1),
                         "pop": round((popser.get("2024") or 0) / 1e6, 0), "popg": round(popg, 4)}

    # country traffic CAGR (Baseline)
    ctry_tot = defaultdict(lambda: [0.0, 0.0])
    for p in perAirport.values():
        ctry_tot[p["country"]][0] += p["scen"]["Baseline"][YRS.index(BASE)]
        ctry_tot[p["country"]][1] += p["scen"]["Baseline"][-1]
    for c, v in CTY.items():
        t = ctry_tot[c]
        v["g"] = round((t[1] / t[0]) ** (1 / (HORIZON - BASE)) - 1, 4) if t[0] > 0 else 0.03

    # region growth (Baseline CAGR)
    reg_tot = defaultdict(lambda: [0.0, 0.0])
    for p in perAirport.values():
        reg_tot[p["region"]][0] += p["scen"]["Baseline"][YRS.index(BASE)]
        reg_tot[p["region"]][1] += p["scen"]["Baseline"][-1]
    RG = {r: round((v[1] / v[0]) ** (1 / (HORIZON - BASE)) - 1, 4) for r, v in reg_tot.items() if v[0] > 0}

    os.makedirs(OUT, exist_ok=True)
    # --- grossing coverage factors (engine-owned; documented) and the adding-up check ---
    _bi = YRS.index(BASE)
    _abyc = {}
    for _a in perAirport.values():
        _v = (_a.get("scen", {}).get("Baseline") or [])
        _abyc.setdefault(_a["country"], []).append(_v[_bi] if len(_v) > _bi else 0.0)
    _c2r = {c: CTY[c]["r"] for c in CTY if "r" in CTY[c]}
    _modelled_c = {c: sum(v) for c, v in _abyc.items()}
    # Coverage factors from real ACI: country/region totals (ALL airports) over the modelled set,
    # grossing up only (floored at 1.0). Real when the ACI panel is present; documented placeholder otherwise.
    try:
        _panel = json.load(open(os.path.join(E, "aci_panel_long.json")))
        _latest = max(int(r["year"]) for r in _panel if r.get("year"))
        _ctry_aci = defaultdict(float)
        for r in _panel:
            if str(r.get("year")) == str(_latest) and r.get("country_code") and r.get("terminal_pax"):
                _ctry_aci[r["country_code"]] += float(r["terminal_pax"]) / 1e6
        coverage_country = {}
        for c in CTY:
            m, tot = _modelled_c.get(c, 0.0), _ctry_aci.get(c, 0.0)
            coverage_country[c] = round(max(1.0, min(3.0, tot / m)), 3) if (m > 0 and tot > 0) else 1.08
        _reg_aci = defaultdict(float)
        for c, tot in _ctry_aci.items():
            rr = R6.get(region_for_iso2(c) or "", None)
            if rr:
                _reg_aci[rr] += tot
        _modelled_r = defaultdict(float)
        for c in CTY:
            rr = CTY[c].get("r")
            if rr:
                _modelled_r[rr] += _modelled_c.get(c, 0.0) * coverage_country.get(c, 1.0)
        coverage_region = {}
        for rr in set(list(_reg_aci) + list(_modelled_r)):
            mr, tr = _modelled_r.get(rr, 0.0), _reg_aci.get(rr, 0.0)
            coverage_region[rr] = round(max(1.0, min(4.0, tr / mr)), 3) if (mr > 0 and tr > 0) else 1.1
        _cov_source = "ACI-based (country/region total over modelled)"
    except Exception as _e:
        coverage_region = {"Europe": 2.6, "Asia Pacific": 2.2, "North America": 1.35,
                           "South America": 2.2, "Middle East": 1.9, "Africa": 3.4}
        coverage_country = {c: 1.12 for c in CTY}
        _cov_source = "placeholder (ACI panel unavailable: %s)" % type(_e).__name__
        print("coverage: using placeholders -", _e)
    _rec = reconcile_levels(_abyc, coverage_country, coverage_region, _c2r)
    try:
        assert_adds_up(_rec); _ok = True
    except AssertionError as _e:
        _ok = False; print("ADDING-UP CHECK FAILED:", _e)
    print("adding-up: world base-year %.0fm, %d issues, ok=%s" % (_rec["world"], len(_rec["issues"]), _ok))
    dump_atomic({"years": YRS, "base": BASE, "scenarios": SCEN,
               "airports": list(perAirport.values()), "cty": CTY,
               "flows": region_pair_flows(), "rg": RG,
               "coverage_country": coverage_country, "coverage_region": coverage_region,
               "checks": {"adds_up": _ok, "world_base_m": round(_rec["world"], 1), "issues": _rec["issues"][:20], "coverage_source": _cov_source},
               "note": f"Avia engine: ACI history to 2024 + forecast to {HORIZON}; Sabre O&D, OAG routing, OEF GDP. Licensed data, internal.",
               "fixtures": [
                   "Shared v1 cost-driven fare index (fare_index_constructed.json) [P1]",
                   "Applied income elasticities clamped to the book bound; country estimates not yet re-estimated on O&D [P1]",
                   "Illustrative grade-C airport capacity (front-end tiered placeholder; capacity register pending)",
                   "Interregional RPK matrix uses representative region-pair stage lengths [P1]",
                   "Hard-coded UK catchment populations in the pilot [P1]",
                   "Comparator CAGRs illustrative pending R14 published values",
                   "Front-end grossing and RPK/ASK/ATM/CO2 derivation factors pending move into the engine",
               ]},
              os.path.join(OUT, "dashboard.json"))
    print(f"dashboard.json: {len(perAirport)} airports, {len(CTY)} countries, "
          f"{len(RG)} regions, flows {len(region_pair_flows())}")
    print("region growth (Baseline):", RG)


if __name__ == "__main__":
    run()

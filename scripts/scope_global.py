"""Global airport-set scope + catchments (Phase 2/3 seam). Applies John's scope rule
(scope.selection) to the global base-year O&D from ingest_global_base, groups airports
into metropolitan catchments by IATA city code (LON = LHR/LGW/STN/LTN/LCY), and reports
coverage: modelled airports, residual pseudo-airports, and the share of world O&D the
modelled set captures. Author: Avia Solutions.
"""
from __future__ import annotations
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from avia_forecast.io_safe import dump_atomic
from avia_forecast.paths import DATA, OEF_DIR, ACI_DIR, ACI_DECRYPT, SABRE_DB, OAG_DB, QSI_REF, PREAGG, QSI_APP, OEF_GDP_XLSX
import csv, json, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from avia_forecast.scope import selection as sc      # noqa: E402
from avia_forecast.config import get                 # noqa: E402

DEF_QSI = QSI_APP
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def load_city(qsi):
    ref = os.path.join(qsi, "reference_tables", "airport_city_country.csv")
    city = {}
    for row in csv.DictReader(open(ref, encoding="utf-8-sig")):
        city[row["airport_code"].strip()] = row["city_code"].strip()
    return city


def run(year=2025, qsi=DEF_QSI):
    meta = json.load(open(os.path.join(DATA, f"global_airport_meta_{year}.json")))
    city = load_city(qsi)

    # scope rule per country, on outbound O&D as the pax measure
    rows = [(iata, m["country"], m["term_out_m"] * 1e6) for iata, m in meta.items()]
    scoped = sc.select_airports(rows)

    modelled_iatas, residual_countries, goal_gap = set(), 0, 0
    world_pax = sum(p for _, _, p in rows)
    modelled_pax = 0.0
    for country, cs in scoped.items():
        for a in cs.modelled:
            modelled_iatas.add(a.iata)
            modelled_pax += a.pax
        if cs.residual_count:
            residual_countries += 1
        goal_gap += cs.goal_gap_count

    # metropolitan catchments (city code) over the MODELLED set
    catchments = defaultdict(list)
    for iata in modelled_iatas:
        cc = city.get(iata, iata)
        catchments[f"{cc}_{meta[iata]['country']}"].append(iata)
    multi = {k: v for k, v in catchments.items() if len(v) > 1}

    dump_atomic({k: sorted(v) for k, v in catchments.items()}, os.path.join(DATA, f"global_catchments_{year}.json"))
    summary = {
        "year": year,
        "airports_total": len(meta),
        "airports_modelled": len(modelled_iatas),
        "countries": len(scoped),
        "residual_pseudo_airports": residual_countries,
        "catchments_modelled": len(catchments),
        "multi_airport_catchments": len(multi),
        "goal_gap_airports_below_scope_above_500k": goal_gap,
        "world_od_m": round(world_pax / 1e6, 1),
        "modelled_od_m": round(modelled_pax / 1e6, 1),
        "coverage_pct": round(100.0 * modelled_pax / world_pax, 2),
        "inclusion_floor_pax": get("scope.inclusion_floor_pax"),
        "coverage_target": get("scope.national_coverage_target"),
    }
    dump_atomic(summary, os.path.join(DATA, f"global_scope_summary_{year}.json"), indent=2)
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("\nsample metropolitan catchments:")
    for k in ["LON_GB", "NYC_US", "TYO_JP", "PAR_FR", "SAO_BR", "BJS_CN"]:
        if k in catchments:
            print(f"  {k}: {sorted(catchments[k])}")
    return summary


if __name__ == "__main__":
    run()

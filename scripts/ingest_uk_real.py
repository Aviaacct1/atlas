"""Regenerate the real UK pilot from the QSI tool's Sabre + OAG stores.

Base-year O&D  <- Sabre GDD 2025 (preagg.duckdb od_p2p; class C, internal seed).
Region distances <- OAG schedules (qsi_wave_cache.duckdb boards; block-time approx).
Capacities are illustrative pending Jess's capacity register.

Usage:
    python scripts/ingest_uk_real.py --out extract.json

Every path resolves through avia_forecast/paths.py; --qsi remains for a one-off run
against another location. Author: Avia Solutions.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from avia_forecast import fixtures, pipeline, paths
from avia_forecast.outputs import extract as ox
from avia_forecast.config import _load

UK = ["LHR", "LGW", "STN", "LTN", "LCY", "MAN", "BHX", "EDI"]
REGIONS = fixtures.REGIONS
K_ILLUSTRATIVE = {"LHR": 23, "LGW": 18.5, "STN": 14.5, "LTN": 12, "LCY": 3, "MAN": 18, "BHX": 9, "EDI": 11}


def _hours(ft):
    try:
        h, m, s = str(ft).split(":"); return int(h) + int(m) / 60 + int(s) / 3600
    except Exception:
        return None


def build_base_od(qsi: Path, c2r: dict, year=2025):
    con = duckdb.connect(paths.PREAGG, read_only=True)
    con.execute(f"CREATE TEMP TABLE ac AS SELECT * FROM read_csv_auto('{qsi/'reference_tables'/'airport_city_country.csv'}')")
    inlist = ",".join(f"'{a}'" for a in UK)
    rows = con.execute(f"""SELECT p.o, ac.country_name, SUM(p.pax) FROM od_p2p p JOIN ac ON p.d=ac.airport_code
        WHERE p.o IN ({inlist}) AND p.year={year} GROUP BY 1,2""").fetchall()
    con.close()
    base = {a: {r: 0.0 for r in REGIONS} for a in UK}
    for o, cty, pax in rows:
        r = c2r.get(cty)
        if r:
            base[o][r] += pax / 1e6
    return base


def build_dist(qsi: Path, c2r_iso: dict):
    con = duckdb.connect(str(qsi / "qsi_wave_cache.duckdb"), read_only=True)
    rows = con.execute(f"""SELECT dep_airport, arr_country, flying_time, days_of_op FROM boards
        WHERE dep_airport IN ({",".join("'"+a+"'" for a in UK)})""").fetchall()
    con.close()
    acc = {a: {r: [0.0, 0.0] for r in REGIONS} for a in UK}
    for dep, cc, ft, dop in rows:
        r = c2r_iso.get(cc); h = _hours(ft)
        if r is None or h is None:
            continue
        w = sum(ch.strip().isdigit() for ch in str(dop)) or 1
        acc[dep][r][0] += w * h; acc[dep][r][1] += w
    km = lambda hh: max(300.0, 800.0 * hh - 250.0)
    dist = {a: {r: (round(km(acc[a][r][0] / acc[a][r][1])) if acc[a][r][1] else None) for r in REGIONS} for a in UK}
    for r in REGIONS:                                    # fill gaps with the network median
        vals = [dist[a][r] for a in UK if dist[a][r]]
        med = round(sum(vals) / len(vals)) if vals else 3000
        for a in UK:
            dist[a][r] = dist[a][r] or med
    return dist


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qsi", required=True, help="path to the QSI tool app/ folder")
    ap.add_argument("--out", default="Dashboard Extract (UK 2025 real).json")
    args = ap.parse_args()
    qsi = Path(args.qsi)
    c2r = _load("country_region.yaml")["map"]
    # ISO2 -> region via the airport reference joined to the country map
    con = duckdb.connect(paths.PREAGG, read_only=True)
    ac = con.execute(f"SELECT DISTINCT country_code, country_name FROM read_csv_auto('{qsi/'reference_tables'/'airport_city_country.csv'}')").fetchall()
    con.close()
    c2r_iso = {code: c2r[name] for code, name in ac if name in c2r}
    c2r_iso["GB"] = "Domestic"

    base = build_base_od(qsi, c2r)
    dist = build_dist(qsi, c2r_iso)
    pilot = fixtures.make_pilot(base_od_override=base, k_override=K_ILLUSTRATIVE, dist=dist)
    res = pipeline.run(vintage="uk-2025-sabre", scenario="Baseline", pilot=pilot, use_propensity=True)
    ext = ox.build_extract(res, pilot)
    ext["meta"]["note"] = "Base: Sabre GDD 2025 (class C). Distances: OAG schedules. GDP: OEF. Population: UN WPP. Elasticities estimated from 2013-2025 Sabre history; propensity-damped per cell."
    ext["meta"]["fixtures_remaining"] = ["segment fare elasticity is the Level 3 literature default (-0.7/-0.7/-0.5); the Level 2 UK estimate was rejected by the reliability rule as expansion-contaminated", "fare index is cost-driven from real EIA jet fuel (Method Spec 4.2); DB1B/GDD absolute levels (F15) still to source", "final-to-next M and the 0.35 via-hub share are structural fixtures, not GDD-derived", "airport capacities are illustrative pending Jess capacity register", "airport capacities illustrative pending Jess register", "F15 absolute fare levels (DB1B/GDD) to source"]
    ox.write_extract(ext, args.out)
    print("exceptions:", res.exceptions, "| wrote", args.out)


if __name__ == "__main__":
    main()

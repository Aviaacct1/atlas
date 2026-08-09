"""Global base-year O&D ingest (Phase 2). Turns the QSI tool's Sabre GDD od_p2p and
the airport reference into the forecast tool's base-year inputs: per-airport
outbound O&D by destination region (Domestic when the destination shares the origin
country), and terminal throughput for the scope rule. Reproducible; writes to
build/data/. Sabre is class C (base-year seeding only, no reconstitutable extract).
Author: Avia Solutions.

Usage: python3 scripts/ingest_global_base.py --qsi "<QSI app path>" --year 2025
"""
from __future__ import annotations
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from avia_forecast.io_safe import dump_atomic
from avia_forecast.paths import DATA, OEF_DIR, ACI_DIR, ACI_DECRYPT, SABRE_DB, OAG_DB, QSI_REF, PREAGG, QSI_APP, OEF_GDP_XLSX
from avia_forecast import paths   # the module, for paths.PREAGG and paths.report()
import argparse, csv, json, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from avia_forecast.geo.regions_iso2 import region_for_iso2, dest_region  # noqa: E402

DEF_QSI = QSI_APP
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def load_airport_country(qsi):
    ref = os.path.join(qsi, "reference_tables", "airport_city_country.csv")
    apc = {}
    for row in csv.DictReader(open(ref, encoding="utf-8-sig")):
        apc[row["airport_code"].strip()] = row["country_code"].strip()
    return apc


def run(qsi, year):
    import duckdb
    apc = load_airport_country(qsi)
    con = duckdb.connect(paths.PREAGG, read_only=True)
    rows = con.execute("select o, d, pax from od_p2p where year=?", [year]).fetchall()
    con.close()

    base_od = defaultdict(lambda: defaultdict(float))   # iata -> region -> pax
    term_out = defaultdict(float)                       # iata -> outbound O&D pax
    country_of = {}
    pax_total = pax_dest_unmapped = pax_origin_unmapped = 0.0

    for o, d, pax in rows:
        pax_total += pax
        oc, dc = apc.get(o), apc.get(d)
        if oc is None:
            pax_origin_unmapped += pax
            continue
        country_of[o] = oc
        r = dest_region(oc, dc)
        if r is None:
            pax_dest_unmapped += pax
            continue
        base_od[o][r] += pax
        term_out[o] += pax

    # airport meta: own world region (Domestic is relative, so store the airport's region)
    meta = {}
    for iata, oc in country_of.items():
        meta[iata] = {"country": oc, "region": region_for_iso2(oc),
                      "term_out_m": round(term_out[iata] / 1e6, 4)}

    base_od_m = {iata: {r: round(v / 1e6, 6) for r, v in regs.items()}
                 for iata, regs in base_od.items()}

    os.makedirs(OUT, exist_ok=True)
    dump_atomic(base_od_m, os.path.join(OUT, f"global_base_od_{year}.json"))
    dump_atomic(meta, os.path.join(OUT, f"global_airport_meta_{year}.json"))

    # coverage report
    n_air = len(meta)
    n_countries = len(set(m["country"] for m in meta.values()))
    top = sorted(meta.items(), key=lambda kv: kv[1]["term_out_m"], reverse=True)[:12]
    print(f"year {year}: od_p2p rows {len(rows):,}")
    print(f"origin airports mapped: {n_air:,} across {n_countries} countries")
    print(f"world outbound O&D: {pax_total/1e6:,.0f}m pax")
    print(f"  origin-country unmapped: {pax_origin_unmapped/1e6:,.1f}m ({pax_origin_unmapped/pax_total:.2%})")
    print(f"  dest-region unmapped:    {pax_dest_unmapped/1e6:,.1f}m ({pax_dest_unmapped/pax_total:.2%})")
    print("top airports by outbound O&D (m):")
    for iata, m in top:
        print(f"  {iata} {m['country']} {m['region']}: {m['term_out_m']:.1f}")
    return meta, base_od_m


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--qsi", default=DEF_QSI)
    ap.add_argument("--year", type=int, default=2025)
    a = ap.parse_args()
    run(a.qsi, a.year)

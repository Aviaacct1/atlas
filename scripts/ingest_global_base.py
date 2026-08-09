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
DROP_NAME_M = 0.1      # name every dropped airport above this, in million pax
DROP_FAIL_M = 2.0      # the scope.selection inclusion floor: dropping one is a build
                       # stopping error, not a line in a report
ALLOW_DROPS = os.environ.get("AVIA_ALLOW_BASE_DROPS") == "1"
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
    # Every dropped origin by name and size, not just a running total. The total alone
    # read 3.22% of world O&D, which looks like acceptable noise, and inside it were
    # Beijing Daxing at 20.4m and Chengdu Tianfu at 23.5m, both outside a world
    # forecast for as long as nobody opened the aggregate. A report that names no
    # airport cannot be checked by the person reading it. See MEASUREMENTS.md 3 and 3a.
    dropped_origin = defaultdict(float)
    dropped_dest = defaultdict(float)

    for o, d, pax in rows:
        pax_total += pax
        oc, dc = apc.get(o), apc.get(d)
        if oc is None:
            pax_origin_unmapped += pax
            dropped_origin[o] += pax
            continue
        country_of[o] = oc
        r = dest_region(oc, dc)
        if r is None:
            pax_dest_unmapped += pax
            dropped_dest[d] += pax
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

    # Name what was dropped, and stop if any single airport above the floor was.
    for label, dd in (("origin", dropped_origin), ("destination", dropped_dest)):
        big = sorted(((v, k) for k, v in dd.items() if v / 1e6 >= DROP_NAME_M),
                     reverse=True)
        if big:
            print(f"{label}s dropped above {DROP_NAME_M}m, largest first:")
            for v, k in big[:25]:
                print(f"  {k} {v/1e6:.2f}m")
    worst = max([v / 1e6 for v in dropped_origin.values()] or [0.0])
    if worst >= DROP_FAIL_M and not ALLOW_DROPS:
        raise SystemExit(
            f"STOP: an origin carrying {worst:.2f}m outbound O&D is absent from the "
            f"airport reference table and would be dropped from the base, which is "
            f"more than the {DROP_FAIL_M}m scope floor, so it would have been modelled "
            f"as an airport in its own right. Add it to "
            f"reference_tables/airport_city_country.csv, or set AVIA_ALLOW_BASE_DROPS=1 "
            f"to proceed deliberately. scripts/build_airport_reference_supplement.py "
            f"generates the missing rows.")

    # Written only once the checks above have passed. The first version of this guard
    # wrote the files and then complained, which leaves the bad base on disk for the
    # next step to pick up and makes the check decorative.
    os.makedirs(OUT, exist_ok=True)
    dump_atomic(base_od_m, os.path.join(OUT, f"global_base_od_{year}.json"))
    dump_atomic(meta, os.path.join(OUT, f"global_airport_meta_{year}.json"))
    print(f"written: global_base_od_{year}.json and global_airport_meta_{year}.json")
    return meta, base_od_m


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--qsi", default=DEF_QSI)
    ap.add_argument("--year", type=int, default=2025)
    a = ap.parse_args()
    run(a.qsi, a.year)

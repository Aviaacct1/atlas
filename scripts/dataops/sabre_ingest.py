#!/usr/bin/env python3
"""
Avia Solutions - Sabre ODPOO ingest to DuckDB.
==============================================
Loads one annual Sabre ODPOO CSV (circa 5-8GB) into a local DuckDB store at
full grain, streaming (never into memory). Run once per year.

Idempotent per year: before inserting it DELETEs any existing rows for that
source_year, so re-running a year replaces it rather than duplicating it.

Run with no arguments to ingest the 2013 file with the standard paths:
    py -3.12 scripts\dataops\sabre_ingest.py

Or override any path:
    py -3.12 sabre_ingest.py --csv "<year CSV>" --year 2016 --directionality ND --db "C:\\Avia\\sabre.duckdb"

Normalisations: two-space "  " placeholders -> NULL; numerics cast to DOUBLE
(Distance is int in 2013, decimal later); a directionality tag (POO/ND) and
source_year / source_file columns are added; trailing empty column dropped.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import argparse, os, sys, subprocess, datetime

# DuckDB self-install (first run only).
try:
    import duckdb
except ImportError:
    print("DuckDB not found - installing it now (one-off, needs internet)...", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "duckdb"])
    import duckdb

COLUMNS = [
    ("Itinerary","itinerary","txt"),("Origin Airport","origin_airport","txt"),
    ("Destination Airport","destination_airport","txt"),("Marketing Airline","marketing_airline","txt"),
    ("Operating Airline","operating_airline","txt"),("Cabin Class","cabin_class","txt"),
    ("Year","year","int"),
    ("Connecting Airport1","connecting_airport1","txtnull"),("Connecting City1","connecting_city1","txtnull"),
    ("Connecting Country1","connecting_country1","txtnull"),("Connecting Airport2","connecting_airport2","txtnull"),
    ("Connecting City2","connecting_city2","txtnull"),("Connecting Country2","connecting_country2","txtnull"),
    ("Connecting Airport3","connecting_airport3","txtnull"),("Connecting City3","connecting_city3","txtnull"),
    ("Connecting Country3","connecting_country3","txtnull"),
    ("Leg1 Mkt Aln","leg1_mkt_aln","txtnull"),("Leg2 Mkt Aln","leg2_mkt_aln","txtnull"),
    ("Leg3 Mkt Aln","leg3_mkt_aln","txtnull"),("Leg4 Mkt Aln","leg4_mkt_aln","txtnull"),
    ("Leg1 Op Aln","leg1_op_aln","txtnull"),("Leg2 Op Aln","leg2_op_aln","txtnull"),
    ("Leg3 Op Aln","leg3_op_aln","txtnull"),("Leg4 Op Aln","leg4_op_aln","txtnull"),
    ("Point Of Origin Airport","poo_airport","txt"),("Point Of Origin Airport Name","poo_airport_name","txt"),
    ("Point Of Origin City","poo_city","txt"),("Point Of Origin City Name","poo_city_name","txt"),
    ("Point Of Origin Country","poo_country","txt"),("Point Of Origin Country Name","poo_country_name","txt"),
    ("Point Of Origin Region Name","poo_region_name","txt"),
    ("Airline Share","airline_share","num"),("Passengers","passengers","num"),("PPDEW","ppdew","num"),
    ("Avg. Base Fare(USD)","avg_base_fare_usd","num"),("Base Revenue(USD)","base_revenue_usd","num"),
    ("Avg. Total Fare(USD)","avg_total_fare_usd","num"),("Total Revenue(USD)","total_revenue_usd","num"),
    ("Distance (km)","distance_km","num"),
]

def expr(src, kind):
    q = f'"{src}"'
    if kind in ("txt","txtnull"): return f"NULLIF(trim({q}), '')"
    if kind == "int": return f"TRY_CAST(trim({q}) AS INTEGER)"
    if kind == "num": return f"TRY_CAST(trim({q}) AS DOUBLE)"
    raise ValueError(kind)

DEFAULT_CSV = _os.path.join(_paths.SABRE_SRC,
                            "World2013POO-1av002013-235-20260423121045.csv")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=DEFAULT_CSV)
    ap.add_argument("--year", type=int, default=2013)
    ap.add_argument("--directionality", choices=["POO","ND"], default="POO")
    ap.add_argument("--db", default=_paths.SABRE_DB)
    a = ap.parse_args()

    print(f"Python {sys.version.split()[0]}  |  DuckDB {duckdb.__version__}", flush=True)
    print(f"Source : {a.csv}", flush=True)
    print(f"Store  : {a.db}", flush=True)
    if not os.path.exists(a.csv):
        print(f"ERROR: cannot find the CSV at that path. Check the drive letter / filename.", flush=True)
        sys.exit(1)
    os.makedirs(os.path.dirname(a.db) or ".", exist_ok=True)
    t0 = datetime.datetime.now()
    print(f"Started {t0:%H:%M:%S} - reading ~{os.path.getsize(a.csv)/1e9:.1f}GB, please wait...", flush=True)

    select_cols = ",\n  ".join(f"{expr(s,k)} AS {c}" for s,c,k in COLUMNS)
    con = duckdb.connect(a.db)
    # Robust read: some files (e.g. the 2025 "Best" estimate) defeat the dialect
    # sniffer. Try auto-detect with permissive options, then fall back to explicit
    # delimiters before giving up.
    # ODPOO files are comma-delimited UTF-8 with a header. State the delimiter and
    # sniff only a sample of the (clean) head: sample_size=-1 makes DuckDB sniff the
    # whole multi-GB file, which one malformed row deep inside defeats (the 2025
    # 'Best' file). ignore_errors skips any bad rows; null_padding handles ragged ones.
    csv = a.csv.replace("'", "''")
    common = ("header=true, all_varchar=true, ignore_errors=true, null_padding=true, "
              "strict_mode=false, max_line_size=40000000")
    attempts = [
        f"read_csv('{csv}', delim=',', sample_size=50000, {common})",
        f"read_csv('{csv}', delim=',', sample_size=-1, {common})",
        f"read_csv('{csv}', sample_size=50000, {common})",
        f"read_csv('{csv}', delim='|', sample_size=50000, {common})",
    ]
    last = None; loaded = False
    for sql in attempts:
        try:
            con.execute(f"CREATE OR REPLACE TEMP VIEW _raw AS SELECT * FROM {sql}")
            loaded = True; break
        except Exception as e:
            last = e
            print(f"  read attempt failed: {str(e).splitlines()[0][:140]}", flush=True)
    if not loaded:
        raise last
    con.execute("DROP TABLE IF EXISTS _stg")
    con.execute(f"""CREATE TABLE _stg AS SELECT {select_cols},
        '{a.directionality}' AS directionality, {a.year} AS source_year,
        '{os.path.basename(a.csv)}' AS source_file FROM _raw""")
    con.execute("CREATE TABLE IF NOT EXISTS sabre AS SELECT * FROM _stg WHERE 1=0")
    con.execute(f"DELETE FROM sabre WHERE source_year = {a.year}")
    con.execute("INSERT INTO sabre SELECT * FROM _stg")
    con.execute("DROP TABLE _stg")
    n = con.execute(f"SELECT count(*) FROM sabre WHERE source_year={a.year}").fetchone()[0]
    tot = con.execute("SELECT count(*) FROM sabre").fetchone()[0]
    con.close()
    secs = (datetime.datetime.now()-t0).total_seconds()
    print(f"DONE in {secs/60:.1f} min. Ingested {n:,} rows for {a.year} ({a.directionality}). Store now holds {tot:,} rows.", flush=True)

if __name__ == "__main__":
    main()

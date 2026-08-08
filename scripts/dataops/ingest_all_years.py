#!/usr/bin/env python3
"""
Avia Solutions - bulk Sabre ingest. Loads every annual ODPOO file into the store,
skipping years already present. Run once and leave it; ~30-45 min per year.
Directional years (2013, 2015) are detected automatically (no 'ND' in the name).

Run: py -3.12 scripts\dataops\ingest_all_years.py
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import os, sys, glob, subprocess, re, datetime
try:
    import duckdb
except ImportError:
    subprocess.check_call([sys.executable,"-m","pip","install","--quiet","duckdb"]); import duckdb

ODPOO = _paths.SABRE_SRC
DB    = _paths.SABRE_DB
INGEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sabre_ingest.py")

def year_of(name):
    if name.startswith("World2924"):   return 2024          # filename typo for 2024
    if name.startswith("World202021"): return 2021          # combined 2020-21
    m = re.match(r"World(\d{4})", name)
    return int(m.group(1)) if m else None

def main():
    files = sorted(glob.glob(os.path.join(ODPOO, "World*.csv")))
    if not files:
        print(f"No World*.csv found in {ODPOO} - check the drive letter."); return
    con = duckdb.connect(DB, read_only=True)
    try:
        done = {r[0] for r in con.execute("SELECT DISTINCT source_year FROM sabre").fetchall()}
    except Exception:
        done = set()
    con.close()
    print(f"Years already in store: {sorted(done) or 'none'}\n")
    plan = []
    for f in files:
        n = os.path.basename(f); y = year_of(n)
        d = "ND" if "ND" in n else "POO"
        plan.append((f, n, y, d))
    for f, n, y, d in plan:
        tag = "SKIP (already loaded)" if y in done else "INGEST"
        print(f"  {y} [{d}]  {tag}   {n}")
    print()
    for f, n, y, d in plan:
        if y in done:
            continue
        print(f"=== {datetime.datetime.now():%H:%M} ingesting {y} ({d}) ===", flush=True)
        try:
            subprocess.run([sys.executable, INGEST, "--csv", f, "--year", str(y),
                            "--directionality", d, "--db", DB], check=True)
            done.add(y)
        except subprocess.CalledProcessError as e:
            print(f"  !! {y} failed ({e}); moving on", flush=True)
    print("\nALL DONE. Years in store:", sorted(done))

if __name__ == "__main__":
    main()

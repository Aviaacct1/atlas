#!/usr/bin/env python3
"""
Avia Solutions - bulk OAG ingest.
=================================
Loads every OAG region file in a folder into C:\\Avia\\oag.duckdb, inferring week
and region from the filename, skipping the Hub Airports file and any (week, region)
already loaded. Continue-on-error. Run it again whenever Jess adds more weeks.

  py -3.12 ingest_all_oag.py
  py -3.12 ingest_all_oag.py "<folder>" "<db>"
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import os, sys, glob, datetime
import oag_ingest as OI

def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else _os.path.join(_paths.EGNYTE, "18 Products", "QSI", "Data Store")
    db = sys.argv[2] if len(sys.argv) > 2 else _paths.OAG_DB
    files = sorted(glob.glob(os.path.join(folder, "*.xls*")))
    if not files:
        print("No files found in", folder); return

    done = set()
    if os.path.exists(db):
        import duckdb
        con = duckdb.connect(db, read_only=True)
        try:
            done = {(w, r) for w, r in con.execute("SELECT DISTINCT week, region FROM oag").fetchall()}
        except Exception:
            pass
        con.close()

    t0 = datetime.datetime.now()
    n_new = 0
    for f in files:
        b = os.path.basename(f)
        if b.lower().startswith("hub airports"):
            print(f"skip (not a region file): {b}"); continue
        wk, rg = OI.infer(f)
        if not wk or not rg:
            print(f"SKIP (cannot infer week/region): {b}"); continue
        if (wk, rg) in done:
            print(f"skip (already loaded): {rg} {wk}"); continue
        try:
            t = datetime.datetime.now()
            n, tot = OI.ingest_one(f, wk, rg, db)
            print(f"loaded {rg} {wk}: {n:,} flights ({(datetime.datetime.now()-t).total_seconds():.0f}s); store now {tot:,}", flush=True)
            done.add((wk, rg)); n_new += 1
        except Exception as e:
            print(f"FAILED {b}: {str(e).splitlines()[0][:140]}", flush=True)
    print(f"ALL DONE in {(datetime.datetime.now()-t0).total_seconds()/60:.1f} min. Loaded weeks/regions: {len(done)}")
    _refresh_serve_copy(db, n_new)


def _refresh_serve_copy(db, n_new):
    """Copy the live store to a timestamped serve file the web service reads, so the
    service never locks the live file. Old copies are deleted best-effort (an open
    one survives until the service restarts, then goes on the next refresh)."""
    import glob, shutil
    pattern = os.path.join(os.path.dirname(db) or ".", "oag_serve_*.duckdb")
    existing = sorted(glob.glob(pattern))
    if n_new == 0 and existing:
        print("serve copy unchanged (nothing new loaded)"); return
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    new = os.path.join(os.path.dirname(db) or ".", f"oag_serve_{ts}.duckdb")
    print(f"refreshing serve copy -> {new} ...", flush=True)
    shutil.copy2(db, new)
    for old_f in existing:
        try:
            os.remove(old_f); print(f"removed old serve copy {os.path.basename(old_f)}")
        except OSError:
            print(f"old serve copy {os.path.basename(old_f)} in use; will clear next run")
    print("serve copy ready (service adopts it on next restart)")

if __name__ == "__main__":
    main()

"""Re-ingest every OAG file whose workbook has continuation sheets (the ones
the old single-sheet reader truncated). Safe to re-run; ingest_one replaces the
(week, region) slice atomically. Author: Avia Solutions.

  py -3.12 reingest_multisheet.py            # scan Z: Data Store, reload capped files
  py -3.12 reingest_multisheet.py "<folder>" "<db>"
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import glob, os, sys, datetime
import pandas as pd
import oag_ingest as OI

def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else _os.path.join(_paths.EGNYTE, "18 Products", "QSI", "Data Store")
    db = sys.argv[2] if len(sys.argv) > 2 else _paths.OAG_DB
    t0 = datetime.datetime.now()
    n_fixed = 0
    for f in sorted(glob.glob(os.path.join(folder, "*.xls*"))):
        b = os.path.basename(f)
        if b.lower().startswith("hub airports"):
            continue
        wk, rg = OI.infer(f)
        if not wk or not rg:
            continue
        try:
            sheets = [s for s in pd.ExcelFile(f, engine="calamine").sheet_names
                      if not s.lower().startswith("note")]
        except Exception as e:
            print(f"SKIP {b}: cannot open ({str(e)[:80]})", flush=True); continue
        if len(sheets) <= 1:
            continue
        print(f"multi-sheet ({len(sheets)}): {b} -> reloading {rg} {wk}", flush=True)
        try:
            t = datetime.datetime.now()
            n, tot = OI.ingest_one(f, wk, rg, db)
            n_fixed += 1
            print(f"  reloaded {n:,} rows ({(datetime.datetime.now()-t).total_seconds():.0f}s); store now {tot:,}", flush=True)
        except Exception as e:
            print(f"  FAILED: {str(e)[:140]}", flush=True)
    print(f"DONE in {(datetime.datetime.now()-t0).total_seconds()/60:.1f} min; {n_fixed} files reloaded")

if __name__ == "__main__":
    main()

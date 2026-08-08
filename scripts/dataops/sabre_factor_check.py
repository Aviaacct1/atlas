#!/usr/bin/env python3
"""
Avia Solutions - factor / basis diagnostic.
Compares specific direct O-D markets in the store against the analyst's
hand-pulled figures, to see whether the store sits on a constant factor below
the analyst (a simple calibration) or varies by market. Also prints the store's
total 2013 passengers as a sanity check on completeness.
Run: py -3.12 scripts\dataops\sabre_factor_check.py
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import sys, subprocess
try:
    import duckdb
except ImportError:
    subprocess.check_call([sys.executable,"-m","pip","install","--quiet","duckdb"]); import duckdb
DB=_paths.SABRE_DB
PAIRS=[("LAX","CDG",244882),("SFO","CDG",222062),("SFO","FRA",176160),("SFO","AMS",85279),
       ("LAX","AMS",80727),("LAX","TLV",78811),("LAX","FRA",66253),("SFO","ZRH",59685),
       ("SFO","MUC",58494),("LAX","ZRH",57877)]
con=duckdb.connect(DB, read_only=True)
grand=con.execute("SELECT COALESCE(sum(passengers),0) FROM sabre WHERE source_year=2013").fetchone()[0]
print(f"Store total 2013 passengers (all rows): {grand:,.0f}\n")
print(f"{'O-D':>9} {'store direct':>13} {'analyst':>10} {'store/analyst':>14}")
ts=ta=0
for o,d,a in PAIRS:
    v=con.execute(f"SELECT COALESCE(sum(passengers),0) FROM sabre WHERE source_year=2013 AND origin_airport='{o}' AND destination_airport='{d}' AND itinerary='NON-STOP'").fetchone()[0]
    ts+=v; ta+=a
    print(f"{o+'-'+d:>9} {v:>13,.0f} {a:>10,.0f} {v/a if a else 0:>13.2f}x")
print(f"\n{'TOTAL':>9} {ts:>13,.0f} {ta:>10,.0f} {ts/ta if ta else 0:>13.2f}x")
con.close()

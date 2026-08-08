#!/usr/bin/env python3
"""
Avia Solutions - directionality diagnostic.
Tests whether the store's 2013 directional (POO) data matches the analyst's
extract once BOTH directions of each market are counted. If the both-ways ratio
lands near 1.0, the analyst extract is non-directional and the only adjustment
for 2013/2015 is to combine directions.
Run: py -3.12 scripts\dataops\sabre_direction_check.py
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
print(f"{'O-D':>9} {'one-way':>10} {'both-ways':>10} {'analyst':>9} {'1way':>6} {'2way':>6}")
t1=t2=ta=0
for o,d,a in PAIRS:
    one=con.execute(f"SELECT COALESCE(sum(passengers),0) FROM sabre WHERE source_year=2013 AND itinerary='NON-STOP' AND origin_airport='{o}' AND destination_airport='{d}'").fetchone()[0]
    both=con.execute(f"SELECT COALESCE(sum(passengers),0) FROM sabre WHERE source_year=2013 AND itinerary='NON-STOP' AND ((origin_airport='{o}' AND destination_airport='{d}') OR (origin_airport='{d}' AND destination_airport='{o}'))").fetchone()[0]
    t1+=one; t2+=both; ta+=a
    print(f"{o+'-'+d:>9} {one:>10,.0f} {both:>10,.0f} {a:>9,.0f} {one/a if a else 0:>5.2f}x {both/a if a else 0:>5.2f}x")
print(f"{'TOTAL':>9} {t1:>10,.0f} {t2:>10,.0f} {ta:>9,.0f} {t1/ta:>5.2f}x {t2/ta:>5.2f}x")
con.close()

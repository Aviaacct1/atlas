#!/usr/bin/env python3
"""
Avia Solutions - acceptance check: reproduce the analyst's SFO/LAX/SAN 2013
demand extract from the DuckDB store. Computes totals on two origin bases
(board point vs true origin) so we can see which one the analyst used and
whether the store matches the hand-pulled figures.

Run:  py -3.12 scripts\dataops\sabre_compare_analyst.py
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import sys, subprocess
try:
    import duckdb
except ImportError:
    subprocess.check_call([sys.executable,"-m","pip","install","--quiet","duckdb"]); import duckdb

DB = _paths.SABRE_DB
CATCH = ('SFO','LAX','SAN')
TARGET = dict(total=6122094, direct=1486445, indirect=4635649, ba=711297)

con = duckdb.connect(DB, read_only=True)
def lst(t): return "(" + ",".join(f"'{x}'" for x in t) + ")"

print(f"ANALYST TARGET (2013 SFO/LAX/SAN -> everywhere):")
print(f"   total {TARGET['total']:,} | direct {TARGET['direct']:,} | indirect {TARGET['indirect']:,} | BA {TARGET['ba']:,}\n")

for label, origin_col in [("BOARD POINT (origin_airport)", "origin_airport"),
                          ("TRUE ORIGIN (poo_city)", "poo_city")]:
    w = f"source_year=2013 AND {origin_col} IN {lst(CATCH)}"
    tot = con.execute(f"SELECT COALESCE(sum(passengers),0) FROM sabre WHERE {w}").fetchone()[0]
    d   = con.execute(f"SELECT COALESCE(sum(passengers),0) FROM sabre WHERE {w} AND itinerary='NON-STOP'").fetchone()[0]
    ind = tot - d
    ba  = con.execute(f"SELECT COALESCE(sum(passengers),0) FROM sabre WHERE {w} AND operating_airline='BA'").fetchone()[0]
    def pct(x, t): return f"{(x-t)/t*100:+.1f}%" if t else "n/a"
    print(f"== {label} ==")
    print(f"   total    {tot:>12,.0f}   ({pct(tot,TARGET['total'])} vs analyst)")
    print(f"   direct   {d:>12,.0f}   ({pct(d,TARGET['direct'])})")
    print(f"   indirect {ind:>12,.0f}   ({pct(ind,TARGET['indirect'])})")
    print(f"   BA oper  {ba:>12,.0f}   ({pct(ba,TARGET['ba'])})")
    print()
con.close()

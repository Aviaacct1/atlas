#!/usr/bin/env python3
"""
Avia Solutions - reconnaissance query: LHR <-> California market, 2013.
Reads the local DuckDB store and reports the London <-> California O-D market
so we can compare it against the analyst's hand-pulled BA LHR-SJC extract and
build the QSI-view generator. Also writes a small CSV extract of the market.

Run:  py -3.12 scripts\dataops\sabre_query_lhrsjc.py
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import sys, subprocess, os
try:
    import duckdb
except ImportError:
    subprocess.check_call([sys.executable,"-m","pip","install","--quiet","duckdb"]); import duckdb

DB  = _paths.SABRE_DB
OUT = _os.path.join(_paths.AVIA, 'lhr_california_2013.csv')
LON = ('LHR','LGW','STN','LTN','LCY','SEN')
CAL = ('SFO','OAK','SJC','LAX','SAN','BUR','ONT','SNA')

def lst(t): return "(" + ",".join(f"'{x}'" for x in t) + ")"

con = duckdb.connect(DB, read_only=True)
tot = con.execute("SELECT count(*) FROM sabre WHERE source_year=2013").fetchone()[0]
print(f"Store 2013 rows: {tot:,}")

where = f"""source_year=2013 AND (
   (origin_airport IN {lst(LON)} AND destination_airport IN {lst(CAL)})
   OR (origin_airport IN {lst(CAL)} AND destination_airport IN {lst(LON)}) )"""

m = con.execute(f"SELECT count(*), COALESCE(sum(passengers),0), COALESCE(sum(total_revenue_usd),0) FROM sabre WHERE {where}").fetchone()
print(f"\nLHR<->California market rows: {m[0]:,} | passengers: {m[1]:,.0f} | revenue ${m[2]:,.0f}")

print("\n-- direct vs connecting (by passengers) --")
for r in con.execute(f"""SELECT CASE WHEN itinerary='NON-STOP' THEN 'direct' ELSE 'connecting' END t,
   count(*) nrows, sum(passengers) pax FROM sabre WHERE {where} GROUP BY 1 ORDER BY pax DESC""").fetchall():
    print(f"   {r[0]:>10}: {r[1]:>5} rows, {r[2]:>12,.0f} pax")

print("\n-- top marketing carriers (by passengers) --")
for r in con.execute(f"""SELECT marketing_airline, sum(passengers) pax FROM sabre WHERE {where}
   GROUP BY 1 ORDER BY pax DESC LIMIT 10""").fetchall():
    print(f"   {r[0]:>4}: {r[1]:>12,.0f}")

print("\n-- board-point pairs (top 12 by passengers) --")
for r in con.execute(f"""SELECT origin_airport||'-'||destination_airport pair, sum(passengers) pax
   FROM sabre WHERE {where} GROUP BY 1 ORDER BY pax DESC LIMIT 12""").fetchall():
    print(f"   {r[0]:>9}: {r[1]:>12,.0f}")

print("\n-- true-origin cities present (top 12 by passengers) --")
for r in con.execute(f"""SELECT poo_city, sum(passengers) pax FROM sabre WHERE {where}
   GROUP BY 1 ORDER BY pax DESC LIMIT 12""").fetchall():
    print(f"   {r[0]:>5}: {r[1]:>12,.0f}")

con.execute(f"COPY (SELECT * FROM sabre WHERE {where}) TO '{OUT}' (HEADER, DELIMITER ',')")
n = con.execute(f"SELECT count(*) FROM sabre WHERE {where}").fetchone()[0]
print(f"\nWrote {n:,} market rows to {OUT}")
con.close()

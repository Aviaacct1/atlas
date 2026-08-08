#!/usr/bin/env python3
"""
Avia Solutions - refined acceptance check.
Reproduce the analyst's SFO/LAX/SAN 2013 demand by applying the two rules the
first comparison revealed:
  1. destination scope = the contestable LHR-hub geography (the 58 destination
     countries present in the analyst's own extract), via the airport->country
     lookup;
  2. BA counted across the connecting legs, not just the single operating field.

Needs in the same folder:  sabre.duckdb  and  airport_city_country.csv
Run:  py -3.12 scripts\dataops\sabre_compare_refined.py
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import sys, subprocess, os
try:
    import duckdb
except ImportError:
    subprocess.check_call([sys.executable,"-m","pip","install","--quiet","duckdb"]); import duckdb

DB     = _paths.SABRE_DB
LOOKUP = _os.path.join(_paths.AVIA, 'airport_city_country.csv')
CATCH  = ('SFO','LAX','SAN')
TARGET = dict(total=6122094, direct=1486445, indirect=4635649, ba=711297)
COUNTRIES = ["France","Germany","India","Italy","Spain","Netherlands","Switzerland","Israel","Denmark",
"Ireland Republic of","Sweden","Russian Federation","United Kingdom","Turkey","Iran Islamic Republic of",
"United Arab Emirates","Belgium","Austria","Norway","Czech Republic","Saudi Arabia","South Africa","Hungary",
"Greece","Egypt","Finland","Poland","Lebanon","Pakistan","Jordan","Portugal","Ukraine","Romania","Kuwait",
"Nigeria","Kenya","Bahrain","Bulgaria","Sri Lanka","Croatia","Ethiopia","Serbia","Qatar","Luxembourg",
"Morocco","Uganda","Ghana","Tunisia","Algeria","Oman","Malta","Cyprus","Azerbaijan","Uzbekistan","Angola",
"Mauritius","Gibraltar","Turkmenistan"]

def slist(t): return "(" + ",".join("'" + x.replace("'","''") + "'" for x in t) + ")"

con = duckdb.connect(DB, read_only=True)
con.execute(f"CREATE TEMP TABLE lk AS SELECT * FROM read_csv_auto('{LOOKUP}', header=true)")
con.execute(f"CREATE TEMP TABLE dest_ok AS SELECT DISTINCT airport_code FROM lk WHERE country_name IN {slist(COUNTRIES)}")
ndest = con.execute("SELECT count(*) FROM dest_ok").fetchone()[0]
print(f"Contestable destination airports (in {len(COUNTRIES)} countries): {ndest:,}")
print(f"\nANALYST TARGET: total {TARGET['total']:,} | direct {TARGET['direct']:,} | indirect {TARGET['indirect']:,} | BA {TARGET['ba']:,}\n")

def pct(x,t): return f"{(x-t)/t*100:+.1f}%" if t else "n/a"
for label, oc in [("BOARD POINT (origin_airport)","origin_airport"),("TRUE ORIGIN (poo_city)","poo_city")]:
    w = f"""source_year=2013 AND {oc} IN {slist(CATCH)}
            AND destination_airport IN (SELECT airport_code FROM dest_ok)"""
    tot = con.execute(f"SELECT COALESCE(sum(passengers),0) FROM sabre WHERE {w}").fetchone()[0]
    d   = con.execute(f"SELECT COALESCE(sum(passengers),0) FROM sabre WHERE {w} AND itinerary='NON-STOP'").fetchone()[0]
    ba_single = con.execute(f"SELECT COALESCE(sum(passengers),0) FROM sabre WHERE {w} AND operating_airline='BA'").fetchone()[0]
    ba_legop  = con.execute(f"SELECT COALESCE(sum(passengers),0) FROM sabre WHERE {w} AND ('BA' IN (leg1_op_aln,leg2_op_aln,leg3_op_aln,leg4_op_aln))").fetchone()[0]
    ba_legmkt = con.execute(f"SELECT COALESCE(sum(passengers),0) FROM sabre WHERE {w} AND ('BA' IN (leg1_mkt_aln,leg2_mkt_aln,leg3_mkt_aln,leg4_mkt_aln))").fetchone()[0]
    print(f"== {label} ==")
    print(f"   total      {tot:>12,.0f}   ({pct(tot,TARGET['total'])})")
    print(f"   direct     {d:>12,.0f}   ({pct(d,TARGET['direct'])})")
    print(f"   indirect   {tot-d:>12,.0f}   ({pct(tot-d,TARGET['indirect'])})")
    print(f"   BA single  {ba_single:>12,.0f}   ({pct(ba_single,TARGET['ba'])})")
    print(f"   BA any-leg-op  {ba_legop:>12,.0f}   ({pct(ba_legop,TARGET['ba'])})")
    print(f"   BA any-leg-mkt {ba_legmkt:>12,.0f}   ({pct(ba_legmkt,TARGET['ba'])})")
    print()
con.close()

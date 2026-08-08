#!/usr/bin/env python3
"""
Avia Solutions - 2023 cut control (Cathay HKG-SJC).
Tests whether the store's 2023 (recent, non-directional) data reproduces the
Cathay model's Bay Area <-> Hong Kong market. If it lands near the analyst
figure, the 12% seen on 2013 was the old 2015 Sabre pull; if it's ~0.88x again,
the ODPOO/pull offset is persistent and we size a factor-up.
Run: py -3.12 scripts\dataops\sabre_2023_control.py
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
BAY=("SFO","OAK","SJC")
TARGET_FULL=375184      # analyst full Bay Area-HKG market
TARGET_SJC=144446       # analyst SJC catchment share (38.5%)
def L(t): return "("+",".join(f"'{x}'" for x in t)+")"
con=duckdb.connect(DB, read_only=True)
yr=con.execute("SELECT count(*) FROM sabre WHERE source_year=2023").fetchone()[0]
print(f"store 2023 rows: {yr:,}\nanalyst: full Bay Area-HKG market {TARGET_FULL:,} | SJC share {TARGET_SJC:,}\n")

def market(origins):
    w=f"source_year=2023 AND ((origin_airport IN {L(origins)} AND destination_airport='HKG') OR (origin_airport='HKG' AND destination_airport IN {L(origins)}))"
    tot=con.execute(f"SELECT COALESCE(sum(passengers),0) FROM sabre WHERE {w}").fetchone()[0]
    one=con.execute(f"SELECT COALESCE(sum(passengers),0) FROM sabre WHERE {w} AND origin_airport IN {L(origins)}").fetchone()[0]
    direct=con.execute(f"SELECT COALESCE(sum(passengers),0) FROM sabre WHERE {w} AND itinerary='NON-STOP'").fetchone()[0]
    return tot,one,direct

for label,origins,tgt in [("Bay Area (SFO/OAK/SJC) <-> HKG",BAY,TARGET_FULL),("SJC only <-> HKG",("SJC",),TARGET_SJC)]:
    tot,one,direct=market(origins)
    print(f"== {label} ==")
    print(f"   both-ways total : {tot:>10,.0f}   ({tot/tgt:.2f}x analyst {tgt:,})")
    print(f"   one-way (Bay->) : {one:>10,.0f}")
    print(f"   of which direct : {direct:>10,.0f}")
    # by carrier (both-ways)
    w=f"source_year=2023 AND ((origin_airport IN {L(origins)} AND destination_airport='HKG') OR (origin_airport='HKG' AND destination_airport IN {L(origins)}))"
    print("   top carriers (operating, both-ways):")
    for c,p in con.execute(f"SELECT operating_airline, round(sum(passengers)) p FROM sabre WHERE {w} GROUP BY 1 ORDER BY p DESC LIMIT 6").fetchall():
        print(f"      {c:>4}: {p:>10,.0f}")
    print()
con.close()

#!/usr/bin/env python3
"""
Avia Solutions - cabin-level diff to localise the master-vs-extract gap.
For two clean direct markets (2013, both directions, non-stop), shows the store's
passengers by cabin against Ollie's extract. Confirms whether the ~12% gap is a
uniform per-cabin volume scaling (=> a factor-up / product difference, benign and
fixable) and exposes the cabin-granularity difference (store 4 labels vs extract 6).
Run: py -3.12 scripts\dataops\sabre_cabin_diff.py
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
OLLIE={
 ("LAX","CDG"): {"Discount Coach":181903,"Coach":19664,"Business":37004,"Discount Business":2002,"First":4309,"_total":244882},
 ("SFO","CDG"): {"Discount Coach":177255,"Coach":17047,"Business":26656,"Discount Business":1071,"First":33,"_total":222062},
}
con=duckdb.connect(DB, read_only=True)
for (o,d),tgt in OLLIE.items():
    w=f"source_year=2013 AND itinerary='NON-STOP' AND ((origin_airport='{o}' AND destination_airport='{d}') OR (origin_airport='{d}' AND destination_airport='{o}'))"
    print(f"\n===== {o}-{d}  (2013, both directions, non-stop) =====")
    print("  STORE cabins:")
    stot=0
    for c,p in con.execute(f"SELECT cabin_class, round(sum(passengers)) p FROM sabre WHERE {w} GROUP BY 1 ORDER BY p DESC").fetchall():
        print(f"     {c:<16}: {p:>10,.0f}"); stot+=p
    print("  OLLIE cabins (extract):")
    for c,v in sorted(tgt.items(), key=lambda x:-x[1] if isinstance(x[1],(int,float)) else 0):
        if c!='_total': print(f"     {c:<16}: {v:>10,.0f}")
    print(f"  TOTAL  store {stot:>10,.0f}  vs Ollie {tgt['_total']:>10,.0f}  = {stot/tgt['_total']:.2f}x")
con.close()

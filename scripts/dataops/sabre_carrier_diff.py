#!/usr/bin/env python3
"""
Avia Solutions - carrier-level diff to diagnose the direct-market gap.
For two clean direct markets, compares the store's passengers by operating
carrier (both directions, non-stop, 2013) against Ollie's extract figures.
Uniform shortfall across carriers => basis/cut difference (benign).
A missing or wildly different carrier => method/data problem to fix.
Run: py -3.12 scripts\dataops\sabre_carrier_diff.py
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
# Ollie's DIRECT figures by operating carrier (from his extract)
OLLIE={
 ("LAX","CDG"): {"AF":193137,"TN":51727,"_total":244882},
 ("SFO","CDG"): {"AF":146485,"UA":63666,"SE":11883,"_total":222062},
}
con=duckdb.connect(DB, read_only=True)
for (o,d),tgt in OLLIE.items():
    w=f"source_year=2013 AND itinerary='NON-STOP' AND ((origin_airport='{o}' AND destination_airport='{d}') OR (origin_airport='{d}' AND destination_airport='{o}'))"
    rows=con.execute(f"SELECT operating_airline, round(sum(passengers)) p FROM sabre WHERE {w} GROUP BY 1 ORDER BY p DESC").fetchall()
    store=dict(rows); stot=sum(store.values())
    print(f"\n===== {o}-{d}  (both directions, non-stop, 2013) =====")
    print(f"  {'carrier':>8} {'store':>10} {'Ollie':>10} {'store/Ollie':>12}")
    cars=[c for c in tgt if c!='_total']
    for c in cars:
        sv=store.get(c,0); ov=tgt[c]
        print(f"  {c:>8} {sv:>10,.0f} {ov:>10,.0f} {sv/ov if ov else 0:>11.2f}x")
    # any big store carriers Ollie didn't list?
    extra=[(c,v) for c,v in store.items() if c not in cars and v>2000]
    for c,v in sorted(extra,key=lambda x:-x[1])[:5]:
        print(f"  {c:>8} {v:>10,.0f} {'(not in Ollie)':>10}")
    print(f"  {'TOTAL':>8} {stot:>10,.0f} {tgt['_total']:>10,.0f} {stot/tgt['_total']:>11.2f}x")
con.close()

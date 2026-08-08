#!/usr/bin/env python3
"""
Avia Solutions - exact-scope acceptance check.
Scopes the store to the analyst's exact origins (SFO/LAX/SAN board point) and
their exact 128 destination airports, so any residual gap vs the analyst total
is the carrier-counting rule, not scope. Run: py -3.12 scripts\dataops\sabre_compare_exact.py
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
CATCH=('SFO','LAX','SAN')
DESTS=['ABV', 'ABZ', 'ACC', 'ADD', 'AGP', 'ALG', 'AMM', 'AMS', 'ANR', 'ARN', 'ASB', 'ATH', 'AUH', 'BAH', 'BCN', 'BEG', 'BEY', 'BFS', 'BGO', 'BGY', 'BHD', 'BIO', 'BLQ', 'BLR', 'BMA', 'BOM', 'BRU', 'BSL', 'BUD', 'CAI', 'CDG', 'CFU', 'CGN', 'CMB', 'CMN', 'CPH', 'CPT', 'DEL', 'DME', 'DOH', 'DUB', 'DUS', 'DXB', 'EBB', 'EDI', 'FAO', 'FCO', 'FRA', 'GIB', 'GLA', 'GOT', 'GVA', 'GYD', 'HAJ', 'HAM', 'HEL', 'HYD', 'IBZ', 'IEV', 'IKA', 'ISB', 'IST', 'JED', 'JMK', 'JNB', 'JTR', 'KBP', 'KGS', 'KHI', 'KRK', 'KWI', 'LAD', 'LBA', 'LCA', 'LCG', 'LED', 'LHE', 'LIN', 'LIS', 'LOS', 'LUX', 'LXR', 'LYS', 'MAA', 'MAD', 'MAN', 'MCT', 'MLA', 'MLH', 'MRS', 'MRU', 'MUC', 'MXP', 'NBO', 'NCE', 'NCL', 'OLB', 'OPO', 'ORK', 'ORY', 'OSL', 'OTP', 'PMI', 'PRG', 'PSA', 'RJK', 'RUH', 'SAW', 'SNN', 'SOF', 'SPU', 'STR', 'SVG', 'SVO', 'SXF', 'TAS', 'TLS', 'TLV', 'TRF', 'TUN', 'TXL', 'VCE', 'VIE', 'VKO', 'WAW', 'WIL', 'ZAG', 'ZRH']
TARGET=dict(total=6122094, direct=1486445, indirect=4635649, ba=711297)
def L(t): return "("+",".join("'"+x+"'" for x in t)+")"
con=duckdb.connect(DB, read_only=True)
w=f"source_year=2013 AND origin_airport IN {L(CATCH)} AND destination_airport IN {L(DESTS)}"
def s(extra=""): return con.execute(f"SELECT COALESCE(sum(passengers),0) FROM sabre WHERE {w}{extra}").fetchone()[0]
tot=s(); d=s(" AND itinerary='NON-STOP'")
ba1=s(" AND operating_airline='BA'")
ba2=s(" AND ('BA' IN (leg1_op_aln,leg2_op_aln,leg3_op_aln,leg4_op_aln))")
ba3=s(" AND ('BA' IN (leg1_mkt_aln,leg2_mkt_aln,leg3_mkt_aln,leg4_mkt_aln))")
def p(x,t): return f"{(x-t)/t*100:+.1f}%" if t else "n/a"
print(f"ANALYST TARGET: total {TARGET['total']:,} | direct {TARGET['direct']:,} | indirect {TARGET['indirect']:,} | BA {TARGET['ba']:,}")
print(f"scope: 3 origins, {len(DESTS)} destination airports\n")
print(f"   total      {tot:>12,.0f}   ({p(tot,TARGET['total'])})")
print(f"   direct     {d:>12,.0f}   ({p(d,TARGET['direct'])})")
print(f"   indirect   {tot-d:>12,.0f}   ({p(tot-d,TARGET['indirect'])})")
print(f"   BA single      {ba1:>12,.0f}   ({p(ba1,TARGET['ba'])})")
print(f"   BA any-leg-op  {ba2:>12,.0f}   ({p(ba2,TARGET['ba'])})")
print(f"   BA any-leg-mkt {ba3:>12,.0f}   ({p(ba3,TARGET['ba'])})")
con.close()

#!/usr/bin/env python3
"""Quick validation of the 2025 Sabre ingest vs 2024. Read-only."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import duckdb
con = duckdb.connect(_paths.SABRE_DB, read_only=True)

print("years in store:", [r[0] for r in con.execute(
    "SELECT DISTINCT source_year FROM sabre ORDER BY 1").fetchall()])

print("\n            rows         passengers   null-orig  null/0-pax  origins  avg_fare")
for y in (2024, 2025):
    r = con.execute(f"""
        SELECT count(*), sum(passengers),
          100.0*sum(CASE WHEN origin_airport IS NULL THEN 1 ELSE 0 END)/count(*),
          100.0*sum(CASE WHEN passengers IS NULL OR passengers=0 THEN 1 ELSE 0 END)/count(*),
          count(DISTINCT origin_airport), avg(avg_total_fare_usd)
        FROM sabre WHERE source_year={y}""").fetchone()
    print(f"{y}:  {r[0]:>12,}  {r[1]:>14,.0f}   {r[2]:>6.1f}%   {r[3]:>7.1f}%   {r[4]:>6,}  ${r[5]:>7,.0f}")

print("\n2025 data 'year' column values:",
      con.execute("SELECT DISTINCT year FROM sabre WHERE source_year=2025 ORDER BY 1").fetchall())

NYC = "('JFK','EWR','LGA')"
print("\nknown-market cross-check (passengers):")
for mkt, where in [("MXP->NYC", f"origin_airport='MXP' AND destination_airport IN {NYC}"),
                   ("LHR->SFO", "origin_airport='LHR' AND destination_airport='SFO'"),
                   ("GOA->NYC", f"origin_airport='GOA' AND destination_airport IN {NYC}")]:
    a = con.execute(f"SELECT sum(passengers) FROM sabre WHERE source_year=2024 AND {where}").fetchone()[0] or 0
    b = con.execute(f"SELECT sum(passengers) FROM sabre WHERE source_year=2025 AND {where}").fetchone()[0] or 0
    print(f"  {mkt}:  2024 {a:>10,.0f}   2025 {b:>10,.0f}")

print("\n5 sample 2025 rows (origin, dest, op carrier, cabin, pax, fare):")
for r in con.execute("""SELECT origin_airport,destination_airport,operating_airline,cabin_class,
    passengers,avg_total_fare_usd FROM sabre WHERE source_year=2025 AND passengers>0 LIMIT 5""").fetchall():
    print("  ", r)
con.close()

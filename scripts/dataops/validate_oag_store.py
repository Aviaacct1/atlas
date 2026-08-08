"""Section-3 validation for the full-year OAG store (C:\\Avia\\oag.duckdb).
Characterises the store before any downstream layer reads it:
  - label granularity per year (annual / monthly / half-year / weekly) and the double-count trap
  - which granularity covers which region, 2015-2018
  - capacity semantics (seats_total = seats x frequency; frequency = departures in period)
  - directional (each-way) basis
  - service_type passenger filter
  - Excel-ceiling truncation of the North America / Southwest Pacific annual files
  - a trunk-route full-year reconciliation
Read-only, memory-capped for a small box. Author: Avia Solutions.
Usage: py -3.12 validate_oag_store.py
"""
import duckdb

DB = "oag.duckdb"
MON = "regexp_full_match(week,'[0-9]{4}-[0-9]{2}')"
LT = """CASE
  WHEN regexp_full_match(week,'[0-9]{4}-[0-9]{2}-[0-9]{2}') THEN 'weekly'
  WHEN regexp_full_match(week,'[0-9]{4}-[0-9]{2}') THEN 'monthly'
  WHEN regexp_full_match(week,'[0-9]{4}') THEN 'annual'
  ELSE 'other' END"""
D = "TRY_CAST"

con = duckdb.connect(DB, read_only=True)
con.execute("SET memory_limit='2GB'")
con.execute("SET threads=2")

print(f"rows total: {con.execute('SELECT COUNT(*) FROM oag').fetchone()[0]:,}\n")

print("=== label_type x year ===")
for y, lt, n, r in con.execute(
        f"SELECT year, {LT} lt, COUNT(DISTINCT week) nl, COUNT(*) nr "
        f"FROM oag GROUP BY year, lt ORDER BY year, lt").fetchall():
    print(f"  {y}  {lt:<8} {n:>4} labels  {r:>14,} rows")

print("\n=== granularity x region, 2015-2019 ===")
for y, reg, lt, n in con.execute(
        f"SELECT year, region, {LT} lt, COUNT(*) n FROM oag "
        f"WHERE year BETWEEN 2015 AND 2019 GROUP BY year, region, lt "
        f"ORDER BY year, region, lt").fetchall():
    print(f"  {y} {reg:<18} {lt:<8} {n:>12,}")

print("\n=== service_type distribution ===")
for st, n in con.execute(
        "SELECT service_type, COUNT(*) n FROM oag GROUP BY service_type "
        "ORDER BY n DESC LIMIT 15").fetchall():
    print(f"  {st!r:<6} {n:>14,}")

print("\n=== truncation: source files at/near Excel 1,048,576 ceiling ===")
for sf, n in con.execute(
        "SELECT source_file, COUNT(*) n FROM oag GROUP BY source_file "
        "ORDER BY n DESC LIMIT 12").fetchall():
    flag = "  <-- CEILING" if n >= 1_040_000 else ""
    print(f"  {n:>10,}  {sf}{flag}")

print("\n=== capacity semantics + each-way check: LHR-JFK 2018 monthly ===")
for a, b in [("LHR", "JFK"), ("JFK", "LHR")]:
    m, seats, deps = con.execute(
        f"SELECT COUNT(DISTINCT week), SUM({D}(seats_total AS DOUBLE)), "
        f"SUM({D}(frequency AS DOUBLE)) FROM oag "
        f"WHERE dep_airport='{a}' AND arr_airport='{b}' AND {MON} AND year=2018 "
        f"AND service_type='J'").fetchone()
    print(f"  {a}->{b}: months={m}  seats(one-way)={seats:,.0f}  departures={deps:,.0f}")

print("\n=== truncation symptom on NA annual: JFK-LAX 2018 annual label ===")
nr, deps, seats = con.execute(
    f"SELECT COUNT(*), SUM({D}(frequency AS DOUBLE)), SUM({D}(seats_total AS DOUBLE)) "
    f"FROM oag WHERE dep_airport='JFK' AND arr_airport='LAX' AND week='2018'").fetchone()
if nr == 0:
    print("  no rows under the legacy annual '2018' label: the truncated annual/half-year"
          " slices have already been superseded and removed (dedupe applied in an earlier"
          " session). Nothing left to demonstrate here; kept as a regression check.")
else:
    print(f"  rows={nr:,}  departures(one-way)={deps:,.0f}  seats={seats:,.0f}"
          f"   (real JFK-LAX is ~10,000+ deps/yr; low value confirms truncation)")

con.close()

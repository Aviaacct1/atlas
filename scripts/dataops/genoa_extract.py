#!/usr/bin/env python3
"""Genoa / Italy - NYC complete analysis pack from the Sabre store. Read-only.
Bidirectional O&D (both directions). NYC = JFK+EWR+LGA. Prints everything for the deck.
Seasonality (monthly) is not derivable: the store is annual O&D with no month field."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import duckdb, csv, os
con = duckdb.connect(_paths.SABRE_DB, read_only=True)
nyc = "('JFK','EWR','LGA')"
YEARS = [2025, 2024]
NAMED = ['FCO', 'MXP', 'LIN', 'BLQ', 'VCE', 'NAP', 'GOA']

# Italian airports from the lookup in C:\Avia
ITAL = []
p = _os.path.join(_paths.AVIA, 'airport_city_country.csv')
if os.path.exists(p):
    for r in csv.DictReader(open(p, encoding="utf-8")):
        if (r.get('country_name') or '').strip().lower() == 'italy':
            ITAL.append(r['airport_code'].strip())
itset = "(" + ",".join(repr(a) for a in ITAL) + ")" if ITAL else "('XXX')"
print(f"Italian airports in lookup: {len(ITAL)}")

def bidir(airset, yr):
    return con.execute(f"""SELECT sum(passengers) FROM sabre WHERE source_year={yr} AND (
      (origin_airport IN {airset} AND destination_airport IN {nyc}) OR
      (destination_airport IN {airset} AND origin_airport IN {nyc}))""").fetchone()[0] or 0

print("="*70); print("OUTPUT 1: Italy-NYC by origin airport (bidirectional), with clean Other + Total")
for yr in YEARS:
    print(f"-- {yr} --")
    nt = 0
    for a in NAMED:
        v = bidir(f"('{a}')", yr); nt += v; print(f"  {a}: {v:,.0f}")
    tot = bidir(itset, yr)
    print(f"  Other Italian airports: {tot-nt:,.0f}")
    print(f"  ITALY TOTAL: {tot:,.0f}")

print("="*70); print("OUTPUT 2: MXP-NYC routing (bidirectional)")
for yr in YEARS:
    tot = bidir("('MXP')", yr)
    direct = con.execute(f"""SELECT sum(passengers) FROM sabre WHERE source_year={yr} AND connecting_airport1 IS NULL AND (
      (origin_airport='MXP' AND destination_airport IN {nyc}) OR (destination_airport='MXP' AND origin_airport IN {nyc}))""").fetchone()[0] or 0
    print(f"-- {yr} --  total {tot:,.0f}  direct {direct:,.0f}  connecting {tot-direct:,.0f}")
    print("   direct by operating carrier:")
    for c, v in con.execute(f"""SELECT operating_airline, sum(passengers) FROM sabre WHERE source_year={yr} AND connecting_airport1 IS NULL AND (
      (origin_airport='MXP' AND destination_airport IN {nyc}) OR (destination_airport='MXP' AND origin_airport IN {nyc}))
      GROUP BY 1 ORDER BY 2 DESC LIMIT 7""").fetchall(): print(f"     {c}: {v:,.0f}")
    print("   connecting by hub:")
    for h, v in con.execute(f"""SELECT connecting_airport1, sum(passengers) FROM sabre WHERE source_year={yr} AND connecting_airport1 IS NOT NULL AND (
      (origin_airport='MXP' AND destination_airport IN {nyc}) OR (destination_airport='MXP' AND origin_airport IN {nyc}))
      GROUP BY 1 ORDER BY 2 DESC LIMIT 6""").fetchall(): print(f"     {h}: {v:,.0f}")
    print("   by point-of-ORIGIN country (proxy for point-of-sale):")
    for c, v in con.execute(f"""SELECT poo_country_name, sum(passengers) FROM sabre WHERE source_year={yr} AND (
      (origin_airport='MXP' AND destination_airport IN {nyc}) OR (destination_airport='MXP' AND origin_airport IN {nyc}))
      GROUP BY 1 ORDER BY 2 DESC LIMIT 4""").fetchall(): print(f"     {c}: {v:,.0f}")

print("="*70); print("OUTPUT 3: GOA-NYC routing (bidirectional), 2025 + 2024")
for yr in YEARS:
    tot = bidir("('GOA')", yr)
    print(f"-- {yr} --  total {tot:,.0f}  direct 0")
    for h, c, v in con.execute(f"""SELECT connecting_airport1, operating_airline, sum(passengers) FROM sabre WHERE source_year={yr}
      AND connecting_airport1 IS NOT NULL AND (
      (origin_airport='GOA' AND destination_airport IN {nyc}) OR (destination_airport='GOA' AND origin_airport IN {nyc}))
      GROUP BY 1,2 ORDER BY 3 DESC LIMIT 10""").fetchall(): print(f"     {h} / {c}: {v:,.0f}")

print("="*70); print("OUTPUT 5: cabin mix + yield")
print("  cabin labels:", [r[0] for r in con.execute("SELECT DISTINCT cabin_class FROM sabre WHERE cabin_class IS NOT NULL").fetchall()])
for yr in YEARS:
    print(f"-- {yr} Italy-NYC cabin split (origin Italy -> NYC) --")
    for cab, v in con.execute(f"""SELECT cabin_class, sum(passengers) FROM sabre WHERE source_year={yr}
      AND origin_airport IN {itset} AND destination_airport IN {nyc} GROUP BY 1 ORDER BY 2 DESC""").fetchall():
        print(f"     {cab}: {v:,.0f}")
    print(f"-- {yr} premium share + pax-weighted yield by origin (Italy -> NYC outbound) --")
    for a in NAMED:
        row = con.execute(f"""SELECT
          sum(passengers),
          sum(CASE WHEN cabin_class IN ('BUSINESS','FIRST','PREMIUM COACH') THEN passengers ELSE 0 END),
          sum(total_revenue_usd)
          FROM sabre WHERE source_year={yr} AND origin_airport='{a}' AND destination_airport IN {nyc}""").fetchone()
        pax, prem, rev = row[0] or 0, row[1] or 0, row[2] or 0
        prem_sh = prem/pax if pax else 0
        yld = rev/pax if pax else 0
        print(f"     {a}: premium {prem_sh:.1%}, yield ${yld:,.0f}")

print("="*70); print("OUTPUT 6: YoY by origin (2024 -> 2025, bidirectional)")
for a in NAMED:
    a24, a25 = bidir(f"('{a}')", 2024), bidir(f"('{a}')", 2025)
    print(f"  {a}: {a24:,.0f} -> {a25:,.0f}  ({(a25/a24-1)*100:+.1f}%)" if a24 else f"  {a}: {a25:,.0f}")
# Italy market average YoY
it24, it25 = bidir(itset, 2024), bidir(itset, 2025)
print(f"  ITALY ALL: {it24:,.0f} -> {it25:,.0f}  ({(it25/it24-1)*100:+.1f}%)")
con.close()

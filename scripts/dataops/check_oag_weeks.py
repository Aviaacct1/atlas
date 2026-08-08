"""Quick coverage check for C:\\Avia\\oag.duckdb - lists every non-weekly period
key per region (monthly / half-year / annual), then a per-year summary.
Author: Avia Solutions.  Usage: py -3.12 check_oag_weeks.py"""
import duckdb

con = duckdb.connect("oag.duckdb", read_only=True)
print("Non-weekly period keys per region:")
for region, week, n in con.execute(
        "SELECT region, week, COUNT(*) FROM oag "
        "WHERE week NOT LIKE '20__-__-__' "
        "GROUP BY region, week ORDER BY region, week").fetchall():
    print(f"  {region:<18} {week:<10} {n:>12,}")

print("\nPeriod-key count per region per year (weekly snapshots excluded):")
for region, year, k, n in con.execute(
        "SELECT region, substr(week,1,4) AS yr, COUNT(DISTINCT week), COUNT(*) FROM oag "
        "WHERE week NOT LIKE '20__-__-__' "
        "GROUP BY region, yr ORDER BY region, yr").fetchall():
    print(f"  {region:<18} {year}  {k:>3} periods  {n:>12,} rows")

print("\nWeekly snapshot weeks still in store:")
for week, n in con.execute(
        "SELECT week, COUNT(*) FROM oag WHERE week LIKE '20__-__-__' "
        "GROUP BY week ORDER BY week").fetchall():
    print(f"  {week}  {n:>12,}")
con.close()

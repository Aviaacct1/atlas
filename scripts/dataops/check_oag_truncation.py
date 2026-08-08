"""Truncation check for the single-file OAG regions (NA, SWP, Latin America,
and the H1/H2 files). If an annual/half-year export hit Excel's 1,048,576-row
ceiling, routes present in that year's WEEKLY snapshot will be missing from it.
For each region-year, compares distinct (carrier, dep_airport, arr_airport)
in the May weekly snapshot vs the annual/half-year data covering that week.
Coverage well below ~97% = truncated export, re-pull in smaller segments.
Author: Avia Solutions.  Usage: py -3.12 check_oag_truncation.py"""
import duckdb

con = duckdb.connect("oag.duckdb", read_only=True)
years = ["2015", "2016", "2017", "2018", "2019", "2024", "2025"]
weekly = {r[0] for r in con.execute("SELECT DISTINCT week FROM oag WHERE week LIKE '20__-__-__'").fetchall()}

print(f"{'region':<18} {'year':<5} {'weekly wk':<11} {'routes wk':>9} {'covered':>8} {'coverage':>9}")
for region in [r[0] for r in con.execute("SELECT DISTINCT region FROM oag ORDER BY region").fetchall()]:
    for y in years:
        wk = next((w for w in sorted(weekly) if w.startswith(y + "-05")), None)
        if not wk:
            continue
        n = con.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT carrier, dep_airport, arr_airport FROM oag "
            "WHERE region=? AND week=?)", [region, wk]).fetchone()[0]
        if n == 0:
            continue
        cov = con.execute(
            "SELECT COUNT(*) FROM "
            "(SELECT DISTINCT carrier, dep_airport, arr_airport FROM oag WHERE region=? AND week=?) w "
            "WHERE EXISTS (SELECT 1 FROM oag a WHERE a.region=? "
            "  AND a.week NOT LIKE '20__-__-__' AND a.week LIKE ? "
            "  AND a.carrier=w.carrier AND a.dep_airport=w.dep_airport AND a.arr_airport=w.arr_airport)",
            [region, wk, region, y + "%"]).fetchone()[0]
        pct = cov / n * 100
        flag = "   <-- CHECK" if pct < 97 else ""
        print(f"{region:<18} {y:<5} {wk:<11} {n:>9,} {cov:>8,} {pct:>8.1f}%{flag}")
con.close()

#!/usr/bin/env python3
"""
Avia Solutions - QSI demand-extract generator (first cut).
Builds the connecting-demand extract for a route from the DuckDB store, on the
method reverse-engineered from Ollie's 2015 model:
  - origins: the catchment board points (e.g. SFO, LAX, SAN)
  - destinations: the in-scope set (points served beyond the hub within the
    connection window). For now read from a scope table; in phase 4 this comes
    from running the connection builder against OAG.
  - both directions combined (2013/2015 are directional), keyed on the catchment end
  - a carrier credited where it operates any leg
  - aggregated by destination city, split direct/indirect, all cabins summed
Output: a per-destination demand table (CSV) plus headline totals.

Run: py -3.12 scripts\dataops\sabre_generate_extract.py
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import sys, subprocess, os, argparse
try:
    import duckdb
except ImportError:
    subprocess.check_call([sys.executable,"-m","pip","install","--quiet","duckdb"]); import duckdb

def L(t): return "(" + ",".join("'" + str(x).replace("'","''") + "'" for x in t) + ")"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db", default=_paths.SABRE_DB)
    ap.add_argument("--lookup", default=_os.path.join(_paths.AVIA, 'airport_city_country.csv'))
    ap.add_argument("--scope", default=_os.path.join(_paths.AVIA, 'destination_scope_LHR.csv'))
    ap.add_argument("--year", type=int, default=2013)
    ap.add_argument("--catchment", default="SFO,LAX,SAN")
    ap.add_argument("--carrier", default="BA")
    ap.add_argument("--out", default=_os.path.join(_paths.AVIA, 'generated_extract_2013.csv'))
    a=ap.parse_args()
    catch=tuple(x.strip() for x in a.catchment.split(","))
    con=duckdb.connect(a.db, read_only=True)
    con.execute(f"CREATE TEMP TABLE lk AS SELECT * FROM read_csv_auto('{a.lookup}', header=true)")
    con.execute(f"CREATE TEMP TABLE sc AS SELECT * FROM read_csv_auto('{a.scope}', header=true)")
    con.execute("CREATE TEMP TABLE scope_in AS SELECT DISTINCT upper(trim(arr_airport)) ap FROM sc WHERE upper(trim(include))='IN'")
    nscope=con.execute("SELECT count(*) FROM scope_in").fetchone()[0]

    cr=a.carrier
    leg_op=f"('{cr}' IN (leg1_op_aln,leg2_op_aln,leg3_op_aln,leg4_op_aln) OR operating_airline='{cr}')"
    # both directions, normalised so the catchment end is the origin
    base=f"""
    WITH m AS (
      SELECT origin_airport oa, destination_airport da, itinerary, passengers, total_revenue_usd rev,
             {leg_op} AS is_carrier
      FROM sabre
      WHERE source_year={a.year}
        AND ( (origin_airport IN {L(catch)} AND destination_airport IN (SELECT ap FROM scope_in))
           OR (destination_airport IN {L(catch)} AND origin_airport IN (SELECT ap FROM scope_in)) )
        -- single connection only: non-stop, or exactly one connecting point
        -- (excludes multi-stop and double-connections over both hubs), per Ollie's rule
        AND (itinerary='NON-STOP' OR (connecting_airport1 IS NOT NULL AND connecting_airport2 IS NULL))
    ),
    norm AS (
      SELECT CASE WHEN oa IN {L(catch)} THEN oa ELSE da END AS catch_ap,
             CASE WHEN oa IN {L(catch)} THEN da ELSE oa END AS dest_ap,
             CASE WHEN itinerary='NON-STOP' THEN 'Direct' ELSE 'Indirect' END di,
             passengers, rev, is_carrier
      FROM m
    )
    SELECT catch_ap AS mod_org,
           dest_ap,
           COALESCE(lk.city_code, dest_ap) AS dest_city,
           COALESCE(lk.city_name, '') AS dest_city_name,
           COALESCE(lk.country_name, '') AS dest_country,
           di AS direct_indirect,
           round(sum(passengers)) AS passengers,
           round(sum(rev)) AS revenue_usd,
           round(sum(CASE WHEN is_carrier THEN passengers ELSE 0 END)) AS carrier_pax
    FROM norm LEFT JOIN lk ON upper(trim(lk.airport_code))=norm.dest_ap
    GROUP BY 1,2,3,4,5,6
    """
    con.execute(f"CREATE TEMP TABLE ext AS {base}")
    tot=con.execute("SELECT round(sum(passengers)), round(sum(carrier_pax)) FROM ext").fetchone()
    di=con.execute("SELECT direct_indirect, round(sum(passengers)) FROM ext GROUP BY 1 ORDER BY 2 DESC").fetchall()
    con.execute(f"COPY (SELECT * FROM ext ORDER BY passengers DESC) TO '{a.out}' (HEADER, DELIMITER ',')")
    nrows=con.execute("SELECT count(*) FROM ext").fetchone()[0]
    print(f"Generator: {a.carrier} {a.catchment} <-> in-scope ({nscope} airports), year {a.year}, both directions")
    print(f"  total market passengers : {tot[0]:>12,.0f}")
    print(f"  {a.carrier} (operates a leg)   : {tot[1]:>12,.0f}")
    for d,p in di: print(f"  {d:>9}: {p:>12,.0f}")
    print(f"  wrote {nrows:,} destination rows to {a.out}")
    print("\n  top 12 destination cities by market passengers:")
    for r in con.execute("SELECT dest_city, dest_country, round(sum(passengers)) p FROM ext GROUP BY 1,2 ORDER BY p DESC LIMIT 12").fetchall():
        print(f"     {r[0]:>4} {str(r[1])[:22]:<22} {r[2]:>12,.0f}")
    con.close()

if __name__=="__main__":
    main()

#!/usr/bin/env python3
"""
Avia Solutions - QSI demand-extract generator (drop-in for the manual Sabre pull).
Emits the 20-column Sabre layout the demand provider reads (midt_demand_provider.py),
cabin summed out, with a SPLIT market weighting applied: a larger gross-up on direct
(Sabre under-captures point-to-point) and a smaller one on connecting (well captured).

Derived from the BA LHR-SJC reference (store vs Ollie's extract):
  direct  factor ~1.166   indirect factor ~1.044
These reproduce the analyst extract within <0.1% at direct, indirect AND total levels.
PROVISIONAL pending Antonio's confirmation of the actual Sabre weighting and a
cross-check on the Cathay route. Override with --factor-direct / --factor-indirect.

Run: py -3.12 scripts\dataops\sabre_generate_demand.py --catchment SFO,LAX,SAN --year 2013 --combine-directions
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import sys, subprocess, argparse
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
    ap.add_argument("--catchment", default="SFO,LAX,SAN")
    ap.add_argument("--year", type=int, default=2013)
    ap.add_argument("--factor-direct", type=float, default=1.166)
    ap.add_argument("--factor-indirect", type=float, default=1.044)
    ap.add_argument("--combine-directions", action="store_true")
    ap.add_argument("--out", default=_os.path.join(_paths.AVIA, 'demand_extract.csv'))
    a=ap.parse_args()
    catch=tuple(x.strip() for x in a.catchment.split(","))
    fd, fi = a.factor_direct, a.factor_indirect
    con=duckdb.connect(a.db, read_only=True)
    con.execute(f"CREATE TEMP TABLE lk AS SELECT upper(trim(airport_code)) ap, city_code, city_name, country_name FROM read_csv_auto('{a.lookup}', header=true)")
    con.execute(f"CREATE TEMP TABLE scin AS SELECT DISTINCT upper(trim(arr_airport)) ap FROM read_csv_auto('{a.scope}', header=true) WHERE upper(trim(include))='IN'")

    single_conn = "AND (itinerary='NON-STOP' OR (connecting_airport1 IS NOT NULL AND connecting_airport2 IS NULL))"
    if a.combine_directions:
        sel=f"""SELECT CASE WHEN origin_airport IN {L(catch)} THEN origin_airport ELSE destination_airport END AS oa,
                 CASE WHEN origin_airport IN {L(catch)} THEN destination_airport ELSE origin_airport END AS da,
                 itinerary, operating_airline, connecting_airport1, connecting_airport2, connecting_airport3,
                 leg1_op_aln, leg2_op_aln, leg3_op_aln, leg4_op_aln, passengers, total_revenue_usd
            FROM sabre WHERE source_year={a.year}
              AND ( (origin_airport IN {L(catch)} AND destination_airport IN (SELECT ap FROM scin))
                 OR (destination_airport IN {L(catch)} AND origin_airport IN (SELECT ap FROM scin)) ) {single_conn}"""
    else:
        sel=f"""SELECT origin_airport AS oa, destination_airport AS da, itinerary, operating_airline,
                 connecting_airport1, connecting_airport2, connecting_airport3,
                 leg1_op_aln, leg2_op_aln, leg3_op_aln, leg4_op_aln, passengers, total_revenue_usd
            FROM sabre WHERE source_year={a.year}
              AND origin_airport IN {L(catch)} AND destination_airport IN (SELECT ap FROM scin) {single_conn}"""

    q=f"""
    WITH base AS ({sel}),
    tagged AS (
      SELECT *,
        CASE WHEN itinerary='NON-STOP' THEN 'Direct' ELSE 'Indirect' END AS di,
        CASE WHEN itinerary='NON-STOP' THEN {fd} ELSE {fi} END AS f
      FROM base)
    SELECT
      COALESCE(lo.city_code, t.oa) AS "Mod Org City",
      COALESCE(ld.city_code, t.da) AS "Mod Dest City",
      COALESCE(ld.city_name, '')   AS "Mod Dest City Name",
      COALESCE(ld.country_name,'') AS "Mod Dest Country",
      COALESCE(lo.city_code, t.oa) AS "Org City",
      COALESCE(ld.city_code, t.da) AS "Dest City",
      t.di AS "Direct/Indirect",
      t.oa AS "Origin", t.da AS "Destination", t.operating_airline AS "OperatingAirline",
      t.connecting_airport1 AS "ConnectPoint1", t.connecting_airport2 AS "ConnectPoint2", t.connecting_airport3 AS "ConnectPoint3",
      t.leg1_op_aln AS "Segment1Airline", t.leg2_op_aln AS "Segment2Airline", t.leg3_op_aln AS "Segment3Airline", t.leg4_op_aln AS "Segment4Airline",
      round(sum(t.passengers * t.f), 2)        AS "Passengers",
      round(sum(t.total_revenue_usd * t.f), 2) AS "RevenueInUSD",
      round(CASE WHEN sum(t.passengers)>0 THEN sum(t.total_revenue_usd)/sum(t.passengers) ELSE 0 END, 2) AS "AvgFareInUSD"
    FROM tagged t
    LEFT JOIN lk lo ON lo.ap=t.oa
    LEFT JOIN lk ld ON ld.ap=t.da
    GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17
    """
    con.execute(f"CREATE TEMP TABLE demand AS {q}")
    n=con.execute("SELECT count(*) FROM demand").fetchone()[0]
    tot=con.execute('SELECT round(sum("Passengers")) FROM demand').fetchone()[0]
    di=con.execute('SELECT "Direct/Indirect", round(sum("Passengers")) FROM demand GROUP BY 1 ORDER BY 2 DESC').fetchall()
    con.execute(f"COPY (SELECT * FROM demand ORDER BY \"Passengers\" DESC) TO '{a.out}' (HEADER, DELIMITER ',')")
    print(f"Demand extract: {a.catchment} -> in-scope, year {a.year}, factors direct={fd} indirect={fi}, combine_dirs={a.combine_directions}")
    print(f"  rows written     : {n:,}  -> {a.out}")
    print(f"  total passengers : {tot:,.0f}")
    for d,p in di: print(f"  {d:>9}: {p:>12,.0f}")
    con.close()

if __name__=="__main__":
    main()

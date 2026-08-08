#!/usr/bin/env python3
"""Avia Solutions - BT2 Stage 2: monthly nonstop series per candidate pair (OAG).
For cohort L, pulls per (pair, carrier, month) nonstop ops/seats for years L-1 and L
from the monthly store (split months collapsed, region duplicates deduped by max).
Writes bt2/pair_months_L.csv. One cohort per call.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import argparse
import duckdb

BT2 = _os.path.join(_paths.AVIA, "bt2")
OAG = _paths.OAG_DB

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--cohort", type=int, required=True)
    L = ap.parse_args().cohort
    con = duckdb.connect(OAG, read_only=True)
    con.execute("SET memory_limit='3GB'"); con.execute("SET threads=4")
    con.execute(f"""
    CREATE TEMP TABLE cand AS SELECT a, b FROM read_csv('{BT2}/launches_{L}.csv', header=true)
    """)
    con.execute(f"""
    COPY (
      WITH m AS (
        SELECT least(dep_airport, arr_airport) a, greatest(dep_airport, arr_airport) b,
               carrier, substr(week,1,7) mon,
               CASE WHEN week LIKE '%p__' THEN 'split' ELSE 'month' END kt, region,
               count(*) ops, sum(try_cast(seats_total as bigint)) seats
        FROM oag
        WHERE service_type='J' AND try_cast(stops as int)=0
          AND (week LIKE '{L-1}-__' OR week LIKE '{L-1}-__p__' OR week LIKE '{L}-__' OR week LIKE '{L}-__p__')
          AND least(dep_airport, arr_airport) IN (SELECT a FROM cand)
        GROUP BY 1,2,3,4,5,6
      ),
      r AS (  -- region duplicates are exact copies: keep one per (pair,carrier,mon,key-type)
        SELECT a, b, carrier, mon, kt, max(ops) ops, max(seats) seats
        FROM m GROUP BY 1,2,3,4,5
      ),
      d AS (  -- a month present both whole and split: prefer the whole-month key
        SELECT a, b, carrier, mon,
               coalesce(max(ops)  FILTER (kt='month'), max(ops)  FILTER (kt='split')) ops,
               coalesce(max(seats) FILTER (kt='month'), max(seats) FILTER (kt='split')) seats
        FROM r GROUP BY 1,2,3,4
      )
      SELECT d.* FROM d JOIN cand ON cand.a=d.a AND cand.b=d.b
      ORDER BY d.a, d.b, d.mon
    ) TO '{BT2}/pair_months_{L}.csv' (HEADER)
    """)
    n = con.execute(f"SELECT count(*), count(distinct a||'-'||b) FROM read_csv('{BT2}/pair_months_{L}.csv', header=true)").fetchone()
    print(f"cohort {L}: {n[0]} pair-carrier-months, {n[1]} pairs with OAG nonstop service")

if __name__ == "__main__":
    main()

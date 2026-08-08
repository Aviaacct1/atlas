"""Diagnose the OAG store before any panel is built from it. Author: Avia Solutions.

The store holds OAG schedule SERVICES, and two things in it will inflate a peak hour
count if they are not handled, both silently and both plausibly:

  dup_marker    OAG carries the same physical flight once per marketing carrier on a
                codeshare. Counting every row would multiply movements and seats on
                exactly the busiest routes at the busiest airports.
  service_type  Freight, charter, positioning and general aviation records sit
                alongside scheduled passenger services. The model convention is the
                passenger basis, so non-passenger services do not belong in it.

A third risk is period overlap: the store is built from monthly downloads, and the
repo already carries a dedupe_oag_periods routine, so overlapping effective periods
would double count the same operating day.

This script reports what is actually in the store. Nothing is assumed and nothing is
written. Read the output, then set the filter in sources.yaml oag_schedules.filter.

    cd C:\\Avia\\avia_forecast_build
    python scripts\\inspect_oag_store.py
    python scripts\\inspect_oag_store.py --airport LHR --year 2019
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb
from avia_forecast.ingest import oag_peak


def show(con, title, sql, limit=25):
    print()
    print(title)
    print("-" * len(title))
    try:
        rows = con.execute(sql).fetchall()
    except Exception as exc:
        print(f"query failed: {exc}")
        return []
    if not rows:
        print("(no rows)")
        return []
    cols = [d[0] for d in con.description]
    print(" | ".join(cols))
    for r in rows[:limit]:
        print(" | ".join("" if v is None else str(v) for v in r))
    if len(rows) > limit:
        print(f"... {len(rows) - limit} more")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=None)
    ap.add_argument("--airport", default="LHR", help="airport for the worked sample")
    ap.add_argument("--year", type=int, default=None, help="year for the worked sample")
    args = ap.parse_args()

    m = oag_peak.mapping()
    t = m["table"]
    path = oag_peak.store_path(args.store)
    print(f"store: {path}")
    print(f"table: {t}")
    con = duckdb.connect(str(path), read_only=True)

    show(con, "Rows, airports and years", f"""
        SELECT COUNT(*) AS rows, COUNT(DISTINCT "{m['airport']}") AS dep_airports,
               MIN(year) AS min_year, MAX(year) AS max_year,
               COUNT(DISTINCT year) AS n_years FROM "{t}" """)

    show(con, "Rows by year (a short year is an incomplete ingest, not a quiet year)", f"""
        SELECT year, COUNT(*) AS rows, COUNT(DISTINCT week) AS weeks,
               MIN(CAST("{m['eff_from']}" AS DATE)) AS first_eff,
               MAX(CAST("{m['eff_to']}" AS DATE))   AS last_eff
        FROM "{t}" GROUP BY year ORDER BY year """)

    show(con, "service_type: which are passenger services?", f"""
        SELECT service_type, COUNT(*) AS rows, SUM(TRY_CAST(seats AS DOUBLE)) AS seats,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_rows
        FROM "{t}" GROUP BY service_type ORDER BY rows DESC """)

    show(con, "dup_marker: codeshare duplicates", f"""
        SELECT dup_marker, COUNT(*) AS rows,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_rows
        FROM "{t}" GROUP BY dup_marker ORDER BY rows DESC """)

    show(con, "days_of_op patterns (the top few; expansion matches digits against isodow)", f"""
        SELECT "{m['days_of_op']}" AS days_of_op, COUNT(*) AS rows
        FROM "{t}" GROUP BY 1 ORDER BY rows DESC LIMIT 12 """)

    show(con, "local_dep_time format (expansion parses HHMM after stripping any colon)", f"""
        SELECT CAST("{m['dep_time']}" AS VARCHAR) AS sample,
               LENGTH(CAST("{m['dep_time']}" AS VARCHAR)) AS len, COUNT(*) AS rows
        FROM "{t}" GROUP BY 1, 2 ORDER BY rows DESC LIMIT 8 """)

    show(con, "Effective period lengths (a 7-day span means one row per service per week)", f"""
        SELECT DATE_DIFF('day', CAST("{m['eff_from']}" AS DATE),
                         CAST("{m['eff_to']}" AS DATE)) + 1 AS span_days,
               COUNT(*) AS rows
        FROM "{t}" GROUP BY 1 ORDER BY rows DESC LIMIT 10 """)

    yr = args.year
    if yr is None:
        got = con.execute(f'SELECT MAX(year) FROM "{t}"').fetchone()
        yr = got[0] if got else None

    a = args.airport
    print()
    print(f"Worked sample: {a}, {yr}")
    print("=" * 40)

    show(con, "Overlap check: operating dates counted once, or more than once?", f"""
        WITH b AS (
          SELECT CAST("{m['eff_from']}" AS DATE) AS lo, CAST("{m['eff_to']}" AS DATE) AS hi
          FROM "{t}" WHERE "{m['airport']}" = '{a}' AND year = {yr}
        ), cal AS (
          SELECT UNNEST(generate_series((SELECT MIN(lo) FROM b), (SELECT MAX(hi) FROM b),
                                        INTERVAL 1 DAY))::DATE AS d
        )
        SELECT cal.d AS operating_date, COUNT(*) AS rows_covering_that_date
        FROM "{t}" x JOIN cal
          ON cal.d BETWEEN CAST(x."{m['eff_from']}" AS DATE) AND CAST(x."{m['eff_to']}" AS DATE)
         AND strpos(CAST(x."{m['days_of_op']}" AS VARCHAR), CAST(isodow(cal.d) AS VARCHAR)) > 0
        WHERE x."{m['airport']}" = '{a}' AND x.year = {yr}
        GROUP BY 1 ORDER BY 1 LIMIT 14 """)

    show(con, "Expansion cross-check: expanded operations against SUM(frequency)", f"""
        WITH b AS (
          SELECT CAST("{m['eff_from']}" AS DATE) AS lo, CAST("{m['eff_to']}" AS DATE) AS hi
          FROM "{t}" WHERE "{m['airport']}" = '{a}' AND year = {yr}
        ), cal AS (
          SELECT UNNEST(generate_series((SELECT MIN(lo) FROM b), (SELECT MAX(hi) FROM b),
                                        INTERVAL 1 DAY))::DATE AS d
        ), expanded AS (
          SELECT COUNT(*) AS ops FROM "{t}" x JOIN cal
            ON cal.d BETWEEN CAST(x."{m['eff_from']}" AS DATE) AND CAST(x."{m['eff_to']}" AS DATE)
           AND strpos(CAST(x."{m['days_of_op']}" AS VARCHAR), CAST(isodow(cal.d) AS VARCHAR)) > 0
          WHERE x."{m['airport']}" = '{a}' AND x.year = {yr}
        )
        SELECT (SELECT ops FROM expanded) AS expanded_operations,
               (SELECT SUM(TRY_CAST(frequency AS DOUBLE)) FROM "{t}" WHERE "{m['airport']}" = '{a}' AND year = {yr}) AS sum_frequency,
               (SELECT SUM(TRY_CAST(seats AS DOUBLE)) FROM "{t}" WHERE "{m['airport']}" = '{a}' AND year = {yr}) AS sum_seats_per_op,
               (SELECT SUM(TRY_CAST(seats_total AS DOUBLE)) FROM "{t}" WHERE "{m['airport']}" = '{a}' AND year = {yr}) AS sum_seats_total """)

    show(con, "Busiest local hours on the raw rows (sanity, not the panel figure)", f"""
        SELECT substr(lpad(replace(CAST("{m['dep_time']}" AS VARCHAR), ':', ''), 4, '0'), 1, 2) AS hh,
               COUNT(*) AS service_rows, SUM(TRY_CAST(seats AS DOUBLE)) AS seats_per_op
        FROM "{t}" WHERE "{m['airport']}" = '{a}' AND year = {yr}
        GROUP BY 1 ORDER BY hh """, limit=24)

    show(con, "Snapshot overlap by year: how many rows cover one mid-year date", f"""
        WITH probe AS (SELECT UNNEST([DATE '2016-06-15', DATE '2019-06-15', DATE '2025-06-15']) AS d)
        SELECT x.year, probe.d AS probe_date, COUNT(*) AS rows_covering,
               COUNT(DISTINCT x.week) AS distinct_weeks_covering
        FROM "{t}" x JOIN probe
          ON probe.d BETWEEN CAST(x."{m['eff_from']}" AS DATE) AND CAST(x."{m['eff_to']}" AS DATE)
         AND strpos(CAST(x."{m['days_of_op']}" AS VARCHAR), CAST(isodow(probe.d) AS VARCHAR)) > 0
        WHERE x."{m['airport']}" = '{a}'
        GROUP BY 1, 2 ORDER BY 1, 2 """)

    show(con, f"Effect of the candidate filter on one date ({a})", f"""
        WITH probe AS (SELECT DATE '2019-06-15' AS d),
        cov AS (
          SELECT x.* FROM "{t}" x JOIN probe
            ON probe.d BETWEEN CAST(x."{m['eff_from']}" AS DATE) AND CAST(x."{m['eff_to']}" AS DATE)
           AND strpos(CAST(x."{m['days_of_op']}" AS VARCHAR), CAST(isodow(probe.d) AS VARCHAR)) > 0
          WHERE x."{m['airport']}" = '{a}'
        )
        SELECT 'all rows' AS basis, COUNT(*) AS departures FROM cov
        UNION ALL SELECT 'dup_marker = 0', COUNT(*) FROM cov WHERE dup_marker = '0'
        UNION ALL SELECT 'dup_marker = 0, one week only',
               COUNT(*) FROM cov WHERE dup_marker = '0'
                 AND week = (SELECT MAX(week) FROM cov WHERE dup_marker = '0') """)

    con.close()
    print()
    print("What to do with this:")
    print("  1. Set sources.yaml oag_schedules.filter from the service_type and dup_marker tables.")
    print("     The passenger, non-duplicate rows are the ones the panel should see.")
    print("  2. If rows_covering_that_date jumps around rather than holding roughly steady,")
    print("     the effective periods overlap and the store needs the dedupe pass first.")
    print("  3. If expanded_operations and sum_frequency disagree materially, the days_of_op")
    print("     expansion is not reproducing OAG's own count and must be reconciled before")
    print("     any panel is fitted.")
    print("  4. Send me this output and I will set the filter and the mapping.")


if __name__ == "__main__":
    main()

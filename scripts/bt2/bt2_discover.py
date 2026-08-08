#!/usr/bin/env python3
"""Avia Solutions - BT2 Stage 1: launch discovery per cohort (Sabre).
Cohorts 2016-2019 (+2025). Virgin pair: nonstop >=1500 pax in L, <500 in L-1 and L-2.
Writes C:\\Avia\\bt2\\launches_L.csv per cohort. Run: one cohort per call (45s cap).
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import argparse, csv, math, os
import duckdb

BT2 = _os.path.join(_paths.AVIA, "bt2")
SABRE = _paths.SABRE_DB
THR, VIRGIN_FRAC, MINBASE, MAXRATIO = 1500.0, 3.0, 2000.0, 5.0

def gcd_map():
    import airportsdata
    ap = airportsdata.load('IATA')
    return {k: (v['lat'], v['lon']) for k, v in ap.items()}, {k: v.get('country','') for k, v in ap.items()}

def gc(coords, x, y):
    if x not in coords or y not in coords: return None
    (la1, lo1), (la2, lo2) = coords[x], coords[y]
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = math.radians(la2-la1), math.radians(lo2-lo1)
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*6371*math.asin(math.sqrt(h))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--cohort", type=int, required=True)
    L = ap.parse_args().cohort
    os.makedirs(BT2, exist_ok=True)
    con = duckdb.connect(SABRE, read_only=True)
    con.execute("SET memory_limit='3GB'")
    q = f"""
    WITH ns AS (
      SELECT least(origin_airport,destination_airport) a,
             greatest(origin_airport,destination_airport) b,
             source_year y, sum(passengers) p
      FROM sabre WHERE itinerary='NON-STOP' AND source_year IN ({L},{L-1},{L-2})
        AND origin_airport IS NOT NULL AND destination_airport IS NOT NULL
        AND origin_airport<>destination_airport
      GROUP BY 1,2,3),
    cur AS (SELECT a,b,p FROM ns WHERE y={L} AND p>={THR}),
    v AS (SELECT c.a,c.b,c.p FROM cur c
      LEFT JOIN ns p1 ON p1.a=c.a AND p1.b=c.b AND p1.y={L-1}
      LEFT JOIN ns p2 ON p2.a=c.a AND p2.b=c.b AND p2.y={L-2}
      WHERE coalesce(p1.p,0)<{THR/VIRGIN_FRAC} AND coalesce(p2.p,0)<{THR/VIRGIN_FRAC}),
    base AS (
      SELECT least(origin_airport,destination_airport) a,
             greatest(origin_airport,destination_airport) b, sum(passengers) bm
      FROM sabre WHERE source_year={L-1} GROUP BY 1,2),
    car AS (
      SELECT least(origin_airport,destination_airport) a,
             greatest(origin_airport,destination_airport) b,
             operating_airline, sum(passengers) cp,
             row_number() OVER (PARTITION BY least(origin_airport,destination_airport),
               greatest(origin_airport,destination_airport) ORDER BY sum(passengers) DESC) rn
      FROM sabre WHERE itinerary='NON-STOP' AND source_year={L} GROUP BY 1,2,3)
    SELECT v.a, v.b, v.p launch_pax, coalesce(base.bm,0) base_mkt, car.operating_airline carrier
    FROM v LEFT JOIN base ON base.a=v.a AND base.b=v.b
           LEFT JOIN car  ON car.a=v.a AND car.b=v.b AND car.rn=1
    """
    rows = con.execute(q).fetchall()
    coords, ctry = gcd_map()
    out, dropped = [], 0
    for a, b, lp, bm, carrier in rows:
        if bm < MINBASE or lp > MAXRATIO * bm:
            dropped += 1; continue
        d = gc(coords, a, b)
        out.append((L, a, b, round(lp), round(bm), carrier or "?",
                    round(d) if d else "", ctry.get(a,""), ctry.get(b,"")))
    out.sort(key=lambda r: -r[3])
    with open(f"{BT2}/launches_{L}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cohort","a","b","launch_pax","base_mkt","carrier","gcd_km","ctry_a","ctry_b"])
        w.writerows(out)
    print(f"cohort {L}: {len(rows)} virgin candidates, {dropped} dropped (base<{MINBASE:.0f} or ratio>{MAXRATIO:.0f}), {len(out)} kept")

if __name__ == "__main__":
    main()

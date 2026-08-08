#!/usr/bin/env python3
"""
Avia Solutions - GOA-NYC QSI test run (store-driven, experimental).
==================================================================
First end-to-end QSI run straight from the OAG DuckDB store (no spreadsheet load):
pull the GOA-NYC market legs, build connections over every European hub, apply
real MCT + circuity, score QSI, and (a) compare the baseline hub split against the
Sabre observed routing, (b) score a hypothetical GOA-JFK nonstop's raw QSI capture.

This is a VALIDATION harness, not a forecast. Raw QSI fair-share is one input; the
calibrated method maps it to bookings separately.

  py -3.12 C:\\Avia\\goa_qsi_test.py
  py -3.12 C:\\Avia\\goa_qsi_test.py --week 2025-05-26 --freqs 3,5,7 --block 510
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import argparse, os, sys, math
from collections import defaultdict

# --- locate the app package (connection_builder, schedule_chain, config) ---
APP_CANDIDATES = [
    _paths.QSI_APP,
    os.path.join(os.path.dirname(__file__), "app"),
    _paths.QSI_APP,
]

def _import_app(extra=None):
    for p in ([extra] if extra else []) + APP_CANDIDATES:
        if p and os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)
    import connection_builder as CB
    import schedule_chain as SC
    return CB, SC

CNX = {'ONLINE': 1.0, 'ALLIANCE': 0.615, 'INTERLINING': 0.25}

def _et(el, mn):
    x = (el - mn) / 60.0
    return 1.0 if x <= 0 else 1.0 / ((int(x / 0.1) + 1) ** 0.8)


def load_market_legs(con, CB, week, origin, nyc):
    nycsql = "(" + ",".join(f"'{a}'" for a in nyc) + ")"
    rows = con.execute(f"""SELECT carrier,flight_no,dep_airport,arr_airport,dep_terminal,arr_terminal,
      dep_city,arr_city,dep_country,arr_country,local_dep_time,local_arr_time,days_of_op,arr_days_of_op,
      flying_time,elapsed_time,alliance,carrier_category
      FROM oag WHERE week=? AND (dep_airport=? OR arr_airport IN {nycsql})""", [week, origin]).fetchall()
    def hhmm(v):
        try: return CB.parse_time_hhmm(v)
        except Exception: return None
    legs = []
    for r in rows:
        (car, fn, dep, arr, dt, at, dc, ac, dctry, actry, ldt, lat, dop, adop, fly, el, alli, cat) = r
        L = {'carrier': str(car).strip(), 'flight_no': str(fn or '').strip(),
             'dep_airport': str(dep).strip(), 'arr_airport': str(arr).strip(),
             'dep_terminal': str(dt or '').strip(), 'arr_terminal': str(at or '').strip(),
             'dep_city': str(dc or '').strip(), 'arr_city': str(ac or '').strip(),
             'dep_country': str(dctry or '').strip(), 'arr_country': str(actry or '').strip(),
             'dep_time_mins': hhmm(ldt), 'arr_time_mins': hhmm(lat),
             'flying_mins': CB._parse_duration_mins(fly or el),
             'dep_day_set': CB.parse_days_string(dop), 'arr_day_set': CB.parse_days_string(adop or dop),
             'alliance': str(alli or '').strip(), 'carrier_category': str(cat or '').strip(), 'id': len(legs)}
        L['dom_int'] = CB.get_dom_int(L['dep_country'], L['arr_country'])
        legs.append(L)
    return legs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=_paths.OAG_DB)
    ap.add_argument("--week", default="2025-05-26")
    ap.add_argument("--origin", default="GOA")
    ap.add_argument("--nyc", default="JFK,EWR,LGA")
    ap.add_argument("--freqs", default="3,5,7")
    ap.add_argument("--block", type=int, default=0, help="proposed nonstop block mins (0 = estimate from GCD)")
    ap.add_argument("--circuity", type=float, default=1.25)
    ap.add_argument("--app", default=None, help="path to the app package if not auto-found")
    # Sabre observed routing for the comparison line (GOA-NYC 2025, by hub %)
    ap.add_argument("--sabre", default="FCO:50,MUC:27,AMS:22")
    a = ap.parse_args()
    CB, SC = _import_app(a.app)
    import duckdb
    nyc = tuple(a.nyc.split(","))

    con = duckdb.connect(a.db, read_only=True)
    legs = load_market_legs(con, CB, a.week, a.origin, nyc)
    leg1 = [l for l in legs if l['dep_airport'] == a.origin]
    leg2 = [l for l in legs if l['arr_airport'] in nyc]
    print(f"{a.origin}-NYC QSI test, OAG week {a.week}")
    print(f"  legs pulled {len(legs):,}  ({a.origin} departures {len(leg1)}, NYC arrivals {len(leg2)})")

    alliances = SC.alliances_from_legs(legs) or CB.load_alliance_data()
    lcc = SC.lcc_from_legs(legs)
    mct, mctsrc = {}, "default 90 (no master)"
    try:
        from config import MCT_MASTER
        mct = CB.load_mct_data(str(MCT_MASTER), 90)
        mctsrc = f"MCT master ({len(mct)} entries)" if mct else "default 90 (master not reachable)"
    except Exception:
        pass
    coords = SC.load_airport_coords()
    valid, _ = CB.build_connections(leg1, leg2, alliances, mct, lcc, 20, 720, 90, hub_airport=None)
    valid = SC.circuity_filter(valid, coords, a.circuity)
    print(f"  connections after MCT+circuity {len(valid):,}  (alliance grps {len(alliances)}, LCC excl {len(lcc)}, {mctsrc})")
    if not valid:
        print("  no connections; check week/airports."); return

    mn = min(c['elapsed_time'] for c in valid)
    hub_q = defaultdict(float); route_q = defaultdict(float); tot = 0.0
    for c in valid:
        q = c['frequency'] * _et(c['elapsed_time'], mn) * CNX.get(c['cnx_type'], 0)
        hub_q[c['cnx_airport']] += q; route_q[(c['cnx_airport'], c['leg2_carrier'])] += q; tot += q
    sabre = dict((p.split(":")[0], p.split(":")[1]) for p in a.sabre.split(",")) if a.sabre else {}
    print(f"\nBASELINE {a.origin}-NYC QSI by HUB   (Sabre observed in brackets):")
    for h, q in sorted(hub_q.items(), key=lambda x: -x[1])[:8]:
        sv = f"  [Sabre {sabre[h]}%]" if h in sabre else ""
        print(f"   {h}: {q/tot:5.1%}{sv}")
    print("  top routings (hub/operating carrier):")
    for (h, cc), q in sorted(route_q.items(), key=lambda x: -x[1])[:8]:
        print(f"   {h}/{cc}: {q/tot:5.1%}")

    # proposed nonstop
    def gc(x, y):
        (la1, lo1), (la2, lo2) = coords[x], coords[y]
        p1, p2 = math.radians(la1), math.radians(la2); dp, dl = math.radians(la2-la1), math.radians(lo2-lo1)
        h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
        return 2*6371*math.asin(math.sqrt(h))
    jfk = nyc[0]
    dist = gc(a.origin, jfk)
    fly = a.block or (int(dist/13.5) + 30)
    print(f"\nPROPOSED NONSTOP {a.origin}-{jfk} raw QSI capture (uncalibrated; GCD {dist:.0f} km, block ~{fly} min):")
    for F in [int(x) for x in a.freqs.split(",")]:
        mn2 = min(mn, fly)
        qns = F * _et(fly, mn2) * 1.0
        qcx = sum(c['frequency'] * _et(c['elapsed_time'], mn2) * CNX.get(c['cnx_type'], 0) for c in valid)
        print(f"   {F}x weekly: capture {qns/(qns+qcx):5.1%}")
    print("\nNote: raw QSI fair-share of schedule quality only. Calibration against Sabre,")
    print("real MCT master, and the load-factor booking step come next.")
    con.close()


if __name__ == "__main__":
    main()

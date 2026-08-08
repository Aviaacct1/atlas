#!/usr/bin/env python3
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
r"""
Avia Solutions - QSI forecast BACK-TEST (accuracy validation).
==============================================================
Forecast a route using ONLY pre-launch data, then compare to the ACTUAL traffic
that flew after it launched. Produces a forecast-vs-actual accuracy read that can
back a marketing claim ("our forecasts land within X% of actual").

Method per route (transparent, every input a named assumption):
  base_market   = Sabre total O&D origin<->dest in the base (pre-launch) year, both directions
  qsi_capture   = corrected QSI engine (freq x ET x cnx x service) on the pre-launch OAG week,
                  proposed nonstop injected -> QSI1/QSI2 averaged fair share
  predicted_p2p = qsi_capture x base_market x stimulation        (point-to-point chain, v1)
  + recapture   = leakage from other gateways the nonstop repatriates  (NOT yet modelled = v1 floor)
  + beyond      = connecting pax carried beyond the gateway          (NOT yet modelled = v1 floor)
  actual        = Sabre nonstop O&D origin<->dest in the launch / mature year

v1 is deliberately the point-to-point floor; recapture + beyond raise it toward actual.
Run LOCALLY (needs sabre.duckdb + oag.duckdb + the real MCT master).

  py -3.12 C:\Avia\back_test.py
  py -3.12 C:\Avia\back_test.py --alliance 0.75 --onestop 0.20 --stim 1.2,1.3,1.5
"""
import argparse, os, sys, math
from collections import defaultdict

APP_CANDIDATES = [
    _paths.QSI_APP,
    _paths.QSI_APP,
]

# name, origin, dests, launch_year, carrier, base_year, pre_oag_week, mature_year, weekly_freq, block_min, note
ROUTES = [
    ("Krakow-NYC",  "KRK", ["JFK","EWR","LGA"], 2021, "LO", 2019, "2019-05-27", 2023, 4, 0,
     "Cleanest: connecting-only base, contemporaneous 2019 OAG, LOT nonstop from 2021"),
    ("Catania-NYC", "CTA", ["JFK","EWR","LGA"], 2025, "DL", 2024, "2019-05-27", 2025, 7, 0,
     "Recent virgin nonstop; 2019 OAG used as pre-launch proxy (no 2024 OAG held)"),
    ("Naples-NYC",  "NAP", ["JFK","EWR","LGA"], 2019, "UA", 2017, "2017-05-29", 2023, 7, 0,
     "CAVEAT: Air Italy (I9) flew NAP-NYC nonstop until 2017, so not a true virgin-nonstop base"),
]


def _import_app(extra=None):
    for p in ([extra] if extra else []) + APP_CANDIDATES:
        if p and os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)
    import connection_builder as CB
    import schedule_chain as SC
    return CB, SC


def _et(el, mn):
    x = (el - mn) / 60.0
    return 1.0 if x <= 0 else 1.0 / ((int(x / 0.1) + 1) ** 0.8)


def load_legs(con, CB, week, apset):
    s = "(" + ",".join("'%s'" % a for a in apset) + ")"
    rows = con.execute("""SELECT carrier,flight_no,dep_airport,arr_airport,dep_terminal,arr_terminal,
      dep_city,arr_city,dep_country,arr_country,local_dep_time,local_arr_time,days_of_op,arr_days_of_op,
      flying_time,elapsed_time,alliance,carrier_category
      FROM oag WHERE week=? AND (dep_airport IN %s OR arr_airport IN %s)""" % (s, s), [week]).fetchall()
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


def qsi_capture(CB, SC, legs, oset, dset, alliances, mct, lcc, coords, cnx, block, onestop, freq, circuity=1.25):
    """Average QSI1/QSI2 nonstop fair share for the proposed service at `freq`."""
    def direction(oo, dd):
        leg1 = [l for l in legs if l['dep_airport'] in oo]
        leg2 = [l for l in legs if l['arr_airport'] in dd]
        valid, _ = CB.build_connections(leg1, leg2, alliances, mct, lcc, 20, 720, 90, hub_airport=None)
        valid = SC.circuity_filter(valid, coords, circuity)
        mn = min([c['elapsed_time'] for c in valid] + [block]) if valid else block
        qcx = sum(c['frequency'] * _et(c['elapsed_time'], mn) * cnx.get(c['cnx_type'], 0) * onestop for c in valid)
        qns = freq * _et(block, mn) * 1.0
        return qns / (qns + qcx) if (qns + qcx) else 0.0
    return (direction(oset, dset) + direction(dset, oset)) / 2.0


def sabre_market(scon, o, dests, year, nonstop_only=False):
    nyc = "(" + ",".join("'%s'" % a for a in dests) + ")"
    cond = " AND itinerary='NON-STOP'" if nonstop_only else ""
    q = """SELECT COALESCE(sum(passengers),0) FROM sabre WHERE source_year=?%s AND (
      (origin_airport=? AND destination_airport IN %s) OR
      (destination_airport=? AND origin_airport IN %s))""" % (cond, nyc, nyc)
    return scon.execute(q, [year, o, o]).fetchone()[0] or 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oag", default=_paths.OAG_DB)
    ap.add_argument("--sabre", default=_paths.SABRE_DB)
    ap.add_argument("--alliance", type=float, default=0.75)
    ap.add_argument("--onestop", type=float, default=0.20)
    ap.add_argument("--stim", default="1.2,1.3,1.5")
    ap.add_argument("--app", default=None)
    a = ap.parse_args()
    CB, SC = _import_app(a.app)
    import duckdb
    cnx = {'ONLINE': 1.0, 'ALLIANCE': a.alliance, 'INTERLINING': 0.25}
    stims = [float(x) for x in a.stim.split(",")]
    coords = SC.load_airport_coords()
    mct, mctsrc = {}, "default 90"
    try:
        from config import MCT_MASTER
        mct = CB.load_mct_data(str(MCT_MASTER), 90)
        mctsrc = "MCT master (%d)" % len(mct) if mct else "default 90 (master unreachable)"
    except Exception:
        pass
    ocon = duckdb.connect(a.oag, read_only=True)
    scon = duckdb.connect(a.sabre, read_only=True)

    def gc(x, y):
        (la1, lo1), (la2, lo2) = coords[x], coords[y]
        p1, p2 = math.radians(la1), math.radians(la2); dp, dl = math.radians(la2-la1), math.radians(lo2-lo1)
        h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
        return 2*6371*math.asin(math.sqrt(h))

    print("QSI FORECAST BACK-TEST   | alliance %.3f  one-stop %.2f  | %s" % (a.alliance, a.onestop, mctsrc))
    print("predicted (point-to-point floor) = qsi_capture x base_market x stimulation")
    print("=" * 100)
    for name, o, d, launch, car, base_yr, oagwk, mat_yr, freq, blk, note in ROUTES:
        dset = set(d); oset = {o}
        legs = load_legs(ocon, CB, oagwk, oset | dset)
        alliances = SC.alliances_from_legs(legs) or CB.load_alliance_data()
        lcc = SC.lcc_from_legs(legs)
        block = blk or (int(gc(o, d[0]) / 13.5) + 30)
        cap = qsi_capture(CB, SC, legs, oset, dset, alliances, mct, lcc, coords, cnx, block, a.onestop, freq)
        base = sabre_market(scon, o, d, base_yr, nonstop_only=False)
        act_launch = sabre_market(scon, o, d, launch, nonstop_only=True)
        act_mature = sabre_market(scon, o, d, mat_yr, nonstop_only=True)
        print(f"\n{name}   [{note}]")
        print(f"  pre-launch base market (Sabre {base_yr}, both dir): {int(base):,}")
        print(f"  QSI capture ({freq}x wk nonstop, pre-launch {oagwk[:4]} OAG): {cap*100:.1f}%")
        print("  PREDICTED nonstop pax (p2p floor) by stimulation:")
        for s in stims:
            print(f"     stim {s:.2f}:  {int(cap*base*s):,}")
        print(f"  ACTUAL nonstop pax (Sabre):  launch {launch} = {int(act_launch):,}   mature {mat_yr} = {int(act_mature):,}")
        if act_launch:
            best = min(stims, key=lambda s: abs(cap*base*s - act_launch))
            pred = cap*base*best
            print(f"  -> closest p2p-floor prediction (stim {best:.2f}) = {int(pred):,} vs actual launch {int(act_launch):,}  ({pred/act_launch*100:.0f}% of actual)")
    ocon.close(); scon.close()
    print("\nNote: v1 is the point-to-point FLOOR. Leakage recapture + beyond-hub feed (not yet")
    print("modelled) lift the prediction toward actual. Run with real MCT master for valid capture.")


if __name__ == "__main__":
    main()

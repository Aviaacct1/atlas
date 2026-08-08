#!/usr/bin/env python3
"""
Avia Solutions - QSI market test (store-driven), QSI 1 + QSI 2 averaged.
=======================================================================
Faithful to the analyst QSI@SJC method: per O&D, score every itinerary
QSI = Frequency x elapsed-time-coefficient x connection-type-coefficient,
take the proposed nonstop's fair share in each direction (QSI 1 outbound,
QSI 2 return) and AVERAGE them. Also prints the connecting hub split.

Coefficients are parameterised. The 2024 SJC analyst workbooks use
alliance 0.75; Jonathan's 2013 model (app calibration_library) uses 0.615.
Default here is 0.75 to match the workbook we validate against.

  py -3.12 C:\\Avia\\qsi_market.py --origin SJC --dest HKG --carrier CX --freqs 4,7
  py -3.12 C:\\Avia\\qsi_market.py --origin GOA --dest JFK,EWR,LGA --carrier XX \
       --freqs 3,5,7 --hubsplit --sabre FCO:50,MUC:27,AMS:22
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import argparse, os, sys, math
from collections import defaultdict

APP_CANDIDATES = [
    _paths.QSI_APP,
    _paths.QSI_APP,
    os.path.join(os.path.dirname(__file__), "app"),
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
    s = "(" + ",".join(f"'{a}'" for a in apset) + ")"
    rows = con.execute(f"""SELECT carrier,flight_no,dep_airport,arr_airport,dep_terminal,arr_terminal,
      dep_city,arr_city,dep_country,arr_country,local_dep_time,local_arr_time,days_of_op,arr_days_of_op,
      flying_time,elapsed_time,alliance,carrier_category
      FROM oag WHERE week=? AND (dep_airport IN {s} OR arr_airport IN {s})""", [week]).fetchall()
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


def score_direction(CB, SC, legs, oset, dset, alliances, mct, lcc, coords, circuity, cnx, block, onestop):
    """One direction o->hub->d. Returns (qcx, hub_q, total_q, min_elapsed_incl_nonstop).
    Each connecting (one-stop) itinerary carries the one-stop service coefficient."""
    leg1 = [l for l in legs if l['dep_airport'] in oset]       # o -> hub (arrive hub)
    leg2 = [l for l in legs if l['arr_airport'] in dset]       # hub -> d (depart hub)
    valid, _ = CB.build_connections(leg1, leg2, alliances, mct, lcc, 20, 720, 90, hub_airport=None)
    valid = SC.circuity_filter(valid, coords, circuity)
    mn = min([c['elapsed_time'] for c in valid] + [block]) if valid else block
    hub_q = defaultdict(float); qcx = 0.0
    for c in valid:
        q = c['frequency'] * _et(c['elapsed_time'], mn) * cnx.get(c['cnx_type'], 0) * onestop
        hub_q[c['cnx_airport']] += q; qcx += q
    return qcx, hub_q, mn, len(valid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=_paths.OAG_DB)
    ap.add_argument("--week", default="2025-05-26")
    ap.add_argument("--origin", required=True)
    ap.add_argument("--dest", required=True, help="comma list, e.g. HKG or JFK,EWR,LGA")
    ap.add_argument("--carrier", default="XX")
    ap.add_argument("--freqs", default="3,5,7")
    ap.add_argument("--block", type=int, default=0, help="nonstop block mins (0 = estimate from GCD)")
    ap.add_argument("--alliance", type=float, default=0.75, help="alliance cnx coeff (SJC wkbk 0.75; 2013 model 0.615)")
    ap.add_argument("--onestop", type=float, default=0.20, help="one-stop service coeff (nonstop=1.0); QSI@SJC=0.20")
    ap.add_argument("--circuity", type=float, default=1.25)
    ap.add_argument("--hubsplit", action="store_true")
    ap.add_argument("--sabre", default="", help="observed hub split e.g. FCO:50,MUC:27,AMS:22")
    ap.add_argument("--app", default=None)
    a = ap.parse_args()
    CB, SC = _import_app(a.app)
    import duckdb
    oset = set(a.origin.split(",")); dset = set(a.dest.split(","))
    cnx = {'ONLINE': 1.0, 'ALLIANCE': a.alliance, 'INTERLINING': 0.25}

    con = duckdb.connect(a.db, read_only=True)
    legs = load_legs(con, CB, a.week, oset | dset)
    alliances = SC.alliances_from_legs(legs) or CB.load_alliance_data()
    lcc = SC.lcc_from_legs(legs)
    mct, mctsrc = {}, "default 90"
    try:
        from config import MCT_MASTER
        mct = CB.load_mct_data(str(MCT_MASTER), 90)
        mctsrc = f"MCT master ({len(mct)} entries)" if mct else "default 90 (master unreachable)"
    except Exception:
        pass
    coords = SC.load_airport_coords()

    def gc(x, y):
        (la1, lo1), (la2, lo2) = coords[x], coords[y]
        p1, p2 = math.radians(la1), math.radians(la2); dp, dl = math.radians(la2-la1), math.radians(lo2-lo1)
        h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
        return 2*6371*math.asin(math.sqrt(h))
    o0, d0 = sorted(oset)[0], sorted(dset)[0]
    dist = gc(o0, d0); block = a.block or (int(dist/13.5) + 30)

    print(f"QSI market test: {a.origin} <-> {a.dest}  week {a.week}")
    print(f"  legs {len(legs):,}  | alliance {a.alliance}  one-stop {a.onestop}  | {mctsrc}  | nonstop block ~{block} min ({dist:.0f} km)")

    # QSI 1 (outbound o->d) and QSI 2 (return d->o)
    qcx1, hub1, mn1, n1 = score_direction(CB, SC, legs, oset, dset, alliances, mct, lcc, coords, a.circuity, cnx, block, a.onestop)
    qcx2, hub2, mn2, n2 = score_direction(CB, SC, legs, dset, oset, alliances, mct, lcc, coords, a.circuity, cnx, block, a.onestop)
    print(f"  connections: QSI1 {n1:,}  QSI2 {n2:,}")

    print(f"\nPROPOSED NONSTOP {a.carrier} {o0}-{d0} fair share (QSI1, QSI2, average):")
    for F in [int(x) for x in a.freqs.split(",")]:
        s1 = (F*_et(block, mn1)) / (F*_et(block, mn1) + qcx1) if (F*_et(block, mn1)+qcx1) else 0
        s2 = (F*_et(block, mn2)) / (F*_et(block, mn2) + qcx2) if (F*_et(block, mn2)+qcx2) else 0
        print(f"   {F}x weekly:  QSI1 {s1:5.1%}   QSI2 {s2:5.1%}   AVG {(s1+s2)/2:5.1%}")

    if a.hubsplit:
        sab = dict(p.split(":") for p in a.sabre.split(",")) if a.sabre else {}
        # average the two directions' hub QSI for the connecting split
        allhubs = set(hub1) | set(hub2)
        comb = {h: hub1.get(h, 0)/ (sum(hub1.values()) or 1)/2 + hub2.get(h,0)/(sum(hub2.values()) or 1)/2 for h in allhubs}
        tot = sum(comb.values()) or 1
        print(f"\nCONNECTING HUB SPLIT (avg of both directions)   [Sabre observed in brackets]:")
        for h, q in sorted(comb.items(), key=lambda x: -x[1])[:8]:
            sv = f"  [Sabre {sab[h]}%]" if h in sab else ""
            print(f"   {h}: {q/tot:5.1%}{sv}")
    con.close()


if __name__ == "__main__":
    main()

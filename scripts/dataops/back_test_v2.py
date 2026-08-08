#!/usr/bin/env python3
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
r"""
Avia Solutions - QSI back-test / CALIBRATION across route types.
================================================================
Auto-detects each route's nonstop launch (year, carrier, pre-launch base year)
from Sabre, forecasts the point-to-point floor from pre-launch data, compares to
actual, and derives the calibration UPLIFT (actual / floor) segmented by route
type (FSC / LCC / Leisure / Regional). Also runs a one-stop-coefficient sensitivity
analytically, so we can see which coefficient best aligns modelled with observed.

Goal: an evidenced set of calibration factors per route type, and a forecast-vs-
actual accuracy read for marketing.

Run LOCALLY (sabre.duckdb + oag.duckdb + real MCT master).
  py -3.12 C:\Avia\back_test_v2.py
  py -3.12 C:\Avia\back_test_v2.py --stim 1.3 --onestops 0.10,0.20,0.30

DATA NOTE: only 2017 & 2019 pre-launch OAG weeks are held. Routes launched 2020+
borrow the 2019 week (stale). One summer OAG week per year (2015-2024) would let
this calibrate properly across years - the key data request to Jess.
"""
import argparse, os, sys, math, statistics
from collections import defaultdict

APP_CANDIDATES = [
    _paths.QSI_APP,
    _paths.QSI_APP,
]

# Held OAG weeks (summer preferred). Extend as Jess supplies more.
OAG_WEEKS = ["2017-05-29", "2019-05-27", "2025-05-26"]

# market, origin, dests, type. Launch year/carrier/base auto-detected from Sabre.
# Seed spans types; the detector self-selects markets with a clean nonstop launch.
NYC = ["JFK", "EWR", "LGA"]
ROUTE_LIBRARY = [
    # Regional secondary-city, legacy/leisure to NYC
    ("Catania-NYC",  "CTA", NYC, "Regional"),
    ("Krakow-NYC",   "KRK", NYC, "Regional"),
    ("Palermo-NYC",  "PMO", NYC, "Regional"),
    ("Naples-NYC",   "NAP", NYC, "Regional"),
    ("Porto-NYC",    "OPO", NYC, "Regional"),
    ("Bologna-NYC",  "BLQ", NYC, "Regional"),
    # Full-service / flag carrier point-to-point
    ("Venice-NYC",   "VCE", NYC, "FSC"),
    ("Nice-NYC",     "NCE", NYC, "FSC"),
    # LCC long-haul
    ("Oslo-NYC",     "OSL", NYC, "LCC"),
    ("Paris-NYC-ORY","ORY", NYC, "LCC"),
    ("Keflavik-NYC", "KEF", NYC, "LCC"),
    ("London-LGW-NYC","LGW", NYC, "LCC"),
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


def detect_launch(scon, o, d, years, floor=1500):
    """First year nonstop O&D >= floor, with the dominant nonstop carrier and base (prior) year."""
    nyc = "(" + ",".join("'%s'" % a for a in d) + ")"
    prev = None
    for y in years:
        ns = scon.execute("""SELECT COALESCE(sum(passengers),0) FROM sabre WHERE source_year=? AND itinerary='NON-STOP'
          AND ((origin_airport=? AND destination_airport IN %s) OR (destination_airport=? AND origin_airport IN %s))""" % (nyc, nyc),
          [y, o, o]).fetchone()[0] or 0
        if ns >= floor:
            car = scon.execute("""SELECT operating_airline, sum(passengers) p FROM sabre WHERE source_year=? AND itinerary='NON-STOP'
              AND ((origin_airport=? AND destination_airport IN %s) OR (destination_airport=? AND origin_airport IN %s))
              GROUP BY 1 ORDER BY 2 DESC LIMIT 1""" % (nyc, nyc), [y, o, o]).fetchone()
            return y, (car[0] if car else "?"), prev
        prev = y
    return None, None, None


def pick_oag_week(base_yr):
    cand = [w for w in OAG_WEEKS if int(w[:4]) <= base_yr]
    return cand[-1] if cand else OAG_WEEKS[0]


def market_pax(scon, o, d, year, nonstop_only=False):
    nyc = "(" + ",".join("'%s'" % a for a in d) + ")"
    cond = " AND itinerary='NON-STOP'" if nonstop_only else ""
    return scon.execute("""SELECT COALESCE(sum(passengers),0) FROM sabre WHERE source_year=?%s AND (
      (origin_airport=? AND destination_airport IN %s) OR (destination_airport=? AND origin_airport IN %s))""" % (cond, nyc, nyc),
      [year, o, o]).fetchone()[0] or 0


def capture_components(CB, SC, legs, oset, dset, alliances, mct, lcc, coords, cnx, block, freq, circuity=1.25):
    """Per direction return (qns, qcx_raw) where qcx_raw excludes the one-stop coeff,
    so capture at any one-stop coeff = qns/(qns + onestop*qcx_raw)."""
    out = []
    for oo, dd in ((oset, dset), (dset, oset)):
        leg1 = [l for l in legs if l['dep_airport'] in oo]
        leg2 = [l for l in legs if l['arr_airport'] in dd]
        valid, _ = CB.build_connections(leg1, leg2, alliances, mct, lcc, 20, 720, 90, hub_airport=None)
        valid = SC.circuity_filter(valid, coords, circuity)
        mn = min([c['elapsed_time'] for c in valid] + [block]) if valid else block
        qcx_raw = sum(c['frequency'] * _et(c['elapsed_time'], mn) * cnx.get(c['cnx_type'], 0) for c in valid)
        qns = freq * _et(block, mn) * 1.0
        out.append((qns, qcx_raw))
    return out


def cap_at(comp, onestop):
    return statistics.mean([qns / (qns + onestop * qcx) if (qns + onestop * qcx) else 0 for qns, qcx in comp])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oag", default=_paths.OAG_DB)
    ap.add_argument("--sabre", default=_paths.SABRE_DB)
    ap.add_argument("--alliance", type=float, default=0.75)
    ap.add_argument("--onestops", default="0.10,0.20,0.30")
    ap.add_argument("--stim", type=float, default=1.30)
    ap.add_argument("--freq", type=int, default=5, help="assumed weekly nonstop freq (data gap: true freq needs launch-year OAG)")
    ap.add_argument("--app", default=None)
    a = ap.parse_args()
    CB, SC = _import_app(a.app)
    import duckdb
    cnx = {'ONLINE': 1.0, 'ALLIANCE': a.alliance, 'INTERLINING': 0.25}
    onestops = [float(x) for x in a.onestops.split(",")]
    coords = SC.load_airport_coords()
    mct, mctsrc = {}, "default 90"
    try:
        from config import MCT_MASTER
        mct = CB.load_mct_data(str(MCT_MASTER), 90)
        mctsrc = "MCT master (%d)" % len(mct) if mct else "default 90"
    except Exception:
        pass
    ocon = duckdb.connect(a.oag, read_only=True)
    scon = duckdb.connect(a.sabre, read_only=True)
    years = [r[0] for r in scon.execute("SELECT DISTINCT source_year FROM sabre ORDER BY 1").fetchall()]

    def gc(x, y):
        (la1, lo1), (la2, lo2) = coords[x], coords[y]
        p1, p2 = math.radians(la1), math.radians(la2); dp, dl = math.radians(la2-la1), math.radians(lo2-lo1)
        h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
        return 2*6371*math.asin(math.sqrt(h))

    print("QSI CALIBRATION BACK-TEST | alliance %.3f stim %.2f freq %d | %s" % (a.alliance, a.stim, a.freq, mctsrc))
    print("uplift = actual_launch / floor   (floor = cap@0.20 x base x stim)")
    hdr = "route          type      launch car  base   base_mkt  cap0.20   floor   actual   uplift | " + " ".join("u@%.2f" % o for o in onestops)
    print("=" * len(hdr)); print(hdr); print("-" * len(hdr))
    seg = defaultdict(list); seg_os = defaultdict(lambda: defaultdict(list))
    for name, o, d, typ in ROUTE_LIBRARY:
        ly, car, base = detect_launch(scon, o, d, years)
        if not ly or not base:
            print("%-14s %-9s  (no clean launch in window)" % (name, typ)); continue
        wk = pick_oag_week(base)
        legs = load_legs(ocon, CB, wk, set([o]) | set(d))
        if not any(l['dep_airport'] == o for l in legs):
            print("%-14s %-9s  (no %s legs in %s OAG)" % (name, typ, o, wk[:4])); continue
        alliances = SC.alliances_from_legs(legs) or CB.load_alliance_data()
        lcc = SC.lcc_from_legs(legs)
        block = int(gc(o, d[0]) / 13.5) + 30
        comp = capture_components(CB, SC, legs, {o}, set(d), alliances, mct, lcc, coords, cnx, block, a.freq)
        base_mkt = market_pax(scon, o, d, base)
        actual = market_pax(scon, o, d, ly, nonstop_only=True)
        cap20 = cap_at(comp, 0.20); floor = cap20 * base_mkt * a.stim
        uplift = actual / floor if floor else 0
        seg[typ].append(uplift)
        ucols = []
        for os_ in onestops:
            f = cap_at(comp, os_) * base_mkt * a.stim
            u = actual / f if f else 0
            seg_os[typ][os_].append(u); ucols.append("%5.2f" % u)
        print("%-14s %-9s %5d %-4s %5d %9d %7.1f%% %8d %8d %6.2fx | %s" % (
            name, typ, ly, car, base, int(base_mkt), cap20*100, int(floor), int(actual), uplift, " ".join(ucols)))

    print("\nSEGMENT MEDIAN UPLIFT (floor x this = calibrated forecast):")
    for typ, us in seg.items():
        if us:
            line = "  %-9s n=%d  median uplift %.2fx  |  by one-stop coeff: %s" % (
                typ, len(us), statistics.median(us),
                "  ".join("%.2f->%.2fx" % (o, statistics.median(seg_os[typ][o])) for o in onestops))
            print(line)
    print("\nThe one-stop coeff whose median uplift is closest to 1.00 per segment is the better-calibrated value.")
    print("DATA GAP: extend OAG_WEEKS (one summer week/yr 2015-2024) for contemporaneous pre-launch schedules.")
    ocon.close(); scon.close()


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
             'dep_country': str(dctry or '').strip(), 'arr_country': str(actry or '').strip(),
             'dep_time_mins': hhmm(ldt), 'arr_time_mins': hhmm(lat),
             'flying_mins': CB._parse_duration_mins(fly or el),
             'dep_day_set': CB.parse_days_string(dop), 'arr_day_set': CB.parse_days_string(adop or dop),
             'alliance': str(alli or '').strip(), 'carrier_category': str(cat or '').strip(), 'id': len(legs)}
        L['dom_int'] = CB.get_dom_int(L['dep_country'], L['arr_country'])
        legs.append(L)
    return legs


if __name__ == "__main__":
    main()

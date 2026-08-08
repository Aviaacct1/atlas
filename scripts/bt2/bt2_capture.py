#!/usr/bin/env python3
"""Avia Solutions - BT2 Stage 4: QSI capture vs the contemporaneous pre-launch month.
Per pair: rebuilds a representative week (schedule rows covering the 15th-21st of the
pre-launch month), runs the QSI connection builder, stores capture at freq=5 (old
basis) and at ACTUAL launch frequency, plus connection-quality components by type
(ONLINE/ALLIANCE/INTERLINE sums) so weights can be re-tuned without recompute.
Resumable: appends to capture_L.csv, exits cleanly near the 45s cap. Re-run until done.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import argparse, csv, math, os, statistics, sys, time
from collections import defaultdict
import duckdb

BT2 = _os.path.join(_paths.AVIA, "bt2")
OAG = _paths.OAG_DB
APP = _paths.QSI_APP
T0, BUDGET = time.time(), 33.0

sys.path.insert(0, APP)
import connection_builder as CB
import schedule_chain as SC

def _et(el, mn):
    x = (el - mn) / 60.0
    return 1.0 if x <= 0 else 1.0 / ((int(x / 0.1) + 1) ** 0.8)

def load_legs(con, mon, apset):
    s = "(" + ",".join("'%s'" % a for a in apset) + ")"
    base = """SELECT DISTINCT carrier, flight_no, dep_airport, arr_airport, dep_terminal,
      arr_terminal, dep_country, arr_country, local_dep_time, local_arr_time,
      days_of_op, arr_days_of_op, flying_time, elapsed_time, alliance, carrier_category
      FROM oag WHERE week=? AND service_type='J'
      AND (dep_airport IN %s OR arr_airport IN %s)
      AND try_cast(strftime(try_cast(eff_from AS date), '%%d') AS int) IS NOT NULL
      AND try_cast(eff_from AS date) <= ?::date AND try_cast(eff_to AS date) >= ?::date"""
    y, m = int(mon[:4]), int(mon[5:7])
    w_lo, w_hi = f"{mon}-15", f"{mon}-21"
    rows = con.execute(base % (s, s), [mon, w_hi, w_lo]).fetchall()
    if not rows:  # split-month fallback (Asia gaps): second half covers the 16th-21st
        rows = con.execute(base % (s, s), [mon + "p16", w_hi, w_lo]).fetchall()
        if not rows:
            rows = con.execute(base % (s, s), [mon + "p01", w_hi, w_lo]).fetchall()
    legs = []
    for r in rows:
        (car, fno, dep, arr, dt, at, dc, ac, ldt, lat, dop, adop, fly, el, alli, cat) = r
        try: dtm = CB.parse_time_hhmm(ldt)
        except Exception: dtm = None
        try: atm = CB.parse_time_hhmm(lat)
        except Exception: atm = None
        L = {'carrier': str(car).strip(), 'flight_no': str(fno or '').strip(),
             'dep_airport': str(dep).strip(), 'arr_airport': str(arr).strip(),
             'dep_terminal': str(dt or '').strip(), 'arr_terminal': str(at or '').strip(),
             'dep_country': str(dc or '').strip(), 'arr_country': str(ac or '').strip(),
             'dep_time_mins': dtm, 'arr_time_mins': atm,
             'flying_mins': CB._parse_duration_mins(fly or el),
             'dep_day_set': CB.parse_days_string(dop), 'arr_day_set': CB.parse_days_string(adop or dop),
             'alliance': str(alli or '').strip(), 'carrier_category': str(cat or '').strip(), 'id': len(legs)}
        L['dom_int'] = CB.get_dom_int(L['dep_country'], L['arr_country'])
        legs.append(L)
    return legs

def components(legs, a, b, alliances, mct, lcc, coords, block, circuity=1.25):
    """Per direction: (S_online, S_alliance, S_interline, mn). Sums are freq*et by type."""
    out = []
    for oo, dd in ((a, b), (b, a)):
        leg1 = [l for l in legs if l['dep_airport'] == oo]
        leg2 = [l for l in legs if l['arr_airport'] == dd]
        if not leg1 or not leg2:
            out.append((0.0, 0.0, 0.0, block)); continue
        valid, _ = CB.build_connections(leg1, leg2, alliances, mct, lcc, 20, 720, 90, hub_airport=None)
        valid = SC.circuity_filter(valid, coords, circuity)
        mn = min([c['elapsed_time'] for c in valid] + [block]) if valid else block
        S = {'ONLINE': 0.0, 'ALLIANCE': 0.0, 'INTERLINING': 0.0}
        for c in valid:
            S[c['cnx_type']] = S.get(c['cnx_type'], 0.0) + c['frequency'] * _et(c['elapsed_time'], mn)
        out.append((S['ONLINE'], S['ALLIANCE'], S['INTERLINING'], mn))
    return out

def cap_from(so, sa, si, mn, block, freq, w_all=0.75, w_int=0.25, onestop=0.20):
    qcx = onestop * (so + w_all * sa + w_int * si)
    qns = freq * _et(block, mn)
    return qns / (qns + qcx) if (qns + qcx) else 0.0

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--cohort", type=int, required=True)
    L = ap.parse_args().cohort
    prof = list(csv.DictReader(open(f"{BT2}/launch_profile_{L}.csv")))
    outp = f"{BT2}/capture_{L}.csv"
    done = set()
    if os.path.exists(outp):
        done = {(r["a"], r["b"]) for r in csv.DictReader(open(outp))}
    todo = [r for r in prof if (r["a"], r["b"]) not in done]
    if not todo:
        print(f"cohort {L}: COMPLETE ({len(done)}/{len(prof)})"); return
    coords = SC.load_airport_coords()
    mct = {}
    try:
        from config import MCT_MASTER
        mct = CB.load_mct_data(str(MCT_MASTER), 90)
    except Exception:
        try:
            mct = CB.load_mct_data(_os.path.join(_paths.AVIA, "MCT Master List.xlsx"), 90)
        except Exception:
            mct = {}
    con = duckdb.connect(OAG, read_only=True)
    con.execute("SET memory_limit='2GB'"); con.execute("SET threads=4")
    by_pm = defaultdict(list)
    for r in todo: by_pm[r["pre_month"]].append(r)
    fields = ["a","b","pre_month","legs_n","so_ab","sa_ab","si_ab","mn_ab","so_ba","sa_ba","si_ba","mn_ba","block","cap_f5","cap_actual"]
    newf = not os.path.exists(outp)
    fh = open(outp, "a", newline=""); w = csv.writer(fh)
    if newf: w.writerow(fields)
    ndone = 0
    for pm in sorted(by_pm):
        for r in by_pm[pm]:
            if time.time() - T0 > BUDGET:
                fh.close(); print(f"cohort {L}: paused, {len(done)+ndone}/{len(prof)} done"); return
            a, b = r["a"], r["b"]
            legs = load_legs(con, pm, {a, b})
            if not legs:
                w.writerow([a, b, pm, 0] + [""]*11); ndone += 1; continue
            alliances = SC.alliances_from_legs(legs) or CB.load_alliance_data()
            lcc = SC.lcc_from_legs(legs) or CB.DEFAULT_LCC_LIST
            d = float(r["gcd_km"] or 0) or 1000.0
            block = int(d / 13.5) + 30
            comp = components(legs, a, b, alliances, mct, lcc, coords, block)
            (so1, sa1, si1, mn1), (so2, sa2, si2, mn2) = comp
            f_act = max(1.0, float(r["wk_freq_dir"] or 1))
            c5 = statistics.mean([cap_from(so1, sa1, si1, mn1, block, 5),
                                  cap_from(so2, sa2, si2, mn2, block, 5)])
            ca = statistics.mean([cap_from(so1, sa1, si1, mn1, block, f_act),
                                  cap_from(so2, sa2, si2, mn2, block, f_act)])
            w.writerow([a, b, pm, len(legs), round(so1,3), round(sa1,3), round(si1,3), mn1,
                        round(so2,3), round(sa2,3), round(si2,3), mn2, block,
                        round(c5,5), round(ca,5)])
            ndone += 1
    fh.close(); print(f"cohort {L}: COMPLETE ({len(done)+ndone}/{len(prof)})")

if __name__ == "__main__":
    main()

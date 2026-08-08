#!/usr/bin/env python3
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
r"""
Avia Solutions - COHORT proxy back-test / calibration (ANY origin, ANY dest, ANY region).
=========================================================================================
For each launch-year cohort, auto-DISCOVERS every new long-haul nonstop O&D pair from
Sabre (nonstop present in year L, ~absent in L-1, anywhere in the world), forecasts each
from PRE-launch data, and compares to the L outturn. Pairs are direction-agnostic.

Cohorts (launch_year, pre-launch OAG week, base Sabre year):
   2018 <- 2017 OAG + 2017 Sabre   (fully contemporaneous)
   2019 <- 2017 OAG + 2018 Sabre   (OAG 1yr stale)
   2025 <- 2019 OAG + 2024 Sabre   (OAG stale; best pre-2025 week held)

Per pair: floor = qsi_capture(pre-OAG, both directions averaged) x base_market x stim;
uplift = actual_launch / floor. Tagged LCC vs FSC by the launch carrier.
Summaries by cohort and by type => calibration factors.

Run LOCALLY (sabre.duckdb + oag.duckdb + real MCT).
  py -3.12 C:\Avia\back_test_cohort.py
  py -3.12 C:\Avia\back_test_cohort.py --minhaul 2500 --max 30
"""
import argparse, os, sys, math, statistics
from collections import defaultdict

APP_CANDIDATES = [_paths.QSI_APP,
                  _paths.QSI_APP]
COHORTS = [(2018, "2017-05-29", 2017), (2019, "2017-05-29", 2018), (2025, "2019-05-27", 2024)]


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
    rows = con.execute("""SELECT carrier,dep_airport,arr_airport,dep_terminal,arr_terminal,
      dep_country,arr_country,local_dep_time,local_arr_time,days_of_op,arr_days_of_op,
      flying_time,elapsed_time,alliance,carrier_category
      FROM oag WHERE week=? AND (dep_airport IN %s OR arr_airport IN %s)""" % (s, s), [week]).fetchall()
    def hhmm(v):
        try: return CB.parse_time_hhmm(v)
        except Exception: return None
    legs = []
    for r in rows:
        (car, dep, arr, dt, at, dctry, actry, ldt, lat, dop, adop, fly, el, alli, cat) = r
        L = {'carrier': str(car).strip(), 'flight_no': '', 'dep_airport': str(dep).strip(),
             'arr_airport': str(arr).strip(), 'dep_terminal': str(dt or '').strip(),
             'arr_terminal': str(at or '').strip(), 'dep_country': str(dctry or '').strip(),
             'arr_country': str(actry or '').strip(), 'dep_time_mins': hhmm(ldt), 'arr_time_mins': hhmm(lat),
             'flying_mins': CB._parse_duration_mins(fly or el),
             'dep_day_set': CB.parse_days_string(dop), 'arr_day_set': CB.parse_days_string(adop or dop),
             'alliance': str(alli or '').strip(), 'carrier_category': str(cat or '').strip(), 'id': len(legs)}
        L['dom_int'] = CB.get_dom_int(L['dep_country'], L['arr_country'])
        legs.append(L)
    return legs


def ns_pairs(scon, year):
    """{frozenset(o,d): nonstop_pax} for a year, direction-agnostic."""
    rows = scon.execute("""SELECT origin_airport, destination_airport, sum(passengers)
        FROM sabre WHERE source_year=? AND itinerary='NON-STOP' GROUP BY 1,2""", [year]).fetchall()
    agg = defaultdict(float)
    for o, d, p in rows:
        if o and d and o != d:
            agg[frozenset((o, d))] += (p or 0)
    return agg


def load_countries():
    """IATA -> ISO country, for an international (cross-country) filter."""
    try:
        import airportsdata
        return {k: v.get('country', '') for k, v in airportsdata.load('IATA').items()}
    except Exception:
        return {}


def pair_pax(scon, a, b, year, nonstop_only=False):
    cond = " AND itinerary='NON-STOP'" if nonstop_only else ""
    return scon.execute("""SELECT COALESCE(sum(passengers),0) FROM sabre WHERE source_year=?%s AND (
       (origin_airport=? AND destination_airport=?) OR (origin_airport=? AND destination_airport=?))""" % cond,
       [year, a, b, b, a]).fetchone()[0] or 0


def top_carrier(scon, a, b, year):
    r = scon.execute("""SELECT operating_airline, sum(passengers) p FROM sabre WHERE source_year=? AND itinerary='NON-STOP'
       AND ((origin_airport=? AND destination_airport=?) OR (origin_airport=? AND destination_airport=?))
       GROUP BY 1 ORDER BY 2 DESC LIMIT 1""", [year, a, b, b, a]).fetchone()
    return r[0] if r else "?"


def capture(CB, SC, legs, a, b, alliances, mct, lcc, coords, cnx, block, freq, onestop, circuity=1.25):
    shares = []
    for oo, dd in (({a}, {b}), ({b}, {a})):
        leg1 = [l for l in legs if l['dep_airport'] in oo]
        leg2 = [l for l in legs if l['arr_airport'] in dd]
        if not leg1 or not leg2:
            shares.append(0.0); continue
        valid, _ = CB.build_connections(leg1, leg2, alliances, mct, lcc, 20, 720, 90, hub_airport=None)
        valid = SC.circuity_filter(valid, coords, circuity)
        mn = min([c['elapsed_time'] for c in valid] + [block]) if valid else block
        qcx = sum(c['frequency'] * _et(c['elapsed_time'], mn) * cnx.get(c['cnx_type'], 0) * onestop for c in valid)
        qns = freq * _et(block, mn) * 1.0
        shares.append(qns / (qns + qcx) if (qns + qcx) else 0.0)
    return statistics.mean(shares)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oag", default=_paths.OAG_DB)
    ap.add_argument("--sabre", default=_paths.SABRE_DB)
    ap.add_argument("--alliance", type=float, default=0.75)
    ap.add_argument("--onestop", type=float, default=0.20)
    ap.add_argument("--stim", type=float, default=1.30)
    ap.add_argument("--freq", type=int, default=5)
    ap.add_argument("--minhaul", type=float, default=0.0, help="min GCD km (0 = ANY haul: short-haul, domestic, regional all included)")
    ap.add_argument("--thr", type=float, default=1500.0, help="min launch-year nonstop pax to count")
    ap.add_argument("--minbase", type=float, default=2000.0, help="min pre-launch base market - DATA-QUALITY guard (drops Sabre coverage-gap artifacts), not a route-type filter")
    ap.add_argument("--maxratio", type=float, default=5.0, help="drop if actual > this x base (implausible = artifact)")
    ap.add_argument("--intl", action="store_true", default=False, help="OFF by default: domestic city pairs included. Set to require different countries.")
    ap.add_argument("--region", default="", help="optional: restrict to pairs where an endpoint country is in this comma list (e.g. US,GB,DE) - Sabre is most reliable transatlantic/US/Europe")
    ap.add_argument("--max", type=int, default=40, help="max routes per cohort (by launch pax)")
    ap.add_argument("--app", default=None)
    a = ap.parse_args()
    CB, SC = _import_app(a.app)
    import duckdb
    cnx = {'ONLINE': 1.0, 'ALLIANCE': a.alliance, 'INTERLINING': 0.25}
    coords = SC.load_airport_coords()
    countries = load_countries()
    reg = set(x.strip().upper() for x in a.region.split(",")) if a.region else None
    LCC = CB.DEFAULT_LCC_LIST
    mct, mctsrc = {}, "default 90"
    try:
        from config import MCT_MASTER
        mct = CB.load_mct_data(str(MCT_MASTER), 90); mctsrc = "MCT master (%d)" % len(mct) if mct else "default 90"
    except Exception:
        pass
    ocon = duckdb.connect(a.oag, read_only=True); scon = duckdb.connect(a.sabre, read_only=True)

    def gc(x, y):
        if x not in coords or y not in coords: return None
        (la1, lo1), (la2, lo2) = coords[x], coords[y]
        p1, p2 = math.radians(la1), math.radians(la2); dp, dl = math.radians(la2-la1), math.radians(lo2-lo1)
        h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
        return 2*6371*math.asin(math.sqrt(h))

    print("COHORT PROXY BACK-TEST (any O&D, any region) | alliance %.3f one-stop %.2f stim %.2f freq %d minhaul %.0fkm | %s"
          % (a.alliance, a.onestop, a.stim, a.freq, a.minhaul, mctsrc))
    seg = defaultdict(list); cohort_u = defaultdict(list); rows_all = []
    for L, wk, base in COHORTS:
        cur, pre, pre2 = ns_pairs(scon, L), ns_pairs(scon, L - 1), ns_pairs(scon, L - 2)
        launches = []
        for key, v in cur.items():
            # genuinely virgin: ~no nonstop for TWO prior years (kills false launches from Sabre gaps)
            if v >= a.thr and pre.get(key, 0) < a.thr / 3 and pre2.get(key, 0) < a.thr / 3:
                a1, b1 = sorted(key)
                d = gc(a1, b1)
                if d is None or d < a.minhaul:
                    continue
                if a.intl and countries and countries.get(a1, 'X') == countries.get(b1, 'Y'):
                    continue   # only if --intl set: skip domestic
                if reg and countries and not (countries.get(a1) in reg or countries.get(b1) in reg):
                    continue   # only if --region set: keep pairs touching those countries
                launches.append((a1, b1, v, d))
        launches.sort(key=lambda x: -x[2])
        print("\n===== COHORT %d (pre-OAG %s, base %d) -- %d candidate long-haul launches =====" % (L, wk[:4], base, len(launches)))
        print("  pair           car  type  km     base_mkt   cap   floor  actual  uplift")
        shown = 0
        for a1, b1, lpax, d in launches:
            if shown >= a.max:
                break
            base_mkt = pair_pax(scon, a1, b1, base)
            actual = pair_pax(scon, a1, b1, L, nonstop_only=True)
            # sanity filters: real pre-existing market, plausible launch vs that market
            if base_mkt < a.minbase or actual <= 0 or actual > a.maxratio * base_mkt:
                continue
            legs = load_legs(ocon, CB, wk, {a1, b1})
            if not legs:
                continue
            alliances = SC.alliances_from_legs(legs) or CB.load_alliance_data()
            lcc = SC.lcc_from_legs(legs) or LCC
            block = int(d / 13.5) + 30
            cap = capture(CB, SC, legs, a1, b1, alliances, mct, lcc, coords, cnx, block, a.freq, a.onestop)
            floor = cap * base_mkt * a.stim
            if floor <= 0:
                continue
            car = top_carrier(scon, a1, b1, L)
            typ = "LCC" if car in LCC else "FSC"
            up = actual / floor
            seg[typ].append(up); cohort_u[L].append(up)
            rows_all.append((L, cap, up, typ, floor, actual, a1 + "-" + b1, base_mkt))
            print("  %-4s-%-4s     %-4s %-4s %5.0f %8d %5.1f%% %7d %7d %6.2fx"
                  % (a1, b1, car, typ, d, int(base_mkt), cap * 100, int(floor), int(actual), up))
            shown += 1
        if cohort_u[L]:
            print("  cohort %d median uplift: %.2fx (n=%d)" % (L, statistics.median(cohort_u[L]), len(cohort_u[L])))

    print("\n================ CALIBRATION SUMMARY ================")
    for typ in ("FSC", "LCC"):
        us = seg[typ]
        if us:
            print("  %-4s n=%2d  median uplift %.2fx  (range %.2f-%.2f)" % (typ, len(us), statistics.median(us), min(us), max(us)))
    allu = seg["FSC"] + seg["LCC"]
    if allu:
        print("  ALL  n=%2d  median uplift %.2fx" % (len(allu), statistics.median(allu)))

    # CAPTURE-BAND calibration table: the uplift is a strong function of modelled
    # capture, so the right calibration is a lookup by capture band, not a flat factor.
    print("\n---- CAPTURE-BAND CALIBRATION (median uplift to apply to the floor) ----")
    print("  cap band       n   median   FSC(n)        LCC(n)")
    bands = [(0.0, 0.05), (0.05, 0.15), (0.15, 0.40), (0.40, 0.80), (0.80, 1.01)]
    for lo, hi in bands:
        inb = [(u, t) for (Lx, c, u, t, fl, ac, pr, bm) in rows_all if lo <= c < hi]
        if not inb:
            continue
        allu_b = [u for u, _ in inb]
        f = [u for u, t in inb if t == "FSC"]; l = [u for u, t in inb if t == "LCC"]
        fcol = "%.2fx(%d)" % (statistics.median(f), len(f)) if f else "   -   "
        lcol = "%.2fx(%d)" % (statistics.median(l), len(l)) if l else "   -   "
        print("  %4.0f-%4.0f%%  %4d   %6.2fx   %-12s  %-12s" % (lo*100, hi*100, len(allu_b), statistics.median(allu_b), fcol, lcol))
    print("\nUse: forecast = floor x (capture-band uplift). Capture-band beats a flat per-type factor")
    print("because QSI under-credits the nonstop most where connecting competition is densest (low cap).")

    # -------- HOLD-OUT ACCURACY: train bands on 2018+2019, forecast 2025 BLIND --------
    def band_idx(c):
        for i, (lo, hi) in enumerate(bands):
            if lo <= c < hi:
                return i
        return len(bands) - 1
    BASE_BUCKETS = [(0, 15000), (15000, 35000), (35000, float("inf"))]
    def base_bucket(bm):
        for i, (lo, hi) in enumerate(BASE_BUCKETS):
            if lo <= bm < hi:
                return i
        return len(BASE_BUCKETS) - 1
    HICAP = 0.80
    train = [r for r in rows_all if r[0] in (2018, 2019)]
    test = [r for r in rows_all if r[0] == 2025]
    if train and test:
        tbl = defaultdict(lambda: defaultdict(list))
        hicap = defaultdict(list)   # base-size bucket -> uplifts, for cap >= HICAP
        for (Lx, c, u, t, fl, ac, pr, bm) in train:
            tbl[band_idx(c)][t].append(u); tbl[band_idx(c)]["ALL"].append(u)
            if c >= HICAP:
                hicap[base_bucket(bm)].append(u)
        all_train = [u for (Lx, c, u, t, fl, ac, pr, bm) in train]
        hicap_all = [u for (Lx, c, u, t, fl, ac, pr, bm) in train if c >= HICAP]
        def uplift_flat(c, t):
            b = band_idx(c)
            if len(tbl[b].get(t, [])) >= 3:
                return statistics.median(tbl[b][t])
            if tbl[b].get("ALL"):
                return statistics.median(tbl[b]["ALL"])
            return statistics.median(all_train)
        def uplift_ref(c, t, bm):
            # HIGH-CAPTURE refinement: above 80% capture the flat band over-inflates large
            # established markets, so condition on base-market SIZE instead.
            if c >= HICAP:
                vals = hicap[base_bucket(bm)]
                if len(vals) >= 3:
                    return statistics.median(vals)
                return statistics.median(hicap_all) if hicap_all else uplift_flat(c, t)
            return uplift_flat(c, t)
        print("\n==== HOLD-OUT TEST (high-capture refinement): train 2018+2019, 2025 BLIND ====")
        print("  pair          type  cap    base   actual  predicted  error")
        eo, en = [], []
        for (Lx, c, u, t, fl, ac, pr, bm) in sorted(test, key=lambda r: -r[5]):
            po = fl * uplift_flat(c, t); pn = fl * uplift_ref(c, t, bm)
            eo.append(abs(po / ac - 1)); en.append(abs(pn / ac - 1))
            print("  %-12s %-4s %4.1f%% %7d %8d %9d  %+5.0f%%" % (pr, t, c*100, int(bm), int(ac), int(pn), (pn/ac-1)*100))
        def stat(e):
            es = sorted(e)
            return (statistics.median(es),
                    sum(1 for x in es if x <= 0.25)/len(es),
                    sum(1 for x in es if x <= 0.50)/len(es), max(es))
        mo, o25, o50, omax = stat(eo); mn, n25, n50, nmax = stat(en)
        print("  FLAT bands :  median %.0f%%  within+-25 %.0f%%  within+-50 %.0f%%  worst %.0f%%" % (mo*100, o25*100, o50*100, omax*100))
        print("  REFINED    :  median %.0f%%  within+-25 %.0f%%  within+-50 %.0f%%  worst %.0f%%  <== high-cap fix" % (mn*100, n25*100, n50*100, nmax*100))
        print("  (refinement tames the high-capture / large-base over-prediction tail; n=%d, blind)" % len(en))
    print("2018/2019 cohorts are pre-COVID = cleanest; 2020/2021 deliberately excluded (COVID).")
    ocon.close(); scon.close()


if __name__ == "__main__":
    main()

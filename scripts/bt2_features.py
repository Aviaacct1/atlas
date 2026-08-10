"""bt2_features - BT2 stage-4 feature construction for LIVE launch candidates, ported
faithfully from C:\\Avia\\bt2\\bt2_capture.py (same legs/connection/qcx definitions), plus
batch scoring against the exported BT2 model. Author: Avia Solutions.

legs_n = distinct scheduled J-service legs touching either endpoint in the reference week.
qcx    = sum over both directions of S_online + 0.75*S_alliance + 0.25*S_interline
         (S = frequency x elapsed-time decay over valid built connections).
capa   = mean over directions of qns / (qns + 0.20*qcx_dir), qns = freq x et(block, mn).
Live reference week = the newest weekly snapshot in the store (same construction as the
training pre-launch months). Requires the QSI app on sys.path (caller does this already).
"""
from __future__ import annotations
import math, os, statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from avia_forecast import paths

_COORDS = None
_MCT = None


def _et(el, mn):
    x = (el - mn) / 60.0
    return 1.0 if x <= 0 else 1.0 / ((int(x / 0.1) + 1) ** 0.8)


def _cb():
    import connection_builder as CB
    import schedule_chain as SC
    return CB, SC


def _coords(SC):
    """Airport coordinates, from Meridian's loader first and our own airport reference
    second.

    Meridian's `load_airport_coords` reads the optional `airportsdata` package and returns
    an EMPTY dictionary when it is absent, with circuity then disabled. That package was
    not in requirements.txt until 10 August 2026, so on any machine installed from it the
    dictionary was empty, `pair_metrics` raised "gcd unsourceable" for every candidate
    route, and the circuity filter passed everything. `bum_candidates.json` of 29 July 2026
    carries "qsi share failed: ValueError" on all 136 of its routes for that reason, and
    the estimate on each row came from the crude market times capture fallback rather than
    the BT2 model its source line names.

    The package is now a requirement AND this falls back to
    E:\\Avia\\Global\\data\\airports.csv, 85,846 rows, which the estate already holds and
    which journey_length_history.py reads. A missing dependency should degrade to a second
    source, not to a silently disabled filter.
    """
    global _COORDS
    if _COORDS is None:
        _COORDS = dict(SC.load_airport_coords() or {})
        if len(_COORDS) < 1000:
            import csv
            fp = os.path.join(paths.DATA, "airports.csv")
            n = 0
            if os.path.isfile(fp):
                with open(fp, encoding="utf-8") as fh:
                    for row in csv.DictReader(fh):
                        code = (row.get("iata_code") or "").strip()
                        if len(code) != 3 or code in _COORDS:
                            continue
                        try:
                            _COORDS[code] = (float(row["latitude_deg"]), float(row["longitude_deg"]))
                            n += 1
                        except (TypeError, ValueError):
                            continue
            print(f"bt2_features: Meridian supplied coordinates for "
                  f"{len(_COORDS) - n} airports, {n} filled from {fp}")
    return _COORDS


def _mct(CB):
    global _MCT
    if _MCT is None:
        for cand in (os.path.join(paths.AVIA, "MCT Master List.xlsx"),):
            try:
                _MCT = CB.load_mct_data(cand, 90); break
            except Exception:
                _MCT = {}
    return _MCT


def load_legs_week(con, week, apset):
    """Distinct legs touching either endpoint in a weekly-snapshot week (live variant of
    bt2_capture.load_legs; a snapshot week needs no effective-date windowing)."""
    CB, _ = _cb()
    s = "(" + ",".join("'%s'" % a for a in apset) + ")"
    rows = con.execute("""SELECT DISTINCT carrier, flight_no, dep_airport, arr_airport,
        dep_terminal, arr_terminal, dep_country, arr_country, local_dep_time, local_arr_time,
        days_of_op, arr_days_of_op, flying_time, elapsed_time, alliance, carrier_category
        FROM oag WHERE week=? AND service_type='J'
        AND (dep_airport IN %s OR arr_airport IN %s)""" % (s, s), [week]).fetchall()
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
             'dep_day_set': CB.parse_days_string(dop),
             'arr_day_set': CB.parse_days_string(adop or dop),
             'alliance': str(alli or '').strip(), 'carrier_category': str(cat or '').strip(),
             'id': len(legs)}
        L['dom_int'] = CB.get_dom_int(L['dep_country'], L['arr_country'])
        legs.append(L)
    return legs


def _components(legs, a, b, block):
    CB, SC = _cb()
    alliances = SC.alliances_from_legs(legs) or CB.load_alliance_data()
    lcc = SC.lcc_from_legs(legs) or CB.DEFAULT_LCC_LIST
    coords = _coords(SC)
    mct = _mct(CB)
    out = []
    for oo, dd in ((a, b), (b, a)):
        leg1 = [l for l in legs if l['dep_airport'] == oo]
        leg2 = [l for l in legs if l['arr_airport'] == dd]
        if not leg1 or not leg2:
            out.append((0.0, 0.0, 0.0, block)); continue
        valid, _ = CB.build_connections(leg1, leg2, alliances, mct, lcc, 20, 720, 90, hub_airport=None)
        valid = SC.circuity_filter(valid, coords, 1.25)
        mn = min([c['elapsed_time'] for c in valid] + [block]) if valid else block
        S = {'ONLINE': 0.0, 'ALLIANCE': 0.0, 'INTERLINING': 0.0}
        for c in valid:
            S[c['cnx_type']] = S.get(c['cnx_type'], 0.0) + c['frequency'] * _et(c['elapsed_time'], mn)
        out.append((S['ONLINE'], S['ALLIANCE'], S['INTERLINING'], mn))
    return out


def _gcd_km(a, b):
    _, SC = _cb()
    c = _coords(SC)
    if a not in c or b not in c:
        return None
    (la1, lo1), (la2, lo2) = c[a], c[b]
    p = math.pi / 180.0
    x = 0.5 - math.cos((la2 - la1) * p) / 2 + math.cos(la1 * p) * math.cos(la2 * p) * (1 - math.cos((lo2 - lo1) * p)) / 2
    return 12742.0 * math.asin(math.sqrt(x))


def pair_metrics(con, week, a, b, planned_freq, gcd_km=None):
    """legs_n, qcx, capa (at planned freq), gcd for a candidate pair. Raises ValueError
    if gcd cannot be sourced (stop-and-flag rule: never silently default a feature)."""
    gcd = gcd_km or _gcd_km(a, b)
    if not gcd:
        raise ValueError(f"gcd unsourceable for {a}-{b} (missing coords)")
    block = int(gcd / 13.5) + 30
    legs = load_legs_week(con, week, {a, b})
    if not legs:
        raise ValueError(f"no schedule legs for {a}-{b} in week {week}")
    (so1, sa1, si1, mn1), (so2, sa2, si2, mn2) = _components(legs, a, b, block)
    qcx = (so1 + 0.75 * sa1 + 0.25 * si1) + (so2 + 0.75 * sa2 + 0.25 * si2)
    def cap(so, sa, si, mn):
        q = 0.20 * (so + 0.75 * sa + 0.25 * si)
        qns = planned_freq * _et(block, mn)
        return qns / (qns + q) if (qns + q) else 0.0
    capa = statistics.mean([cap(so1, sa1, si1, mn1), cap(so2, sa2, si2, mn2)])
    return {"legs_n": len(legs), "qcx": qcx, "capa": capa, "gcd": gcd, "block": block}


def endpoint_seats(oag_con, week, airport, carrier=None):
    """Departing seats at an airport in the reference week/month, REGION-DEDUPED.
    The store carries inter-regional flights in BOTH region files as exact duplicate
    rows; a raw SUM double-counts every international gateway. BT2 basis (bt2_months):
    group by region, take the airport's home region (the max - it holds ALL the
    airport's departures), sum within it. Carrier filter applies within the home region."""
    rows = oag_con.execute(
        "SELECT region, SUM(try_cast(seats AS DOUBLE)) s FROM oag "
        "WHERE week=? AND dep_airport=? GROUP BY region ORDER BY s DESC",
        [week, airport]).fetchall()
    if not rows:
        return 0.0
    home = rows[0][0]
    if carrier is None:
        return float(rows[0][1] or 0.0)
    v = oag_con.execute(
        "SELECT SUM(try_cast(seats AS DOUBLE)) FROM oag "
        "WHERE week=? AND dep_airport=? AND region=? AND carrier=?",
        [week, airport, home, carrier]).fetchone()[0]
    return float(v or 0.0)


_CITY = None


def _city_map(ref_csv):
    global _CITY
    if _CITY is None:
        import csv as _csv
        _CITY = {}
        for r in _csv.DictReader(open(ref_csv)):
            _CITY[r["airport_code"]] = r["city_code"]
    return _CITY


def sister_flag(oag_con, week, preagg_path, ref_csv, a, b, min_pax=1500):
    """True if the metro-pair already has an established nonstop at sister airports:
    another airport-pair within the same city-pair, nonstop in the reference week,
    with > min_pax O&D in the latest full Sabre year (v1.2 definition)."""
    city = _city_map(ref_csv)
    ca, cb = city.get(a), city.get(b)
    if not ca or not cb:
        return False
    aset = [k for k, v in city.items() if v == ca]
    bset = [k for k, v in city.items() if v == cb]
    if len(aset) == 1 and len(bset) == 1:
        return False
    sa = "(" + ",".join("'%s'" % x for x in aset) + ")"
    sb = "(" + ",".join("'%s'" % x for x in bset) + ")"
    served = oag_con.execute(
        ("SELECT DISTINCT dep_airport, arr_airport FROM oag WHERE week=? "
         "AND dep_airport IN %s AND arr_airport IN %s") % (sa, sb), [week]).fetchall()
    pairs = {(d, r) for d, r in served if (d, r) != (a, b)}
    if not pairs:
        return False
    import duckdb as _dk
    pc = _dk.connect(preagg_path, read_only=True)
    try:
        yr = pc.execute("SELECT max(year) FROM od_p2p").fetchone()[0]
        for d, r in pairs:
            v = pc.execute("SELECT SUM(pax) FROM od_p2p WHERE year=? AND ((o=? AND d=?) OR (o=? AND d=?))",
                           [yr, d, r, r, d]).fetchone()[0]
            if v and v > min_pax:
                return True
    finally:
        pc.close()
    return False


_MODEL = None


def batch_score(routes):
    """Batch BT2 scoring: ONE predict call per quantile (per-route forecast() is ~50x
    slower). routes = list of BT2 feature dicts; returns list of
    {pax, lo, hi, iqr_log, tier} aligned with input order."""
    import numpy as np
    global _MODEL
    import bt2_model as BM
    if _MODEL is None:
        _MODEL = BM.load(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                      "data", "bt2_model_v1_2.pkl"))
    m = _MODEL
    # v1.2 vector = v1.0 vector + [log1p(min base seats), log1p(max), share_a, share_b, sister]
    rows = []
    for r in routes:
        f = BM._vec(r, m["carid"])
        sa, sb = r["base_seats_a"], r["base_seats_b"]
        ta, tb = r["airport_seats_a"], r["airport_seats_b"]
        f += [math.log1p(min(sa, sb)), math.log1p(max(sa, sb)),
              (sa / ta if ta else 0), (sb / tb if tb else 0),
              1.0 if r.get("sister_flag") else 0.0]
        rows.append(f)
    X = np.array(rows)
    p50 = m["q50"].predict(X); p25 = m["q25"].predict(X); p75 = m["q75"].predict(X)
    out = []
    for i, r in enumerate(routes):
        iqr = float(p75[i] - p25[i])
        tier = "A" if (iqr <= 0.090 and not r.get("sister_flag")) else "B"   # v1.2 tier rule
        out.append({"pax": r["seats_ly"] * math.exp(float(p50[i])),
                    "lo": r["seats_ly"] * math.exp(float(p25[i])),
                    "hi": r["seats_ly"] * math.exp(float(p75[i])),
                    "iqr_log": iqr, "tier": tier})
    return out

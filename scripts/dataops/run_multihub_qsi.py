#!/usr/bin/env python3
"""
Avia Solutions - Multi-hub QSI runner
=====================================
One command from a multi-hub OAG schedules pull to a QSI capture for a proposed
service against full hub competition.

  load (calamine, fast) -> data-driven alliances/LCC -> build connections over
  every competing hub into the catchment -> inject the proposed service ->
  real MCT (config.MCT_MASTER) -> circuity cut -> QSI score -> capture per market.

Requires: python-calamine and airportsdata (pip install python-calamine airportsdata).
Run from the app directory so connection_builder, schedule_chain and config import.

Example:
  py -3.12 run_multihub_qsi.py --oag "Hub Airports.xlsx" \
     --catchment SFO,LAX,SJC,SAN,OAK \
     --proposed BA,LHR,SJC,1700,2000,645 --circuity 1.25 --out sjc_capture.csv
"""
import argparse, csv
from collections import defaultdict
from connection_builder import load_oag_legs, load_mct_data, build_connections
import schedule_chain as SC

CNX = {'ONLINE': 1.0, 'ALLIANCE': 0.615, 'INTERLINING': 0.25}
ET_F, ET_I = 0.8, 0.1


def _et(elapsed, mn):
    x = (elapsed - mn) / 60.0
    return 1.0 if x <= 0 else 1.0 / ((int(x / ET_I) + 1) ** ET_F)


def _proposed_leg(spec):
    """spec = carrier,dep,arr,deptime(HHMM),arrtime(HHMM),flyingmins"""
    car, dep, arr, dt, at, fly = spec.split(",")
    dh = int(dt[:2]) * 60 + int(dt[2:])
    ah = int(at[:2]) * 60 + int(at[2:])
    return {'carrier': car, 'flight_no': 'NEW', 'id': -1, 'dep_airport': dep, 'arr_airport': arr,
            'dep_terminal': '', 'arr_terminal': '', 'dep_time_mins': dh, 'arr_time_mins': ah,
            'flying_mins': int(fly), 'dep_day_set': set(range(1, 8)), 'arr_day_set': set(range(1, 8)),
            'dom_int': 'INT', 'arr_city': '', 'alliance': '', 'carrier_category': 'M', 'is_proposed': True}


def run(oag, catchment, proposed=None, circuity_cut=1.25, mct_file=None,
        min_connect=20, max_connect=720, default_mct=90):
    cat = set(catchment)
    legs = load_oag_legs(oag)
    alliances = SC.alliances_from_legs(legs) or []
    lcc = SC.lcc_from_legs(legs)
    if mct_file is None:
        try:
            from config import MCT_MASTER
            mct_file = str(MCT_MASTER)
        except Exception:
            pass
    mct = load_mct_data(mct_file, default_mct)

    arr_by = defaultdict(list)        # arrivals at each candidate hub (beyond -> hub)
    dep_by = defaultdict(list)        # hub -> catchment departures
    for l in legs:
        h = l.get('arr_airport')
        if h and h not in cat:
            arr_by[h].append(l)
        if l.get('dep_airport') not in cat and l.get('arr_airport') in cat:
            dep_by[l['dep_airport']].append(l)
    if proposed:
        dep_by[proposed['dep_airport']].append(proposed)

    coords = SC.load_airport_coords()
    conns = []
    for hub in dep_by:
        arr, dep = arr_by.get(hub, []), dep_by.get(hub, [])
        if not arr or not dep:
            continue
        v, _ = build_connections(arr, dep, alliances, mct, lcc,
                                 min_connect, max_connect, default_mct, hub_airport=hub)
        conns.extend(v)
    if circuity_cut:
        conns = SC.circuity_filter(conns, coords, circuity_cut)

    # QSI capture per beyond market; proposed = connections whose 2nd leg is the proposed service
    mn = defaultdict(lambda: 10 ** 9)
    for c in conns:
        if c['elapsed_time'] < mn[c['dep_airport']]:
            mn[c['dep_airport']] = c['elapsed_time']
    tot = defaultdict(float); prop = defaultdict(float); hubs = defaultdict(set)
    for c in conns:
        q = c['frequency'] * _et(c['elapsed_time'], mn[c['dep_airport']]) * CNX.get(c['cnx_type'], 0)
        tot[c['dep_airport']] += q
        hubs[c['dep_airport']].add(c['cnx_airport'])
        if c.get('leg2_is_proposed'):
            prop[c['dep_airport']] += q
    rows = [{'market': m, 'proposed_capture': (prop[m] / tot[m] if tot[m] else 0),
             'competing_hubs': len(hubs[m]), 'market_qsi': round(tot[m], 2)}
            for m in tot if tot[m] > 0]
    rows.sort(key=lambda r: -r['proposed_capture'])
    return {'connections': len(conns), 'markets': len(rows), 'rows': rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oag", required=True)
    ap.add_argument("--catchment", required=True, help="comma list, e.g. SFO,LAX,SJC,SAN,OAK")
    ap.add_argument("--proposed", help="carrier,dep,arr,deptime,arrtime,flyingmins  e.g. BA,LHR,SJC,1700,2000,645")
    ap.add_argument("--circuity", type=float, default=1.25)
    ap.add_argument("--mct", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    prop = _proposed_leg(a.proposed) if a.proposed else None
    res = run(a.oag, a.catchment.split(","), proposed=prop, circuity_cut=a.circuity, mct_file=a.mct)
    import statistics as st
    caps = [r['proposed_capture'] for r in res['rows'] if r['proposed_capture'] > 0]
    print(f"connections {res['connections']:,}  markets {res['markets']}")
    if caps:
        avg_hubs = sum(r['competing_hubs'] for r in res['rows']) / len(res['rows'])
        print(f"proposed capture: median {st.median(caps):.1%}  mean {sum(caps)/len(caps):.1%}  "
              f"(across {len(caps)} markets served; avg {avg_hubs:.0f} competing hubs/market)")
    if a.out:
        with open(a.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=['market', 'proposed_capture', 'competing_hubs', 'market_qsi'])
            w.writeheader(); w.writerows(res['rows'])
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()

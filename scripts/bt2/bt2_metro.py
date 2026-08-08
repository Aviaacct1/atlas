#!/usr/bin/env python3
"""Avia Solutions - BT2 metro-pair scoring test.
Hypothesis: part of route-level blind error is demand landing at a sister airport in
the same metro (LGW vs LHR, EWR vs JFK). Tests:
  1) Split: launches WITH established sister-airport nonstop service in the metro-pair
     vs without - if the sister subset scores worse, allocation noise is real.
  2) Metro increment scoring for the sister subset: forecast vs (metro nonstop in L
     minus metro nonstop in L-1), the allocation-corrected actual.
  3) Metro-aggregate: multi-launch metro-pairs (>=2 launches same metro-pair, same
     cohort), sum of forecasts vs sum of actuals.
One cohort per call: python3 bt2_metro.py --cohort 2018 ; --score when all done.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import argparse, csv, json, os, statistics
from collections import defaultdict
import duckdb

BT2 = _os.path.join(_paths.AVIA, "bt2")
SABRE = _paths.SABRE_DB

def metro_map():
    import airportsdata
    ap = airportsdata.load("IATA")
    return {k: (v.get("city", "") or k, v.get("country", "")) for k, v in ap.items()}

def build(L):
    outp = f"{BT2}/metro_ns_{L}.json"
    if os.path.exists(outp):
        print(f"{L}: already built"); return
    M = metro_map()
    con = duckdb.connect(SABRE, read_only=True)
    con.execute("SET memory_limit='3GB'; SET threads=4")
    agg = {}
    for y in (L, L - 1):
        rows = con.execute("""SELECT least(origin_airport,destination_airport),
            greatest(origin_airport,destination_airport), sum(passengers)
            FROM sabre WHERE itinerary='NON-STOP' AND source_year=?
            AND origin_airport<>destination_airport GROUP BY 1,2""", [y]).fetchall()
        d = defaultdict(float)
        pair_d = defaultdict(float)
        for a, b, p in rows:
            if not a or not b: continue
            ma, mb = M.get(a, (a, "")), M.get(b, (b, ""))
            k = tuple(sorted([f"{ma[0]}|{ma[1]}", f"{mb[0]}|{mb[1]}"]))
            d[k] += p or 0
            pair_d[(a, b)] = p or 0
        agg[str(y)] = {"|".join(k): v for k, v in d.items()}
        agg[f"pairs_{y}"] = {f"{a}-{b}": v for (a, b), v in pair_d.items()}
    json.dump(agg, open(outp, "w"))
    print(f"{L}: metro nonstop totals built ({len(agg[str(L)])} metro pairs)")

def score():
    M = metro_map()
    preds = list(csv.DictReader(open(f"{BT2}/bt2_blind_preds.csv")))
    def metro_key(a, b):
        ma, mb = M.get(a, (a, "")), M.get(b, (b, ""))
        return "|".join(sorted([f"{ma[0]}|{ma[1]}", f"{mb[0]}|{mb[1]}"]))
    out = defaultdict(list)
    inc_pairs, agg_groups = [], defaultdict(list)
    for r in preds:
        L = r["cohort"]
        mm = json.load(open(f"{BT2}/metro_ns_{L}.json")) if not hasattr(score, f"_c{L}") else getattr(score, f"_c{L}")
        setattr(score, f"_c{L}", mm)
        a, b = r["a"], r["b"]
        mk = metro_key(a, b)
        fc, ac = float(r["fc_blind"]), float(r["actual"])
        ns_L = mm[str(L)].get(mk, 0.0)
        ns_L1 = mm[str(int(L)-1)].get(mk, 0.0)
        own = mm[f"pairs_{L}"].get(f"{a}-{b}", 0) + mm[f"pairs_{L}"].get(f"{b}-{a}", 0)
        sister_est = ns_L1 > 1500          # established sister nonstop existed pre-launch
        multi_airport = (M.get(a, (a,))[0] != a) or True
        e = abs(fc/ac - 1)
        out["sister" if sister_est else "clean"].append(e)
        if sister_est:
            inc = ns_L - ns_L1             # metro increment = allocation-corrected actual
            if inc > 500:
                inc_pairs.append((fc, inc))
        agg_groups[(mk, L)].append((fc, ac))
    def rep(lbl, es):
        print(f"{lbl}: n={len(es)} within +-20% {100*sum(1 for x in es if x<=.2)/len(es):.1f}%  med {100*statistics.median(es):.1f}%")
    rep("no established sister nonstop (clean)", out["clean"])
    rep("established sister nonstop (allocation risk)", out["sister"])
    es = [abs(f/a-1) for f, a in inc_pairs if a > 0]
    rep("sister subset scored vs METRO INCREMENT", es)
    gg = [(sum(f for f, _ in v), sum(a for _, a in v)) for v in agg_groups.values() if len(v) >= 2]
    es = [abs(f/a-1) for f, a in gg if a > 0]
    rep(f"multi-launch metro-pairs aggregated (>=2 launches)", es)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", type=int)
    ap.add_argument("--score", action="store_true")
    a = ap.parse_args()
    if a.score: score()
    else: build(a.cohort)

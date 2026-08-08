#!/usr/bin/env python3
"""Avia Solutions - BT2 v1.2 tier recalibration, staged under the 45s cap.
Stage 1 (one cohort per call): python3 bt2_tier.py --cohort 2016
  LOCO q25/q50/q75 blind predictions on v1.2 config, mixed basis -> tier_preds_L.csv
Stage 2: python3 bt2_tier.py --sweep
"""
import argparse, csv, json, math, os
import numpy as np
from collections import Counter, defaultdict
from sklearn.ensemble import HistGradientBoostingRegressor
import bt2_lib as B
import airportsdata

B.COHORTS = (2016, 2017, 2018, 2019, 2025)
BT2 = B.BT2

def prep():
    rows = [r for r in B.load_clean() if r["actual"] > 0 and r["seats_ly"] > 0 and r["base_mkt"] > 0]
    db = {}
    for L in (2016, 2017, 2018, 2019):
        for r in csv.DictReader(open(f"{BT2}/db1b_outturn_{L}.csv")):
            db[(r["a"], r["b"], L)] = float(r["db1b_pax"])
    for r in rows:
        d = db.get((r["a"], r["b"], r["cohort"]))
        r["outturn"] = d if (d and d > 0) else r["actual"]
    base = {L: json.load(open(f"{BT2}/base_strength_{L}.json")) for L in B.COHORTS}
    tot = defaultdict(float)
    for L, d in base.items():
        for k, v in d.items():
            car, ap_, wk = k.split("|"); tot[(L, ap_, wk)] += v
    metro = {L: json.load(open(f"{BT2}/metro_ns_{L}.json")) for L in B.COHORTS}
    AP = airportsdata.load("IATA")
    def mkey(a, b):
        ma = (AP.get(a, {}).get("city") or a, AP.get(a, {}).get("country", ""))
        mb = (AP.get(b, {}).get("city") or b, AP.get(b, {}).get("country", ""))
        return "|".join(sorted([f"{ma[0]}|{ma[1]}", f"{mb[0]}|{mb[1]}"]))
    carc = Counter(r["oag_carrier"] for r in rows)
    carid = {c: i+1 for i, (c, n) in enumerate(carc.most_common()) if n >= 15}
    from bt2_model import _vec
    def feats(r):
        f = _vec({**r, "launch_mon": int(r["launch_month"][5:7]), "carrier": r["oag_carrier"]}, carid)
        L, pm, car = r["cohort"], r["pre_month"], r["oag_carrier"]
        sa = base[L].get(f"{car}|{r['a']}|{pm}", 0); sb = base[L].get(f"{car}|{r['b']}|{pm}", 0)
        ta = tot.get((L, r["a"], pm), 0); tb = tot.get((L, r["b"], pm), 0)
        r["sis"] = metro[L][str(L-1)].get(mkey(r["a"], r["b"]), 0) > 1500
        f += [math.log1p(min(sa, sb)), math.log1p(max(sa, sb)),
              (sa/ta if ta else 0), (sb/tb if tb else 0), 1.0 if r["sis"] else 0.0]
        return f
    return rows, feats

def mk(q):
    return HistGradientBoostingRegressor(loss="quantile", quantile=q, learning_rate=0.04,
        max_iter=600, max_leaf_nodes=31, min_samples_leaf=60, l2_regularization=5.0, random_state=7)

def cohort(L):
    outp = f"{BT2}/tier_preds_{L}.csv"
    if os.path.exists(outp):
        print(f"{L}: done already"); return
    rows, feats = prep()
    X = {id(r): feats(r) for r in rows}   # feats() also sets r['sis']
    tr = [r for r in rows if r["cohort"] != L]; te = [r for r in rows if r["cohort"] == L]
    Xtr = np.array([X[id(r)] for r in tr]); Xte = np.array([X[id(r)] for r in te])
    ytr = np.array([math.log(r["outturn"]/r["seats_ly"]) for r in tr])
    ps = {}
    for q in (0.25, 0.5, 0.75):
        m = mk(q); m.fit(Xtr, ytr); ps[q] = m.predict(Xte)
    with open(outp, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["a", "b", "cohort", "outturn", "fc", "iqr_log", "sister"])
        for r, p25, p50, p75 in zip(te, ps[0.25], ps[0.5], ps[0.75]):
            w.writerow([r["a"], r["b"], L, round(r["outturn"]),
                        round(r["seats_ly"]*math.exp(p50)), round(p75-p25, 4), r["sis"]])
    print(f"{L}: tier preds written (n={len(te)})")

def sweep():
    recs = []
    for L in B.COHORTS:
        for r in csv.DictReader(open(f"{BT2}/tier_preds_{L}.csv")):
            e = abs(float(r["fc"])/float(r["outturn"]) - 1)
            recs.append((float(r["iqr_log"]), e, r["sister"] == "True", int(r["cohort"])))
    recs.sort()
    n = len(recs)
    print(f"v1.2 blind tier sweep (n={n}, mixed basis, sister demoted from tier A):")
    for frac in (0.10, 0.15, 0.20, 0.25, 0.30):
        cut = recs[int(n*frac)][0]
        sel = [(e, L) for q, e, s, L in recs if q <= cut and not s]
        es = [e for e, _ in sel]
        w = 100*sum(1 for x in es if x <= .2)/len(es)
        e25 = [e for e, L in sel if L == 2025]
        w25 = 100*sum(1 for x in e25 if x <= .2)/len(e25) if e25 else 0
        print(f"  narrowest {frac*100:.0f}% (iqr<={cut:.3f}): n={len(es)} +-20% {w:.1f}% | 2025-only {w25:.1f}% (n={len(e25)})")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", type=int)
    ap.add_argument("--sweep", action="store_true")
    a = ap.parse_args()
    if a.sweep: sweep()
    else: cohort(a.cohort)

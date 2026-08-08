#!/usr/bin/env python3
"""Avia Solutions - BT2 claims layer.
1) Saves route-level BLIND (LOCO) predictions + q25/q75 spread to bt2_blind_preds.csv.
2) Portfolio (grouped) accuracy: sum(forecast) vs sum(actual) within baskets.
3) Confidence tier: narrow predicted IQR = tier A; blind +-20% within tier.
"""
import csv, math, statistics, sys
import numpy as np
import bt2_lib as B
from bt2_gbm import rows, X_of, y_of, make

SPEC = ["car", "qcx", "gro"]
KW = dict(minleaf=60, l2=5.0, lr=0.04, it=600)

def preds_q(tr, te, q):
    m = make(SPEC, q=q, **KW); m.fit(X_of(tr, SPEC), y_of(tr))
    return m.predict(X_of(te, SPEC))

def main():
    out = []
    for L in B.COHORTS:
        tr = [r for r in rows if r["cohort"] != L]
        te = [r for r in rows if r["cohort"] == L]
        p50 = preds_q(tr, te, 0.5); p25 = preds_q(tr, te, 0.25); p75 = preds_q(tr, te, 0.75)
        for r, a50, a25, a75 in zip(te, p50, p25, p75):
            out.append({"cohort": L, "a": r["a"], "b": r["b"],
                        "actual": r["actual"], "fc_blind": r["seats_ly"] * math.exp(a50),
                        "iqr_log": a75 - a25, "typ": r["typ"], "capband": B.cap_band(r["capa"]),
                        "haul": B.haul_band(r["gcd"]), "dom": r["dom"],
                        "seats_ly": r["seats_ly"], "months": r["months"]})
    with open(f"{B.BT2}/bt2_blind_preds.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    errs = [abs(o["fc_blind"]/o["actual"]-1) for o in out]
    print(f"route-level BLIND: n={len(out)} within+-20% {100*sum(1 for e in errs if e<=.2)/len(errs):.1f}%")

    # ---- confidence tiers by predicted IQR ----
    qs = statistics.quantiles([o["iqr_log"] for o in out], n=4)
    for nm, lo, hi in (("A-narrow", 0, qs[0]), ("AB-half", 0, qs[1]), ("ABC-3q", 0, qs[2])):
        sel = [o for o in out if lo <= o["iqr_log"] <= hi]
        e = [abs(o["fc_blind"]/o["actual"]-1) for o in sel]
        print(f"tier {nm:8s}: n={len(sel):4d} ({100*len(sel)/len(out):.0f}% of routes) "
              f"blind +-20%: {100*sum(1 for x in e if x<=.2)/len(e):.1f}%  med {100*statistics.median(e):.0f}%")

    # ---- portfolio claims ----
    def portfolio(groups, label):
        shares = []
        for g in groups:
            if len(g) < 3: continue
            F = sum(o["fc_blind"] for o in g); A = sum(o["actual"] for o in g)
            if A > 0: shares.append(abs(F/A-1))
        if shares:
            w20 = 100*sum(1 for e in shares if e <= .2)/len(shares)
            print(f"portfolio {label:34s}: {len(shares):3d} portfolios, within +-20%: {w20:.1f}%  med {100*statistics.median(shares):.0f}%")
    from collections import defaultdict
    for keyf, label in [
        (lambda o: (o["cohort"], o["capband"]), "cohort x capture band"),
        (lambda o: (o["cohort"], o["typ"], o["haul"]), "cohort x type x haul"),
        (lambda o: (o["cohort"], o["typ"]), "cohort x carrier type"),
    ]:
        d = defaultdict(list)
        for o in out: d[keyf(o)].append(o)
        portfolio(d.values(), label)
    # random baskets of n within cohort
    import random
    for n in (5, 10, 20):
        random.seed(11)
        groups = []
        for L in B.COHORTS:
            co = [o for o in out if o["cohort"] == L]; random.shuffle(co)
            groups += [co[i:i+n] for i in range(0, len(co), n) if len(co[i:i+n]) == n]
        portfolio(groups, f"random baskets of {n} (in-cohort)")

if __name__ == "__main__":
    main()

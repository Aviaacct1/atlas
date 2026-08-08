#!/usr/bin/env python3
"""Avia Solutions - BT2 gradient-boosted LF model (median/quantile loss).
Target: log(actual / seats_ly). Pred: seats_ly * exp(gbm). LOCO blind throughout.
python3 bt2_gbm.py G01 G02 ...
"""
import sys, math, statistics
import numpy as np
from collections import Counter
from sklearn.ensemble import HistGradientBoostingRegressor
import bt2_lib as B

rows = B.load_clean()
rows = [r for r in rows if r["actual"] > 0 and r["seats_ly"] > 0 and r["base_mkt"] > 0]

# carrier code -> integer id for carriers with >=15 launches in sample (else 0)
carc = Counter(r["oag_carrier"] for r in rows)
carid = {c: i + 1 for i, (c, n) in enumerate(carc.most_common()) if n >= 15}

def month_num(r): return int(r["launch_month"][5:7])

def X_of(rs, spec):
    out = []
    for r in rs:
        f = [math.log(r["seats_ly"]), math.log(r["base_mkt"]), r["capa"],
             math.log(max(r["freq"], .5)), math.log(1 + r["legs_n"]),
             math.log(r["months"]), math.log(max(r["gcd"], 100)),
             1.0 if r["typ"] == "LCC" else 0.0, 1.0 if r["dom"] else 0.0,
             r["gauge"], r["ncar"],
             math.log(r["seats_ly"] / r["base_mkt"]),      # capacity aggressiveness
             month_num(r)]
        if "qcx" in spec: f.append(math.log(1 + r["qcx"]))
        if "gro" in spec: f.append(math.log(max(min(r["mkt_growth"], 5.0), 0.2)))
        if "car" in spec: f.append(carid.get(r["oag_carrier"], 0))
        out.append(f)
    return np.array(out)

def y_of(rs): return np.array([math.log(r["actual"] / r["seats_ly"]) for r in rs])

def make(spec, q=0.5, lr=0.06, it=400, leaves=31, minleaf=30, l2=1.0):
    return HistGradientBoostingRegressor(loss="quantile", quantile=q,
        learning_rate=lr, max_iter=it, max_leaf_nodes=leaves,
        min_samples_leaf=minleaf, l2_regularization=l2, random_state=7)

def run(spec, **kw):
    m = make(spec, **kw); m.fit(X_of(rows, spec), y_of(rows))
    fitted = B.score([(r["seats_ly"] * math.exp(p), r["actual"])
                      for r, p in zip(rows, m.predict(X_of(rows, spec)))])
    bp = []
    for L in B.COHORTS:
        tr = [r for r in rows if r["cohort"] != L]
        te = [r for r in rows if r["cohort"] == L]
        m = make(spec, **kw); m.fit(X_of(tr, spec), y_of(tr))
        bp += [(r["seats_ly"] * math.exp(p), r["actual"])
               for r, p in zip(te, m.predict(X_of(te, spec)))]
    return fitted, B.score(bp)

GBMS = {
  "G01": ("GBM quantile-0.5 on logLF, full features", dict(spec=[])),
  "G02": ("G01 + carrier id (>=15 launches)", dict(spec=["car"])),
  "G03": ("G02, slower lr=0.03 it=800", dict(spec=["car"], lr=0.03, it=800)),
  "G04": ("G02, leaves=63", dict(spec=["car"], leaves=63)),
  "G05": ("G02, min_leaf=60 l2=5 (heavier reg)", dict(spec=["car"], minleaf=60, l2=5.0)),
  "G06": ("G02, min_leaf=100 l2=10", dict(spec=["car"], minleaf=100, l2=10.0)),
  "G07": ("G05, lr=0.04 it=600", dict(spec=["car"], minleaf=60, l2=5.0, lr=0.04, it=600)),
  "G08": ("G07 + qcx connection-competition feature", dict(spec=["car","qcx"], minleaf=60, l2=5.0, lr=0.04, it=600)),
  "G09": ("G08 + market growth L-2->L-1", dict(spec=["car","qcx","gro"], minleaf=60, l2=5.0, lr=0.04, it=600)),
}

def run_ens(spec, seeds=(7, 27, 47), **kw):
    """Seed ensemble: average log-LF predictions across seeds."""
    def preds(tr, te):
        P = np.zeros(len(te))
        for s in seeds:
            m = make(spec, **kw); m.set_params(random_state=s)
            m.fit(X_of(tr, spec), y_of(tr)); P += m.predict(X_of(te, spec))
        return P / len(seeds)
    fitted = B.score([(r["seats_ly"] * math.exp(p), r["actual"])
                      for r, p in zip(rows, preds(rows, rows))])
    bp = []
    for L in B.COHORTS:
        tr = [r for r in rows if r["cohort"] != L]
        te = [r for r in rows if r["cohort"] == L]
        bp += [(r["seats_ly"] * math.exp(p), r["actual"]) for r, p in zip(te, preds(tr, te))]
    blind = B.score(bp)
    # forward-blind: train 2016-2018, forecast 2019 (the honest product claim)
    tr = [r for r in rows if r["cohort"] != 2019]; te = [r for r in rows if r["cohort"] == 2019]
    fwd = B.score([(r["seats_ly"] * math.exp(p), r["actual"]) for r, p in zip(te, preds(tr, te))])
    return fitted, blind, fwd

if __name__ == "__main__":
    for eid in sys.argv[1:]:
        if eid.startswith("ENS"):
            kw = dict(spec=["car", "qcx"], minleaf=60, l2=5.0, lr=0.04, it=600)
            fitted, blind, fwd = run_ens(**kw)
            B.log_line(eid, "5-seed ensemble of G08", fitted, blind,
                       f"fwd2019 +-20%: {fwd['w20']*100:.1f}%")
        else:
            desc, kw = GBMS[eid]
            fitted, blind = run(**kw)
            B.log_line(eid, desc, fitted, blind, "logged")

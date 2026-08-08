#!/usr/bin/env python3
"""Avia Solutions - BT2 regression experiments (log-space, LOCO blind).
python3 bt2_reg.py R01 R02 ...
"""
import sys, math, statistics
import numpy as np
import bt2_lib as B

rows = B.load_master()
rows = [r for r in rows if r["actual"] > 0 and r["seats_ly"] > 0 and r["base_mkt"] > 0]

def feats(r, spec):
    f = [1.0]
    if "seats" in spec: f.append(math.log(r["seats_ly"]))
    if "base" in spec:  f.append(math.log(r["base_mkt"]))
    if "cap" in spec:   f.append(r["capa"])
    if "freq" in spec:  f.append(math.log(max(r["freq"], 0.5)))
    if "legs" in spec:  f.append(math.log(1 + r["legs_n"]))
    if "months" in spec: f.append(math.log(r["months"]))
    if "gcd" in spec:   f.append(math.log(max(r["gcd"], 100)))
    if "dums" in spec:
        f += [1.0 if r["typ"] == "LCC" else 0.0, 1.0 if r["dom"] else 0.0]
        hb = B.haul_band(r["gcd"])
        f += [1.0 if hb == h else 0.0 for h in ("H1-mid", "H2-long", "H3-vlong")]
    return f

def fit_predict(train, test, spec, resid_key=None):
    X = np.array([feats(r, spec) for r in train])
    y = np.array([math.log(r["actual"]) for r in train])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    def raw(r): return float(np.dot(feats(r, spec), beta))
    # median residual correction (log space) per cell, optional
    corr = {}
    gcorr = statistics.median([math.log(r["actual"]) - raw(r) for r in train])
    if resid_key:
        from collections import defaultdict
        cells = defaultdict(list)
        for r in train: cells[resid_key(r)].append(math.log(r["actual"]) - raw(r))
        corr = {k: statistics.median(v) for k, v in cells.items() if len(v) >= 8}
    out = []
    for r in test:
        c = corr.get(resid_key(r), gcorr) if resid_key else gcorr
        out.append((math.exp(raw(r) + c), r["actual"], r))
    return out

def run(spec, resid_key=None):
    fitted = B.score([(f, a) for f, a, _ in fit_predict(rows, rows, spec, resid_key)])
    bp = []
    for L in B.COHORTS:
        tr = [r for r in rows if r["cohort"] != L]
        te = [r for r in rows if r["cohort"] == L]
        bp += [(f, a) for f, a, _ in fit_predict(tr, te, spec, resid_key)]
    return fitted, B.score(bp)

REGS = {
  "R01": ("OLS ln(pax)~ln(seats)", ["seats"], None),
  "R02": ("OLS + base,cap,freq,legs,months,dums", ["seats","base","cap","freq","legs","months","dums"], None),
  "R03": ("R02 + gcd", ["seats","base","cap","freq","legs","months","gcd","dums"], None),
  "R04": ("R03 + residual cells type x haul", ["seats","base","cap","freq","legs","months","gcd","dums"],
          lambda r: (r["typ"], B.haul_band(r["gcd"]))),
  "R05": ("R03 + residual cells legsband x freqband", ["seats","base","cap","freq","legs","months","gcd","dums"],
          lambda r: (min(3, r["legs_n"]//1500), min(3, int(r["freq"]//4)))),
}

if __name__ == "__main__":
    for eid in sys.argv[1:]:
        desc, spec, rk = REGS[eid]
        fitted, blind = run(spec, rk)
        B.log_line(eid, desc, fitted, blind, "logged")

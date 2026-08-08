#!/usr/bin/env python3
"""Avia Solutions - BT2 shared lib: master table + scoring + experiment log."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import csv, math, statistics, time
from collections import defaultdict

BT2 = _os.path.join(_paths.AVIA, "bt2")
COHORTS = (2016, 2017, 2018, 2019)
STIM = 1.30

LCC_SET = None
def lcc_set():
    global LCC_SET
    if LCC_SET is None:
        import sys; sys.path.insert(0, _paths.QSI_APP)
        import connection_builder as CB
        LCC_SET = set(CB.DEFAULT_LCC_LIST)
    return LCC_SET

def load_master():
    lcc = lcc_set()
    rows = []
    for L in COHORTS:
        caps = {}
        with open(f"{BT2}/capture_{L}.csv") as f:
            for r in csv.DictReader(f):
                caps[(r["a"], r["b"])] = r
        gro = {}
        try:
            with open(f"{BT2}/growth_{L}.csv") as f:
                for r in csv.DictReader(f):
                    gro[(r["a"], r["b"])] = float(r["base_mkt_m2"] or 0)
        except FileNotFoundError:
            pass
        with open(f"{BT2}/launch_profile_{L}.csv") as f:
            for r in csv.DictReader(f):
                c = caps.get((r["a"], r["b"]))
                if not c or not c.get("cap_f5"):
                    continue
                d = dict(r)
                d.update(cohort=L, actual=float(r["launch_pax"]), base_mkt=float(r["base_mkt"]),
                         gcd=float(r["gcd_km"] or 0), months=int(r["months_operated"]),
                         seats_ly=float(r["seats_ly"]), freq=float(r["wk_freq_dir"]),
                         gauge=float(r["gauge"] or 0), ncar=int(r["n_carriers"]),
                         cap5=float(c["cap_f5"]), capa=float(c["cap_actual"]),
                         legs_n=int(c["legs_n"] or 0),
                         qcx=(float(c["so_ab"] or 0) + 0.75*float(c["sa_ab"] or 0) + 0.25*float(c["si_ab"] or 0)
                              + float(c["so_ba"] or 0) + 0.75*float(c["sa_ba"] or 0) + 0.25*float(c["si_ba"] or 0)),
                         typ="LCC" if (r["carrier"] in lcc or r["oag_carrier"] in lcc) else "FSC",
                         dom=(r["ctry_a"] == r["ctry_b"] and r["ctry_a"] != ""))
                bm2 = gro.get((r["a"], r["b"]), 0.0)
                d["mkt_growth"] = (d["base_mkt"] / bm2) if bm2 >= 500 else 1.0
                d["artifact"] = d["seats_ly"] > 0 and d["actual"] > 1.1 * d["seats_ly"]
                rows.append(d)
    return rows

def load_clean():
    """Master minus pax>1.1x seats artifacts (flagged exclusion, reported once)."""
    rows = load_master()
    n_art = sum(1 for r in rows if r["artifact"])
    print(f"excluded {n_art} pax>1.1x-seats artifacts (Sabre/OAG mismatch), kept {len(rows)-n_art}")
    return [r for r in rows if not r["artifact"]]

def haul_band(g):
    if g < 800: return "H0-short"
    if g < 2000: return "H1-mid"
    if g < 4500: return "H2-long"
    return "H3-vlong"

def size_band(bm):
    if bm < 8000: return "S0"
    if bm < 25000: return "S1"
    if bm < 80000: return "S2"
    return "S3"

def cap_band(c):
    for lo, hi, nm in ((0,.05,"C0"),(.05,.15,"C1"),(.15,.40,"C2"),(.40,.80,"C3"),(.80,1.01,"C4")):
        if lo <= c < hi: return nm
    return "C4"

def score(pairs):
    """pairs = [(forecast, actual)]; returns dict of metrics."""
    errs = sorted(abs(f / a - 1) for f, a in pairs if a > 0 and f > 0)
    n = len(errs)
    if not n: return {"n": 0}
    return {"n": n, "med": statistics.median(errs),
            "w20": sum(1 for e in errs if e <= 0.20) / n,
            "w50": sum(1 for e in errs if e <= 0.50) / n}

def fit_ratio(rows, keyfn, predfn, min_n=8):
    """Median actual/pred per cell; fallback to global median."""
    cells = defaultdict(list)
    allr = []
    for r in rows:
        p = predfn(r)
        if p and p > 0 and r["actual"] > 0:
            u = r["actual"] / p
            cells[keyfn(r)].append(u); allr.append(u)
    gmed = statistics.median(allr) if allr else 1.0
    tab = {k: (statistics.median(v) if len(v) >= min_n else gmed) for k, v in cells.items()}
    return tab, gmed

def apply_cfg(rows_fit, rows_score, predfn, keyfn, min_n=8):
    tab, gmed = fit_ratio(rows_fit, keyfn, predfn, min_n)
    out = []
    for r in rows_score:
        p = predfn(r)
        if not p or p <= 0 or r["actual"] <= 0: continue
        out.append((p * tab.get(keyfn(r), gmed), r["actual"], r))
    return out

def run_experiment(rows, predfn, keyfn, min_n=8):
    """Returns (fitted metrics, blind LOCO metrics)."""
    fitted = score([(f, a) for f, a, _ in apply_cfg(rows, rows, predfn, keyfn, min_n)])
    blind_pairs = []
    for L in COHORTS:
        tr = [r for r in rows if r["cohort"] != L]
        te = [r for r in rows if r["cohort"] == L]
        blind_pairs += [(f, a) for f, a, _ in apply_cfg(tr, te, predfn, keyfn, min_n)]
    blind = score(blind_pairs)
    return fitted, blind

def log_line(expid, desc, fitted, blind, verdict):
    line = (f"{time.strftime('%d %b %Y %H:%M')} | {expid} | {desc} | "
            f"fitted +-20%: {fitted.get('w20',0)*100:.1f}% (n={fitted.get('n',0)}) | "
            f"blind +-20%: {blind.get('w20',0)*100:.1f}% med {blind.get('med',9)*100:.0f}% | {verdict}")
    with open(f"{BT2}/bt2_experiments.log", "a") as f:
        f.write(line + "\n")
    print(line)

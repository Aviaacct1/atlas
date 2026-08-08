#!/usr/bin/env python3
"""Avia Solutions - BT2 Stage 3: launch profile per candidate pair.
From pair_months_L.csv: OAG-confirmed launch month, launching carrier, operated
months, weekly frequency, gauge, launch-year seats, competitive structure.
Excludes (flagged, not filled): no OAG nonstop; OAG service already in L-1;
sub-weekly service (<4 ops in every month).
Writes launch_profile_L.csv. All cohorts in one call.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import csv
from collections import defaultdict

BT2 = _os.path.join(_paths.AVIA, "bt2")
MIN_OPS = 4  # ops per month for a "launched" month (~weekly)

def run(L):
    cand = {}
    with open(f"{BT2}/launches_{L}.csv") as f:
        for r in csv.DictReader(f):
            cand[(r["a"], r["b"])] = r
    series = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0, 0])))
    with open(f"{BT2}/pair_months_{L}.csv") as f:
        for r in csv.DictReader(f):
            s = series[(r["a"], r["b"])][r["mon"]][r["carrier"]]
            s[0] += int(r["ops"] or 0); s[1] += int(float(r["seats"] or 0))
    out, excl = [], defaultdict(int)
    for pair, c in cand.items():
        mons = series.get(pair)
        if not mons:
            excl["no_oag_service"] += 1; continue
        pre_months = [m for m in mons if m.startswith(str(L - 1))]
        pre_ops = sum(v[0] for m in pre_months for v in mons[m].values())
        if pre_ops > MIN_OPS:  # tolerate stray ops; real service in L-1 = not virgin
            excl["oag_preexist_L-1"] += 1; continue
        lmons = sorted(m for m in mons if m.startswith(str(L)) and "-H" not in m)
        if not lmons and any("-H" in m for m in mons):
            excl["half_year_only_AF_ME"] += 1; continue
        launched = [m for m in lmons if sum(v[0] for v in mons[m].values()) >= MIN_OPS]
        if not launched:
            excl["sub_weekly"] += 1; continue
        lm = launched[0]
        op_mons = [m for m in lmons if m >= lm and sum(v[0] for v in mons[m].values()) > 0]
        tot_ops = sum(v[0] for m in op_mons for v in mons[m].values())
        tot_seats = sum(v[1] for m in op_mons for v in mons[m].values())
        by_car = defaultdict(int)
        for m in op_mons:
            for car, v in mons[m].items():
                by_car[car] += v[0]
        oag_carrier = max(by_car, key=by_car.get)
        n_carriers = len([k for k, v in by_car.items() if v >= MIN_OPS])
        wk_freq = tot_ops / (len(op_mons) * 4.345) / 2.0  # per direction
        y, mo = int(lm[:4]), int(lm[5:7])
        pre_m = f"{y-1}-12" if mo == 1 else f"{y}-{mo-1:02d}"
        out.append({**c, "launch_month": lm, "pre_month": pre_m,
                    "months_operated": len(op_mons), "ops_ly": tot_ops,
                    "seats_ly": tot_seats, "wk_freq_dir": round(wk_freq, 2),
                    "gauge": round(tot_seats / tot_ops) if tot_ops else "",
                    "oag_carrier": oag_carrier, "n_carriers": n_carriers})
    with open(f"{BT2}/launch_profile_{L}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)
    print(f"cohort {L}: kept {len(out)} | excluded: " +
          ", ".join(f"{k}={v}" for k, v in sorted(excl.items())))

if __name__ == "__main__":
    import sys
    cohorts = [int(x) for x in sys.argv[1:]] or [2016, 2017, 2018, 2019]
    for L in cohorts:
        run(L)

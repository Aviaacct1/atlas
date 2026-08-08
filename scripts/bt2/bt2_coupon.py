#!/usr/bin/env python3
"""Avia Solutions - BT2: DB1B Coupon segment traversals for the adjudication test.
Question: is DB1B internally consistent with the T-100 census? Coupon passengers
x10 summed by flown segment ~ onboard; compare to T-100 class-F onboard per route
per launch year. If coupons track the census, DB1B's O&D allocation is trustworthy
and divergence from Sabre is evidence against Sabre, not DB1B.
Streamed halves (SPLIT=20m rows):
  python3 bt2_coupon.py --cohort 2018 --quarter 2 --part 1|2
  python3 bt2_coupon.py --cohort 2018 --assemble
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import argparse, csv, glob, os, subprocess, sys

BT2 = _os.path.join(_paths.AVIA, "bt2")
US = _paths.US_MARKET
SPLIT = 20_000_000

def us_pairs(L):
    out = []
    with open(f"{BT2}/launch_profile_{L}.csv") as f:
        for r in csv.DictReader(f):
            if r["ctry_a"] == "US" and r["ctry_b"] == "US":
                out.append((r["a"], r["b"]))
    return out

def run_part(L, Q, part):
    outp = f"{BT2}/cpn_qtr_{L}_{Q}p{part}.csv"
    if os.path.exists(outp) and os.path.getsize(outp) > 20:
        print(f"{L} Q{Q} p{part}: already done"); return
    d = f"{US}/Origin_and_Destination_Survey_DB1BCoupon_{L}_{Q}"
    csvs = glob.glob(f"{d}/*.csv")
    if not csvs:
        print(f"{L} Q{Q}: NO EXTRACT"); sys.exit(1)
    f = csvs[0].replace("'", "'\\''")
    feed = (f"head -n {SPLIT + 1} '{f}'" if part == 1
            else f"(head -n 1 '{f}'; tail -n +{SPLIT + 2} '{f}')")
    aps = sorted({x for p in us_pairs(L) for x in p})
    s = "(" + ",".join(f"'{a}'" for a in aps) + ")"
    py = f"""import duckdb
con = duckdb.connect(); con.execute("SET memory_limit='3GB'; SET threads=8")
q = '''COPY (SELECT least(Origin,Dest) a, greatest(Origin,Dest) b,
  sum(try_cast(Passengers AS DOUBLE)) pax_sample
  FROM read_csv('/dev/stdin', header=true)
  WHERE Origin IN {s} AND Dest IN {s} GROUP BY 1,2)
TO '{outp}.tmp' (HEADER)'''
con.execute(q)
"""
    scr = f"{BT2}/_cpn_worker.py"
    open(scr, "w").write(py)
    r = subprocess.run(f"{feed} | python3 {scr}", shell=True,
                       capture_output=True, text=True, executable="/bin/bash")
    if r.returncode != 0:
        print(f"{L} Q{Q} p{part}: FAILED\n{r.stderr[-300:]}"); sys.exit(1)
    os.replace(f"{outp}.tmp", outp)
    print(f"{L} Q{Q} p{part}: done")

def assemble(L):
    pairs = set(us_pairs(L))
    agg, quarters = {}, set()
    for Q in (1, 2, 3, 4):
        parts = sorted(glob.glob(f"{BT2}/cpn_qtr_{L}_{Q}p*.csv"))
        if not parts: continue
        quarters.add(Q)
        for p in parts:
            for r in csv.DictReader(open(p)):
                k = (r["a"], r["b"])
                if k in pairs:
                    agg[k] = agg.get(k, 0) + float(r["pax_sample"] or 0)
    nq = len(quarters)
    with open(f"{BT2}/coupon_seg_{L}.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["a", "b", "coupon_seg_pax", "quarters"])
        for (a, b), v in sorted(agg.items()):
            w.writerow([a, b, round(v * 10 * 4 / nq), nq])
    print(f"{L}: assembled {len(agg)} segment pairs from {nq} quarters")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", type=int, required=True)
    ap.add_argument("--quarter", type=int)
    ap.add_argument("--part", type=int, default=1)
    ap.add_argument("--assemble", action="store_true")
    a = ap.parse_args()
    if a.assemble: assemble(a.cohort)
    else: run_part(a.cohort, a.quarter, a.part)

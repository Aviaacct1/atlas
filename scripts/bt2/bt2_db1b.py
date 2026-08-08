#!/usr/bin/env python3
"""Avia Solutions - BT2: DB1B outturn for US-domestic launches (outturn re-scoring).
Nonstop = MktCoupons=1; passengers x10 (DB1B is a 10% ticket sample); both directions
summed per pair per year. Quarters parsed in two streamed halves to fit the 45s cap:
  python3 bt2_db1b.py --cohort 2018 --quarter 2 --part 1     (rows 1..15m)
  python3 bt2_db1b.py --cohort 2018 --quarter 2 --part 2     (rows 15m+)
  python3 bt2_db1b.py --cohort 2018 --assemble
2016 Q1 extract is missing on the E: store: 2016 is assembled from 3 quarters,
scaled 4/3 and flagged - not silently filled.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import argparse, csv, glob, os, subprocess, sys

BT2 = _os.path.join(_paths.AVIA, "bt2")
US = _paths.US_MARKET
SPLIT = 15_000_000   # rows in part 1

def us_pairs(L):
    out = []
    with open(f"{BT2}/launch_profile_{L}.csv") as f:
        for r in csv.DictReader(f):
            if r["ctry_a"] == "US" and r["ctry_b"] == "US":
                out.append((r["a"], r["b"]))
    return out

def run_part(L, Q, part):
    outp = f"{BT2}/db1b_qtr_{L}_{Q}p{part}.csv"
    if os.path.exists(outp) and os.path.getsize(outp) > 20:
        print(f"{L} Q{Q} p{part}: already done"); return
    d = f"{US}/Origin_and_Destination_Survey_DB1BMarket_{L}_{Q}"
    csvs = glob.glob(f"{d}/*.csv")
    if not csvs:
        print(f"{L} Q{Q}: NO EXTRACT (flagged, not filled)")
        open(f"{BT2}/db1b_qtr_{L}_{Q}.MISSING", "w").write("no extract on E: store\n")
        return
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
  WHERE try_cast(MktCoupons AS INT)=1 AND Origin IN {s} AND Dest IN {s} GROUP BY 1,2)
TO '{outp}.tmp' (HEADER)'''
con.execute(q)
"""
    scr = f"{BT2}/_db1b_worker.py"
    open(scr, "w").write(py)
    r = subprocess.run(f"{feed} | python3 {scr}", shell=True,
                       capture_output=True, text=True, executable="/bin/bash")
    if r.returncode != 0:
        print(f"{L} Q{Q} p{part}: FAILED\n{r.stderr[-400:]}"); sys.exit(1)
    os.replace(f"{outp}.tmp", outp)
    print(f"{L} Q{Q} p{part}: done")

def assemble(L):
    pairs = set(us_pairs(L))
    agg, quarters, miss = {}, set(), []
    for Q in (1, 2, 3, 4):
        parts = sorted(glob.glob(f"{BT2}/db1b_qtr_{L}_{Q}p*.csv")) or \
                ([f"{BT2}/db1b_qtr_{L}_{Q}.csv"] if os.path.exists(f"{BT2}/db1b_qtr_{L}_{Q}.csv")
                 and os.path.getsize(f"{BT2}/db1b_qtr_{L}_{Q}.csv") > 20 else [])
        if not parts:
            miss.append(Q); continue
        quarters.add(Q)
        for p in parts:
            for r in csv.DictReader(open(p)):
                k = (r["a"], r["b"])
                if k in pairs:
                    agg[k] = agg.get(k, 0) + float(r["pax_sample"])
    nq = len(quarters)
    with open(f"{BT2}/db1b_outturn_{L}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["a", "b", "db1b_pax", "quarters", "scaled"])
        for (a, b), v in sorted(agg.items()):
            w.writerow([a, b, round(v * 10 * 4 / nq), nq, nq < 4])
    print(f"{L}: assembled {len(agg)} pairs from {nq} quarters" +
          (f" (missing Q{miss} - scaled 4/{nq}, FLAGGED)" if miss else ""))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", type=int, required=True)
    ap.add_argument("--quarter", type=int)
    ap.add_argument("--part", type=int, default=1)
    ap.add_argument("--assemble", action="store_true")
    a = ap.parse_args()
    if a.assemble: assemble(a.cohort)
    else: run_part(a.cohort, a.quarter, a.part)

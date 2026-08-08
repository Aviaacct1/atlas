"""validate_bt2_integration - run BEFORE adopting BT2 candidate output (John's machine).
Three checks per the integration instruction:
  1. Feature ranges: pair_metrics on ~100 live pairs vs BT2 training ranges
     (capture_2019.csv) - catches silent defaulting of legs_n/qcx.
  2. Dual-method comparison: BT2 vs superseded uplift table on the same floors.
  3. If webapp/data/bum_candidates.json exists, summarise the new fields.
Usage:  py -3.12 scripts\\validate_bt2_integration.py [--qsi "<QSI app path>"]
Author: Avia Solutions.
"""
import argparse, csv, json, os, statistics, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts")); sys.path.insert(0, REPO)
from avia_forecast import paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qsi", default=paths.QSI_APP)
    ap.add_argument("--oag", default=paths.OAG_DB)
    ap.add_argument("--ref", default=os.path.join(paths.AVIA, "bt2", "capture_2019.csv"))
    ap.add_argument("--n", type=int, default=100)
    a = ap.parse_args()
    sys.path.insert(0, a.qsi)
    import duckdb
    import bt2_features as BF

    ref = list(csv.DictReader(open(a.ref)))
    r_legs = sorted(int(r["legs_n"]) for r in ref if r["legs_n"])
    r_qcx = sorted((float(r["so_ab"] or 0) + .75*float(r["sa_ab"] or 0) + .25*float(r["si_ab"] or 0)
                    + float(r["so_ba"] or 0) + .75*float(r["sa_ba"] or 0) + .25*float(r["si_ba"] or 0))
                   for r in ref if r["so_ab"] != "")
    print(f"training ref: legs_n p5-p95 {r_legs[len(r_legs)//20]}-{r_legs[19*len(r_legs)//20]}, "
          f"qcx p5-p95 {r_qcx[len(r_qcx)//20]:.1f}-{r_qcx[19*len(r_qcx)//20]:.1f}")

    con = duckdb.connect(a.oag, read_only=True)
    week = con.execute("SELECT max(week) FROM oag WHERE week LIKE '20__-__-__'").fetchone()[0]
    pairs = con.execute("""SELECT dep_airport, arr_airport, SUM(try_cast(seats AS DOUBLE)) s
        FROM oag WHERE week=? AND service_type='J' GROUP BY 1,2
        HAVING s > 5000 ORDER BY random() LIMIT ?""", [week, a.n]).fetchall()
    legs_v, qcx_v, feats = [], [], []
    for o, d, _ in pairs:
        try:
            pm = BF.pair_metrics(con, week, o, d, planned_freq=5)
        except ValueError as e:
            print("  flagged (correctly skipped):", e); continue
        legs_v.append(pm["legs_n"]); qcx_v.append(pm["qcx"])
        feats.append({"seats_ly": 220*5*52*2, "base_mkt": 50000.0, "capa": pm["capa"], "freq": 5,
                      "legs_n": pm["legs_n"], "months": 12, "gcd": pm["gcd"], "typ": "LCC",
                      "dom": False, "gauge": 220, "ncar": 1, "launch_mon": 6,
                      "qcx": pm["qcx"], "mkt_growth": 1.0, "carrier": "",
                      "base_seats_a": 0.0, "base_seats_b": 0.0,
                      "airport_seats_a": BF.endpoint_seats(con, week, o),
                      "airport_seats_b": BF.endpoint_seats(con, week, d),
                      "sister_flag": False})   # sister off in the synthetic check; live scripts compute it
    legs_v.sort(); qcx_v.sort()
    print(f"live sample n={len(legs_v)}: legs_n med {legs_v[len(legs_v)//2]}, "
          f"qcx med {qcx_v[len(qcx_v)//2]:.1f}")
    in_l = sum(1 for v in legs_v if r_legs[0] <= v <= r_legs[-1]) / len(legs_v)
    in_q = sum(1 for v in qcx_v if r_qcx[0] <= v <= r_qcx[-1]) / len(qcx_v)
    print(f"within training range: legs_n {in_l:.0%}, qcx {in_q:.0%}  "
          f"({'OK' if min(in_l, in_q) > 0.9 else 'INVESTIGATE - possible definition drift'})")
    zero_q = sum(1 for v in qcx_v if v == 0.0) / len(qcx_v)
    print(f"qcx exactly zero: {zero_q:.0%} ({'OK' if zero_q < 0.3 else 'INVESTIGATE - components may be silently failing'})")

    import qsi_calibration as QC
    scores = BF.batch_score(feats)
    ratios = []
    for f, s in zip(feats, scores):
        old, _, _ = QC.calibrated(f["base_mkt"] * f["capa"], f["capa"])
        if old > 0:
            ratios.append(s["pax"] / old)
    ratios.sort()
    print(f"BT2 vs uplift-table on same candidates: median ratio {ratios[len(ratios)//2]:.2f}x, "
          f"p10-p90 {ratios[len(ratios)//10]:.2f}-{ratios[9*len(ratios)//10]:.2f}x")
    ta = sum(1 for s in scores if s["tier"] == "A") / len(scores)
    print(f"tier A share of sample: {ta:.0%}")

    # permanent region-dedupe check (QSI thread, 5 Aug): endpoint_seats must match the
    # BT2 deduped basis; a raw store sum runs ~1.2-1.5x at international gateways.
    ref_bs = os.path.join(paths.AVIA, "bt2", "base_strength_2019.json")
    if os.path.exists(ref_bs):
        bs = json.load(open(ref_bs))
        ok_all = True
        for ap, mon in (("LHR", "2019-03"), ("JFK", "2019-03"), ("SIN", "2019-05")):
            want = sum(float(v) for k, v in bs.items() if k.split("|")[1:] == [ap, mon])
            got = BF.endpoint_seats(con, mon, ap)
            ratio = got / want if want else 0.0
            ok = 0.99 <= ratio <= 1.01
            ok_all = ok_all and ok
            print(f"region-dedupe {ap} {mon}: builder/BT2 ratio {ratio:.3f} "
                  f"({'OK' if ok else 'FAIL - raw-sum regression, fix endpoint_seats'})")
        if not ok_all:
            print("DO NOT ADOPT: endpoint_seats is double-counting inter-regional rows")
    else:
        print("region-dedupe check SKIPPED: base_strength_2019.json not found - do not adopt without it")

    bc = os.path.join(REPO, "webapp", "data", "bum_candidates.json")
    if os.path.exists(bc):
        d = json.load(open(bc))
        rows = [r for k, v in d.items() if not k.startswith("_") and isinstance(v, list) for r in v]
        with_bt2 = [r for r in rows if r.get("tier")]
        print(f"bum_candidates.json: {len(rows)} rows, {len(with_bt2)} carry BT2 fields "
              f"(est/lo/hi/tier present: {'yes' if with_bt2 and all(x in with_bt2[0] for x in ('est_lo_000','est_hi_000')) else 'CHECK'})")
    print("VALIDATION COMPLETE - adopt only if all checks read OK")


if __name__ == "__main__":
    main()

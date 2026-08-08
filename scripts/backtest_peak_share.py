"""Blind test of the peak hour share projection against a held-out year.
Author: Avia Solutions.

The elasticity was fitted on 2015 to 2019 and every judgement about it so far has been
made on those same years. This holds 2025 back, projects each airport's peak hour share
forward from its last fitted year using its ACTUAL traffic growth, and scores the
projection against what the schedules say actually happened.

Using actual traffic rather than a forecast is deliberate. It isolates the thing under
test. If the demand forecast were in the loop, a good result could come from two errors
cancelling and a bad one could be the demand side's fault.

Four methods are scored against each other:

    flat        hold the share constant, which is what the v0.1 convention did
    single      one elasticity for every airport
    class       the elasticity of the airport's size class
    curve       the size-varying elasticity

The honest expectation is that this is a harsh test. 2019 to 2025 spans the pandemic and
the schedule restructuring that followed, so any airport that rebuilt its bank structure
will score badly on every method. That is the point: a parameter that only works across
undisturbed years is not one to put in front of a client.

    cd C:\\Avia\\avia_forecast_build
    python scripts\\backtest_peak_share.py --fit-years 2015,2016,2017,2018,2019 --test-year 2025
"""
from __future__ import annotations
import argparse
import json
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from avia_forecast.ingest import oag_peak
from avia_forecast.capacity import peakhour as ph


def _class_of(annual_pax_m: float) -> str:
    for label, lo, hi in ph.SIZE_CLASSES:
        if lo <= annual_pax_m < hi:
            return label
    return ph.SIZE_CLASSES[-1][0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=None)
    ap.add_argument("--fit-years", default="2015,2016,2017,2018,2019")
    ap.add_argument("--test-year", type=int, default=2025)
    ap.add_argument("--base-year", type=int, default=None,
                    help="year to project FROM; defaults to the last fit year")
    ap.add_argument("--min-coverage", type=float, default=0.90)
    ap.add_argument("--out", default="data/peak_share_backtest.json")
    args = ap.parse_args()

    fit_years = [int(y) for y in args.fit_years.split(",")]
    base_year = args.base_year or max(fit_years)

    print(f"fitting on {fit_years}, projecting from {base_year}, testing on {args.test_year}")
    print("2025 is not in the fit and has never been seen by any of these parameters.")
    print()

    fit_obs, fit_rep = oag_peak.build_panel(args.store, years=fit_years,
                                            min_hours_covered=args.min_coverage)
    capped = ph.flag_capped_from_panel(fit_obs)
    fit_obs = [o for o in fit_obs if o.iata not in capped]
    print(f"fit panel: {fit_rep.rows:,} airport-years, {fit_rep.airports:,} airports, "
          f"{len(capped):,} capped airports excluded")

    test_obs, test_rep = oag_peak.build_panel(args.store, years=[args.test_year],
                                              min_hours_covered=args.min_coverage)
    print(f"test panel: {test_rep.rows:,} airports in {args.test_year}")

    single = ph.fit_peak_share(fit_obs)
    classes = ph.fit_by_size_class(fit_obs)
    curve = ph.fit_curved(fit_obs)
    print(f"single b {single.b:.3f}; curve usable: {curve.fitted_ok}")
    print()

    base = {o.iata: o for o in fit_obs if o.year == base_year}
    test = {o.iata: o for o in test_obs if o.year == args.test_year}
    both = sorted(set(base) & set(test))
    if not both:
        print("no airports present in both panels; nothing to score")
        return
    print(f"{len(both):,} airports present in both {base_year} and {args.test_year}")
    print()

    def predict(b_elasticity, o0, o1):
        """Project the share on a given elasticity, using ACTUAL traffic growth."""
        ratio = o1.annual_pax_m / o0.annual_pax_m
        return o0.share * ratio ** (b_elasticity - 1.0)

    rows, errs = [], {k: [] for k in ("flat", "single", "class", "curve")}
    by_class_errs: dict = {}
    for iata in both:
        o0, o1 = base[iata], test[iata]
        if o0.share <= 0 or o1.share <= 0 or o0.annual_pax_m <= 0:
            continue
        cls = _class_of(o1.annual_pax_m)
        cls_b = classes[cls].b if cls in classes else single.b
        preds = {
            "flat": o0.share,
            "single": predict(single.b, o0, o1),
            "class": predict(cls_b, o0, o1),
            "curve": (predict(curve.elasticity_at(o1.annual_pax_m), o0, o1)
                      if curve.fitted_ok else float("nan")),
        }
        row = {"iata": iata, "class": cls, "annual_pax_m": round(o1.annual_pax_m, 2),
               "actual_share": o1.share, "traffic_ratio": round(o1.annual_pax_m / o0.annual_pax_m, 4)}
        for k, p in preds.items():
            if p == p and p > 0:
                e = abs(p - o1.share) / o1.share
                errs[k].append(e)
                by_class_errs.setdefault(cls, {}).setdefault(k, []).append(e)
                row[k] = round(p, 8)
                row[k + "_err"] = round(e, 4)
        rows.append(row)

    def score(name, e):
        if not e:
            return f"  {name:>7}: no observations"
        med = statistics.median(e)
        w10 = sum(1 for x in e if x <= 0.10) / len(e)
        w20 = sum(1 for x in e if x <= 0.20) / len(e)
        return (f"  {name:>7}: median error {med:6.1%}   within 10% {w10:5.1%}   "
                f"within 20% {w20:5.1%}   n {len(e):,}")

    print(f"Projecting the peak hour share from {base_year} to {args.test_year}, all airports")
    print("Lower median error is better. 'flat' is the old convention and the thing to beat.")
    for k in ("flat", "single", "class", "curve"):
        print(score(k, errs[k]))

    print()
    print("By size class in the test year:")
    for label, _, _ in ph.SIZE_CLASSES:
        if label in by_class_errs:
            print(f"  {label}:")
            for k in ("flat", "single", "class", "curve"):
                if by_class_errs[label].get(k):
                    print("  " + score(k, by_class_errs[label][k]))

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"fit_years": fit_years, "base_year": base_year,
                   "test_year": args.test_year, "n_airports": len(rows),
                   "single_b": single.b, "curve_ok": curve.fitted_ok,
                   "summary": {k: {"median": statistics.median(v) if v else None,
                                   "within_10pc": (sum(1 for x in v if x <= 0.10) / len(v)) if v else None,
                                   "n": len(v)} for k, v in errs.items()},
                   "rows": rows}, fh, indent=1)
    print()
    print(f"written to {args.out}")
    print()
    print("Read it this way. If 'flat' wins, the whole size-varying apparatus is not earning")
    print("its keep across a shock and should be dropped. If the methods are within a point")
    print("or two of each other, prefer the simplest that beats flat. Only a clear margin")
    print("justifies the curve, because it is the hardest to explain to a reviewer.")


if __name__ == "__main__":
    main()

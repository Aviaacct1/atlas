"""Build the peak hour panel from the OAG store and fit the share relationship
(Capacity Method and Evidence Record v0.4, section 11.1). Author: Avia Solutions.

Run this on whichever machine holds the store. The store is data and never lives
in the repo, so its location comes from --store, AVIA_OAG_STORE or sources.yaml.

    # 1. confirm the schema before trusting anything
    python scripts/build_peak_panel.py --store "D:/Avia/OAG.duckdb" --describe

    # 2. build the panel and fit
    python scripts/build_peak_panel.py --store "D:/Avia/OAG.duckdb" \
        --out data/peak_panel.json --fit-out data/peak_share_fit.json

Nothing is written back to the store. The panel and the fit are outputs, and the
fit carries its own diagnostics so a thin or perverse fit is visible rather than
silently used.
"""
from __future__ import annotations
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from avia_forecast.ingest import oag_peak
from avia_forecast.capacity import peakhour as ph


def _codes(arg):
    """A comma-separated list, or a file of codes one per line."""
    if not arg:
        return set()
    p = Path(arg)
    raw = p.read_text(encoding="utf-8").split() if p.exists() else arg.split(",")
    return {c.strip().upper() for c in raw if c.strip()}


def _busiest(store, n):
    import duckdb
    from avia_forecast.ingest import oag_peak as _op
    con = duckdb.connect(str(_op.store_path(store)), read_only=True)
    try:
        con.execute("SET enable_progress_bar=false")
        yr = con.execute("SELECT MAX(CAST(year AS INTEGER)) FROM oag WHERE length(week)=7").fetchone()[0]
        rows = con.execute("SELECT dep_airport, COUNT(*) AS c FROM oag WHERE CAST(year AS INTEGER) = ? "
                           "GROUP BY 1 ORDER BY c DESC LIMIT ?", [yr, n]).fetchall()
        return {r[0] for r in rows if r[0]}
    finally:
        con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=None, help="path to OAG.duckdb (else AVIA_OAG_STORE or sources.yaml)")
    ap.add_argument("--describe", action="store_true", help="report the tables and columns present, then stop")
    ap.add_argument("--out", default="data/peak_panel.json")
    ap.add_argument("--fit-out", default="data/peak_share_fit.json")
    ap.add_argument("--nth", type=int, default=None, help="busy-hour rank; defaults to the book convention")
    ap.add_argument("--airports", default=None,
                    help="comma-separated IATA codes, or a file of them one per line. "
                         "Omit for every airport, which is a long run on the full store.")
    ap.add_argument("--top", type=int, default=None,
                    help="restrict to the N busiest departure airports in the latest full year")
    ap.add_argument("--years", default=None, help="comma-separated years, e.g. 2015,2016,2017,2018,2019")
    ap.add_argument("--min-coverage", type=float, default=0.90,
                    help="drop an airport-year below this share of days present")
    ap.add_argument("--constrained", default=None,
                    help="comma-separated IATA codes whose peak is set by a declared parameter, "
                         "or a file of them one per line. These are flagged and then excluded "
                         "from the estimation sample, because their filed peak reports the "
                         "declaration and not demand.")
    ap.add_argument("--screen-out", default="data/capacity_screen.csv",
                    help="where to write the capacity screen: every airport in the panel "
                         "classified at_ceiling, tightening or headroom, from its own "
                         "filed schedules and with no declared rate needed")
    ap.add_argument("--auto-capped", action="store_true",
                    help="read the peak-capped airports out of the panel itself (peak growth "
                         "far below annual growth) and exclude them from the fit. A starting "
                         "filter until the register carries declared rates.")
    args = ap.parse_args()

    if args.describe:
        info = oag_peak.describe_store(args.store)
        print(f"store: {info['store']}")
        print(f"tables: {', '.join(info['tables'])}")
        for t, cols in info["columns"].items():
            print(f"  {t}: {', '.join(cols)}")
        print(f"configured table resolves: {info['table_resolved']}")
        if info["missing_columns"]:
            print("MISSING, correct sources.yaml oag_schedules.columns:")
            for miss in info["missing_columns"]:
                print(f"  {miss}")
        return

    constrained = _codes(args.constrained)
    airports = _codes(args.airports) or None
    years = [int(y) for y in args.years.split(",")] if args.years else None
    if args.top and not airports:
        airports = _busiest(args.store, args.top)
        print(f"restricted to the {len(airports)} busiest departure airports")

    if args.auto_capped and not constrained:
        first, _ = oag_peak.build_panel(args.store, nth=args.nth,
                                        min_hours_covered=args.min_coverage,
                                        airports=sorted(airports) if airports else None,
                                        years=years)
        constrained = ph.flag_capped_from_panel(first)
        print(f"read as peak-capped from the panel and excluded from the fit "
              f"({len(constrained)}): {', '.join(sorted(constrained))}")

    obs, report = oag_peak.build_panel(args.store, nth=args.nth,
                                       min_hours_covered=args.min_coverage,
                                       constrained=constrained,
                                       airports=sorted(airports) if airports else None,
                                       years=years)

    print(f"basis: {report.notes}")
    print(f"panel: {report.rows:,} airport-years, {report.airports:,} airports, "
          f"{min(report.years) if report.years else '-'} to {max(report.years) if report.years else '-'}, "
          f"convention {report.convention}")
    if report.dropped_incomplete:
        print(f"dropped for incomplete coverage: {len(report.dropped_incomplete)} airport-years "
              f"(first few: {report.dropped_incomplete[:5]})")
    if constrained:
        print(f"flagged constrained and excluded from the fit: {len(constrained)} airports")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump([asdict(o) for o in obs], fh, indent=1)
    print(f"panel written to {args.out}")

    # The screen. This is the part that has to cover EVERY airport rather than the
    # largest few hundred: a constrained secondary airport spills traffic the engine
    # would otherwise let through, and the airports with headroom are where that spill
    # has to go, so the catchment redistribution needs both halves.
    screen = ph.capacity_screen(obs)
    if args.screen_out:
        import csv as _csv
        Path(args.screen_out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.screen_out, "w", encoding="utf-8", newline="") as fh:
            w = _csv.writer(fh)
            w.writerow(["iata", "first_year", "last_year", "annual_mvts", "peak_hour_mvts",
                        "annual_growth", "peak_growth", "absorption", "peak_hour_share",
                        "state", "note"])
            for r in screen:
                w.writerow([r.iata, r.first_year, r.last_year, round(r.annual_mvts),
                            round(r.peak_hour_mvts, 1), round(r.annual_growth, 4),
                            round(r.peak_growth, 4), round(r.absorption, 3),
                            round(r.share, 6), r.state, r.note])
        counts = {}
        for r in screen:
            counts[r.state] = counts.get(r.state, 0) + 1
        print()
        print("capacity screen: " + ", ".join(f"{v:,} {k}" for k, v in sorted(counts.items())))
        tight = sorted((r for r in screen if r.state in ("at_ceiling", "tightening")),
                       key=lambda r: -r.annual_mvts)[:25]
        if tight:
            print("busiest airports at or approaching their ceiling:")
            for r in tight:
                import math as _m
                a = f"{r.absorption:>5.2f}" if _m.isfinite(r.absorption) else "   na"
                print(f"  {r.iata}  {r.annual_mvts:>8,.0f} ATM/yr  peak {r.peak_hour_mvts:>5.1f}/hr  "
                      f"annual {r.annual_growth:>+6.1%}  peak {r.peak_growth:>+6.1%}  "
                      f"absorption {a}  {r.state}")
        print(f"screen written to {args.screen_out}")
        print()

    fit = ph.fit_peak_share(obs)
    with open(args.fit_out, "w", encoding="utf-8") as fh:
        json.dump(asdict(fit), fh, indent=1)
    print()
    print(ph.describe(fit))
    print()
    print("Elasticity by size class. A single line across the whole range belongs to no")
    print("part of it; for capacity work read the classes where constraints actually bite.")
    classes = ph.fit_by_size_class(obs)
    for label, f in classes.items():
        flag = "   BOOK FALLBACK, not estimated" if f.fallback_used else ""
        r2 = f"{f.r2:.3f}" if f.r2 == f.r2 else "  na"
        se = f"+/-{f.se_b:.3f}" if f.se_b == f.se_b else "     na"
        print(f"  {label:>14}:  b {f.b:.3f} {se}   share elasticity {f.share_elasticity:+.3f}   "
              f"r2 {r2}   {f.n_obs:>5,} airport-years, {f.n_airports:>4,} airports{flag}")

    # Adjacent classes were not separable while the ends of the range emphatically were,
    # which is a continuous relationship forced through arbitrary boundaries. The curved
    # fit removes the boundaries.
    import math as _mm
    labels = list(classes)
    if len(labels) > 1:
        print()
        print("Are adjacent classes actually different?")
        for l1, l2 in zip(labels, labels[1:]):
            f1, f2 = classes[l1], classes[l2]
            if f1.se_b == f1.se_b and f2.se_b == f2.se_b:
                se = _mm.sqrt(f1.se_b ** 2 + f2.se_b ** 2)
                t = (f2.b - f1.b) / se if se else float("nan")
                verdict = "different" if abs(t) > 2 else "NOT separable"
                print(f"  {l1:>14} vs {l2:<14} diff {f2.b - f1.b:+.3f}  t {t:+5.2f}  {verdict}")

    cf = ph.fit_curved(obs)
    print()
    if cf.fitted_ok:
        print("Curved fit: elasticity varies smoothly with size, no class boundaries.")
        print(f"  curvature term {cf.b2:+.5f} +/-{cf.se_b2:.5f}, r2 {cf.r2:.3f}, "
              f"{cf.n_obs:,} airport-years")
        print("  elasticity at:  " + "   ".join(
            f"{m:g}m {cf.elasticity_at(m):.3f}" for m in (0.5, 2, 10, 25, 60)))
    else:
        print(f"Curved fit not used: {cf.notes}")
    if not fit.fitted_ok:
        print("FIT NOT USABLE: the book fallback elasticity is in force. Do not treat the "
              "level as estimated.")
    print(f"fit written to {args.fit_out}")


if __name__ == "__main__":
    main()

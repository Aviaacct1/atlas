"""backtest_horizon - the engine's own forward test at scale, scored BY HORIZON YEAR.

Fit at a base year; forecast every airport forward with the BLENDED path (filed-schedule
anchor tapering to the propensity-damped econometric path - the C2 design); score each
horizon year against ACI actuals; compare against pure seats, pure econometrics and the
naive GDP multiple. This is the error-band exhibit in embryo: error should be lowest at
t+1..t+3 (schedule visibility) and rise as econometrics take over.

DISCIPLINE: 2015-2019 is the DEVELOPMENT window - tune spans/weights here freely.
2023-2025 is reserved as the blind hold-out; do not tune after seeing its results.

  py -3.12 scripts\\backtest_horizon.py                    # base 2015, score 2016-2019
  py -3.12 scripts\\backtest_horizon.py --base 2019        # blind hold-out (when 2023-25 land)
  py -3.12 scripts\\backtest_horizon.py --span 4           # tune the anchor taper
Author: Avia Solutions.
"""
from __future__ import annotations
import argparse, json, os, sys

import duckdb

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from avia_forecast.io_safe import dump_atomic
from avia_forecast.paths import DATA
from avia_forecast.backtest import scaffold
from avia_forecast.demand import capacity_anchor as ca
from backtest_seats_anchor import DB_CANDIDATES, seats_by_basis, load_actuals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=int, default=2015)
    ap.add_argument("--last", type=int, default=None, help="last horizon year (default base+4)")
    ap.add_argument("--span", type=int, default=5, help="anchor taper span (house transition)")
    args = ap.parse_args()
    base, last = args.base, (args.last or args.base + 4)

    db = next(p for p in DB_CANDIDATES if p and os.path.exists(p))
    con = duckdb.connect(db, read_only=True)
    seats = seats_by_basis(con)["annual"]
    pax, ctry = load_actuals()
    gfp = next(p for p in (os.path.join(DATA, "oef_gdp_pop_by_iso2.json"),
                           os.path.join(REPO, "data", "oef_gdp_pop_by_iso2.json")) if os.path.exists(p))
    oef = json.load(open(gfp))
    gdp, pop = oef["gdp"], oef["pop"]
    from avia_forecast.geo.regions_iso2 import region_for_iso2

    horizon_err = {m: {h: [0.0, 0.0] for h in range(1, last - base + 1)}
                   for m in ("blend", "seats", "econ", "naive")}
    blend_apes = {h: [] for h in range(1, last - base + 1)}
    n_scored, thin = 0, 0
    for iata, sy in seats.items():
        if base not in sy or iata not in pax or base not in pax[iata] or pax[iata][base] <= 0:
            continue
        c = ctry.get(iata, "")
        g, p = gdp.get(c, {}), pop.get(c, {})
        if not all(g.get(str(y)) and p.get(str(y)) for y in range(base, last + 1)):
            continue
        region = region_for_iso2(c) or "default"
        base_pax = pax[iata][base]
        try:
            econ = scaffold.econometric_path(base_pax, base, g, p, region, last)
        except Exception:
            continue
        blend_path, was_thin = ca.blend(base_pax, sy, base, econ, span=args.span)
        thin += bool(was_thin)
        ok = False
        for y in range(base + 1, last + 1):
            a = pax.get(iata, {}).get(y)
            if not a or a <= 0:
                continue
            h = y - base
            preds = {"blend": blend_path.get(y), "econ": econ.get(y),
                     "seats": (base_pax * sy[y] / sy[base]) if sy.get(y) else None,
                     "naive": base_pax * float(g[str(y)]) / float(g[str(base)])}
            for m, f in preds.items():
                if f is not None:
                    horizon_err[m][h][0] += abs(f - a)
                    horizon_err[m][h][1] += a
            if preds["blend"] is not None:
                blend_apes[h].append(abs(preds["blend"] - a) / a)
            ok = True
        n_scored += ok
    con.close()

    exhibit = {"base": base, "last": last, "span": args.span, "n_airports": n_scored,
               "thin_schedule_airports": thin, "wmape_by_horizon": {}}
    print(f"base {base}, span {args.span}, {n_scored} airports "
          f"({thin} thin-schedule fallbacks)")
    print(f"{'h':>3} {'blend':>8} {'seats':>8} {'econ':>8} {'naive':>8}")
    for h in range(1, last - base + 1):
        row = {}
        for m in ("blend", "seats", "econ", "naive"):
            e, a = horizon_err[m][h]
            row[m] = round(e / a, 4) if a else None
        ap = blend_apes[h]
        row["blend_within_20pct"] = round(sum(1 for e in ap if e <= 0.20) / len(ap), 4) if ap else None
        exhibit["wmape_by_horizon"][f"t+{h}"] = row
        w20 = f"{row['blend_within_20pct']*100:5.0f}%" if row["blend_within_20pct"] is not None else "  n/a"
        print(f"t+{h} " + " ".join(f"{(row[m]*100 if row[m] is not None else float('nan')):7.1f}%"
                                   for m in ("blend", "seats", "econ", "naive")) +
              f"   | blend within +-20%: {w20}")
    out = os.path.join(REPO, "data", f"backtest_horizon_{base}_{args.span}.json")
    dump_atomic(exhibit, out, indent=1)
    print("exhibit ->", out)


if __name__ == "__main__":
    main()

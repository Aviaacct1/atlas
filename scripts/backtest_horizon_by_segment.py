"""backtest_horizon_by_segment - the frozen span-5 blend (backtest_horizon.py), broken
down by world region and airport size-class, to find WHERE t+3/t+4 accuracy fails
rather than chase the span parameter further (span is frozen at 5; span 6 only wins
via hindsight and is not adopted - see CHANGELOG). Author: Avia Solutions.

Reuses backtest_horizon's own per-airport blend computation unchanged; adds two tags
per airport (region, size-class by base-year ACI pax) and reports blend within-+-20%
by horizon for each segment. Base year and span are fixed at the settled values
(2015, span 5) so this is a diagnostic on the existing frozen run, not a new tune.

  py -3.12 scripts\\backtest_horizon_by_segment.py
"""
from __future__ import annotations
import json, os, sys

import duckdb

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from avia_forecast.io_safe import dump_atomic
from avia_forecast.paths import DATA
from avia_forecast.backtest import scaffold
from avia_forecast.demand import capacity_anchor as ca
from avia_forecast.geo.regions_iso2 import region_for_iso2
from backtest_seats_anchor import DB_CANDIDATES, seats_by_basis, load_actuals

BASE, LAST, SPAN = 2015, 2019, 5   # settled values - see CHANGELOG, do not vary here

SIZE_BINS = [
    (0, 1_000_000, "<1mppa"),
    (1_000_000, 5_000_000, "1-5mppa"),
    (5_000_000, 15_000_000, "5-15mppa"),
    (15_000_000, 40_000_000, "15-40mppa"),
    (40_000_000, float("inf"), "40mppa+"),
]


def size_class(base_pax: float) -> str:
    for lo, hi, label in SIZE_BINS:
        if lo <= base_pax < hi:
            return label
    return "unclassified"


def main():
    db = next(p for p in DB_CANDIDATES if p and os.path.exists(p))
    con = duckdb.connect(db, read_only=True)
    seats = seats_by_basis(con)["annual"]
    pax, ctry = load_actuals()
    gfp = next(p for p in (os.path.join(DATA, "oef_gdp_pop_by_iso2.json"),
                           os.path.join(REPO, "data", "oef_gdp_pop_by_iso2.json")) if os.path.exists(p))
    oef = json.load(open(gfp))
    gdp, pop = oef["gdp"], oef["pop"]

    # {segment_type: {segment_label: {h: [n_within20, n_total]}}}
    seg = {"region": {}, "size_class": {}}
    n_scored, thin = 0, 0
    for iata, sy in seats.items():
        if BASE not in sy or iata not in pax or BASE not in pax[iata] or pax[iata][BASE] <= 0:
            continue
        c = ctry.get(iata, "")
        g, p = gdp.get(c, {}), pop.get(c, {})
        if not all(g.get(str(y)) and p.get(str(y)) for y in range(BASE, LAST + 1)):
            continue
        region = region_for_iso2(c) or "Unmapped"
        base_pax = pax[iata][BASE]
        sc = size_class(base_pax)
        try:
            econ = scaffold.econometric_path(base_pax, BASE, g, p, region_for_iso2(c) or "default", LAST)
        except Exception:
            continue
        blend_path, was_thin = ca.blend(base_pax, sy, BASE, econ, span=SPAN)
        thin += bool(was_thin)
        ok = False
        for y in range(BASE + 1, LAST + 1):
            a = pax.get(iata, {}).get(y)
            if not a or a <= 0:
                continue
            h = y - BASE
            f = blend_path.get(y)
            if f is None:
                continue
            within20 = abs(f - a) / a <= 0.20
            for seg_type, label in (("region", region), ("size_class", sc)):
                d = seg[seg_type].setdefault(label, {})
                cnt = d.setdefault(h, [0, 0])
                cnt[0] += int(within20)
                cnt[1] += 1
            ok = True
        n_scored += ok
    con.close()

    exhibit = {"base": BASE, "last": LAST, "span": SPAN, "n_airports": n_scored,
               "thin_schedule_airports": thin, "by_region": {}, "by_size_class": {}}
    for seg_type, out_key in (("region", "by_region"), ("size_class", "by_size_class")):
        print(f"\n=== within +-20%, by {seg_type} (base {BASE}, span {SPAN}) ===")
        for label, hs in sorted(seg[seg_type].items()):
            row = {}
            line = f"  {label:<14}"
            for h in sorted(hs):
                w, n = hs[h]
                pct = w / n if n else None
                row[f"t+{h}"] = {"within_20pct": round(pct, 4) if pct is not None else None, "n": n}
                line += f"  t+{h} {pct*100:4.0f}% (n={n:>4})" if pct is not None else f"  t+{h}   n/a"
            exhibit[out_key][label] = row
            print(line)

    out = os.path.join(REPO, "data", f"backtest_horizon_segments_{BASE}_{SPAN}.json")
    dump_atomic(exhibit, out, indent=1)
    print("\nexhibit ->", out)


if __name__ == "__main__":
    main()

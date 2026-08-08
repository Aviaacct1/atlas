"""Score our peak hour panel against Jess Rowden's hand-built benchmark set.

This is the closest thing to an independent audit the peak hour work has. Her set is one
workbook per airport built straight from dated OAG rows, with no reference to our engine,
so agreement is evidence and disagreement is a lead.

It compares BOTH conventions separately, which is the whole point. On 4 August 2026 a
day was lost to comparing our 30th busiest hour against her absolute peak and concluding
that our method had a defect. It has not. Compare like with like or do not compare.

    python scripts/extract_peakhour_outputs.py --folder "<Egnyte>/02 Peak Hour/Benchmarks"
    python scripts/compare_peakhour_benchmark.py

Author: Avia Solutions.
"""
from __future__ import annotations
import argparse, csv, statistics as st
from pathlib import Path

PAIRS = [
    ("annual_mvt_2way",    "a_m2", "annual movements"),
    ("annual_seats_2way",  "a_s2", "annual seats"),
    ("peak_mvt_2way",      "p_m2", "PEAK hour movements"),
    ("peak_seats_2way",    "p_s2", "PEAK hour seats"),
    ("busy30_mvt_2way",    "p_m2", "30th busiest movements"),
    ("busy30_seats_2way",  "p_s2", "30th busiest seats"),
]


def load(p):
    return {r["iata"]: r for r in csv.DictReader(open(p, encoding="utf-8"))} if Path(p).exists() else {}


def num(v):
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def score(bench, ours, keys, label):
    print(f"\n--- our {label}")
    for bkey, okey, name in keys:
        d = []
        for a, b in bench.items():
            x, y = num(b.get(bkey)), num((ours.get(a) or {}).get(okey))
            if x and y:
                d.append((y - x) / x)
        if not d:
            continue
        print(f"   {name:26} n={len(d):>3}  median bias {st.median(d)*100:+6.1f}%"
              f"   median |diff| {st.median(abs(x) for x in d)*100:5.1f}%"
              f"   within 5% {sum(1 for x in d if abs(x) < .05)/len(d)*100:3.0f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", default="data/peakhour_benchmark_outputs.csv")
    ap.add_argument("--peak", default="data/peak_panel_2025_absolute_peak.csv")
    ap.add_argument("--busy30", default="data/peak_panel_2025_busy30.csv")
    a = ap.parse_args()

    bench = load(a.benchmark)
    if not bench:
        print(f"no benchmark at {a.benchmark}; run extract_peakhour_outputs.py first")
        return 2
    print(f"benchmark airports: {len(bench)}")

    score(bench, load(a.peak), [p for p in PAIRS if p[0].startswith(("annual", "peak"))],
          "ABSOLUTE PEAK panel against her row 7")
    score(bench, load(a.busy30), [p for p in PAIRS if p[0].startswith("busy30")],
          "30th BUSIEST panel against her row 12")

    # her own two conventions, side by side: the number nobody had until now
    gaps = [num(b["peak_seats_2way"]) / num(b["busy30_seats_2way"]) - 1
            for b in bench.values()
            if num(b.get("peak_seats_2way")) and num(b.get("busy30_seats_2way"))]
    if gaps:
        gaps.sort()
        print(f"\nIn her own data, the peak hour runs {st.median(gaps)*100:.0f}% above the "
              f"30th busiest at the median (range {gaps[0]*100:.0f}% to {gaps[-1]*100:.0f}%), "
              f"n={len(gaps)}.")
        print("Anything sized on the peak while being described as a 30th busy hour is high "
              "by that much.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

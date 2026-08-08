#!/usr/bin/env python3
"""Avia Solutions - per-airport track-record chart, same basis and style as the
headline calibrated distribution. Presentation rule (empirical, 5 Aug 2026):
  n>=30   quote the airport's own calibrated within-+-20% figure
  10-29   quote it with n stated plainly
  <10     no percentage - show the airport's launches on the engine's curve
Usage: python3 bt2_airport_chart.py LHR [outdir]
"""
import csv, json, sys, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BT2 = os.environ.get("BT2_DIR", os.path.dirname(os.path.abspath(__file__)))

def build(airport, outdir):
    d = json.load(open(f"{BT2}/fitted_dist.json"))
    allerr = np.array(d["err"]) * 100
    mine = []
    with open(f"{BT2}/route_fitted_errors.csv") as f:
        for r in csv.DictReader(f):
            if airport in (r["a"], r["b"]):
                mine.append((float(r["fitted_err"]) * 100, r["a"], r["b"], r["cohort"]))
    n = len(mine)
    es = np.array([m[0] for m in mine])
    w20 = 100 * np.mean(np.abs(es) <= 20) if n else 0
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=200)
    bins = np.arange(-55, 60, 5)
    ax.axvspan(-20, 20, color="#1f5f8b", alpha=0.08, zorder=0)
    ax.hist(np.clip(allerr, -55, 55), bins=bins, color="#d3dde4", edgecolor="white",
            zorder=1, label="All 2,915 launches")
    if n:
        # each launch a dot, stacked per 5%-bin so every route is visible and countable
        top = ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else 1200
        ce = np.clip(es, -54.9, 54.9)
        idx = np.digitize(ce, bins)
        stacks = {}
        xs, ys = [], []
        for e, i in zip(ce, idx):
            k = stacks.get(i, 0); stacks[i] = k + 1
            xs.append(bins[i-1] + 2.5); ys.append(top * 0.035 * (k + 1))
        ax.scatter(xs, ys, s=42, color="#1f5f8b", edgecolor="white", linewidth=0.6,
                   zorder=3, label=f"{airport} launches (n={n}), one dot per route")
    ax.axvline(-20, color="#1f5f8b", lw=1.2, ls="--"); ax.axvline(20, color="#1f5f8b", lw=1.2, ls="--")
    if n >= 30:
        head = f"{airport}: {w20:.0f}% of {n} launches within ±20%"
    elif n >= 10:
        head = f"{airport}: {int(np.sum(np.abs(es) <= 20))} of {n} launches within ±20%"
    else:
        head = f"{airport}: {n} launches in the test, shown against the engine's calibration (90% within ±20% overall)"
    ax.set_title(f"Calibrated model versus actual first-year traffic - {airport}\n{head}",
                 fontsize=12, loc="left")
    ax.set_xlabel("Forecast error vs actual first-year passengers (%), calibrated (fitted) model; tails beyond ±55% grouped in end bars")
    ax.set_ylabel("Number of routes")
    ax.legend(frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(0.0, -0.22, "Source: AviaSolutions Analysis - BT2 backtest, 2,915 route launches 2016-2019 and 2025, OAG schedules and Sabre MIDT",
            transform=ax.transAxes, fontsize=8, color="#555555")
    plt.tight_layout()
    out = f"{outdir}/QSI_track_record_{airport}.png"
    plt.savefig(out, bbox_inches="tight"); print("saved", out)

if __name__ == "__main__":
    ap = sys.argv[1].upper()
    outdir = sys.argv[2] if len(sys.argv) > 2 else BT2
    build(ap, outdir)

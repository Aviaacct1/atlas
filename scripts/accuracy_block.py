"""Accuracy card content, generated from the archived backtest exhibits.

The dashboard's accuracy statement was three rows typed into dashboard.html under the
caption "refreshed every vintage", and nothing wrote them, so they could not refresh
(independent review, 16 August 2026). This module is the single producer: it reads the
exhibit files and returns the block build_dashboard_data.py ships inside dashboard.json.
The page renders what this returns and holds no accuracy literal of its own;
tests/test_accuracy_card.py asserts both ends.

Basis discipline, from the Meridian control-arm pattern (note of 16 August 2026): every
figure names its basis on the surface it appears on, and a schedule-anchored test and a
demand-model backtest may not borrow each other's numbers. The seats exhibit validates
the published-schedule anchor; the Method Spec 9 exhibits are the demand model against
outturn, naive control beside it, shown including the window it loses.

Author: Avia Solutions.
"""
from __future__ import annotations
import datetime
import json
import os


def _pc(v) -> str:
    return f"{v * 100:.1f}%"


def _stamp(fp: str) -> str:
    d = datetime.date.fromtimestamp(os.path.getmtime(fp))
    return f"{os.path.basename(fp)} ({d.day} {d.strftime('%B %Y')})"


def build_accuracy(data_dir: str):
    """Returns the accuracy block for dashboard.json, or None with a printed reason
    when an exhibit is absent. Flag rather than fill: no exhibit, no card."""
    seats_fp = os.path.join(data_dir, "backtest_seats_exhibit.json")
    scale_fp = os.path.join(data_dir, "backtest_exhibit.json")
    full_fp = os.path.join(data_dir, "backtest_full_engine_exhibit.json")
    for fp in (seats_fp, scale_fp, full_fp):
        if not os.path.isfile(fp):
            print(f"accuracy block NOT built: {os.path.basename(fp)} is absent. The card "
                  f"will say so rather than show a typed figure.")
            return None

    seats = json.load(open(seats_fp))["summary"]
    scale = json.load(open(scale_fp))
    full = json.load(open(full_fp))

    seats_rows = []
    for key, label in (("annual 2023->2024", "1 year (2023 to 2024)"),
                       ("annual 2015->2019", "4 years, pre-pandemic (2015 to 2019)"),
                       ("annual 2019->2024", "5 years, through the pandemic (2019 to 2024)")):
        s = seats.get(key)
        if s:
            seats_rows.append([label, f"{s['n']:,} airports", _pc(s["wmape_seats"]),
                               _pc(s["within_20pct"]), _pc(s["within_10pct"])])

    def _engine_rows(ex, unit):
        rows = []
        base = ex.get("base_year", 2014)
        for y in sorted(ex.get("summary", {})):
            s = ex["summary"][y]
            rows.append([f"{base} to {y}", f"{s['n']:,} {unit}", _pc(s["wmape_model"]),
                         _pc(s["wmape_naive"]), "yes" if s.get("beats_naive_wmape") else "no"])
        return rows

    return {
        "seats_anchor": {
            "title": "Schedule anchor validation (seats-driven)",
            "rows": seats_rows,
            "basis": ("Basis: base-year passengers grown by the outturn schedule seat ratio "
                      "(scripts/backtest_seats_anchor.py), scored against ACI actuals; WMAPE is "
                      "traffic-weighted. This validates the published-schedule anchor the product "
                      "uses for its near year. Beyond one year the outturn schedule would not have "
                      "been knowable at forecast time, so the multi-year rows are anchor "
                      "validation, not forecast accuracy, and are labelled here so the two claims "
                      "cannot be read as one."),
        },
        "engine": {
            "title": "Demand model backtest, Method Spec 9",
            "rows": _engine_rows(scale, "airports") + _engine_rows(full, "countries"),
            "basis": ("Basis: the demand model run forward from its base year on the GDP driver "
                      "and scored against ACI outturn (scripts/backtest_at_scale.py at airport "
                      "scale, scripts/backtest_full_engine.py at country scale). The naive column "
                      "is a fixed 1.5x traffic multiplier as the control arm. The model beats the "
                      "naive control on the windows through the pandemic and does not on the "
                      "pre-pandemic windows; both are shown, because a track record that omits "
                      "the windows it loses is not a track record."),
        },
        "provenance": ("Generated at build time from " + ", ".join(
            _stamp(fp) for fp in (seats_fp, scale_fp, full_fp)) +
            "; produced by scripts/accuracy_block.py, never typed into the page."),
    }

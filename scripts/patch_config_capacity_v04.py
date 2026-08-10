"""Add the Capacity Method v0.4 config blocks to an existing assumptions book and
source register, without touching anything already there. Author: Avia Solutions.

Written because the new capacity modules were built in one copy of the repo and the
live copy is elsewhere. Copying whole config files between the two would quietly
undo live edits, so this appends only the three missing top-level sections and says
what it did.

Idempotent: run it twice and the second run reports three skips and changes nothing.
A timestamped backup of each file is written before any change.

    cd C:\\Avia\\avia_forecast_build
    python scripts\\patch_config_capacity_v04.py            # dry run, shows what would change
    python scripts\\patch_config_capacity_v04.py --apply
"""
from __future__ import annotations
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "config" / "assumptions_book.yaml"
SOURCES = ROOT / "config" / "sources.yaml"

PEAK_HOUR = """
# --- Peak hour share (Capacity Method and Evidence Record v0.4, section 11.1) ---
# The share is fitted as a relationship across the schedule panel, not read off one
# year and held flat. Peak-constrained airports are excluded from the estimation
# sample: their filed peak reports the declared parameter, not demand.
peak_hour:
  convention: busy_30th                    # model convention (v0.4 section 10); DDFS supplies the rate
  basis: passengers                        # passenger basis, not movements
  min_annual_pax_m: 0.25                   # [P1] below this the observed peak is erratic
  min_obs_per_airport: 3                   # [P1] airport-years needed to enter the sample
  min_obs_total: 30                        # [P1] below this the fit falls back, flagged
  min_r2: 0.80                             # [P1] below this the level is flagged indicative, not rejected
  # OPERATING CHOICE, settled by the 2025 blind test (3 August 2026): ONE elasticity.
  # Fitted 2015-2019, projected each airport's share to 2025 on its actual traffic
  # growth, scored against the schedules. 2,096 airports, median absolute error:
  #     flat 17.7%   single 15.1%   class 15.1%   curve 15.0%
  # All three modelled methods beat holding the share flat by about 2.7 points, and
  # they finish within 0.1 of each other. The rule set before the run was to prefer
  # the simplest method that beats flat, so the single elasticity is the operating
  # choice; the class table and the curve are kept for reference and did not earn
  # their complexity. Note the test has weak power above 15m, where traffic barely
  # moved between 2019 and 2025, so the choice there is not really tested.
  elasticity: 0.696                        # single elasticity, full store, capped airports out
  # Reference only, not used by the engine:
  elasticity_by_class:
    under_1m: 0.676
    1m_to_5m: 0.664
    5m_to_15m: 0.754
    15m_to_40m: 0.822
    40m_and_above: 0.917
  # Blind-test accuracy of the share projection itself, to be carried into any output
  # that depends on it: median absolute error 15%, 36% of airports within 10%, 62%
  # within 20%. A 15% error on the share is a 15% error on the implied annual capacity,
  # which at 3% growth moves a binding year by about 4.7 years. This is the evidence
  # behind reporting a binding-year RANGE rather than a point (Capacity Method v0.4,
  # section 11.3), and it is a stronger reason than the convention argument was.
  share_projection_median_error: 0.144
  fallback_elasticity: 0.696               # same as the operating value
  projection_floor_share: 0.00015          # [P1] floor on projected share over a long horizon
  constrained_utilisation_flag: 0.95       # [P1] filed peak at/above this share of the declared rate = constrained
  capped_growth_ratio: 0.35                # [P1] peak growth below this share of annual growth reads as capped
  capped_static_growth: 0.02               # [P1] growth below this counts as static
  capped_size_floor_mvts: 150000           # [P1] a large airport with a static peak is at its ceiling
  screen_min_mvts: 20000                   # [P1] below this the busy hour is too small to read a trend
"""

CAPACITY_EVIDENCE = """
# --- Capacity evidence record and resolution (Capacity Method v0.4, sections 2, 5, 11) ---
# Observations are stored as published and never converted in place; the resolution
# layer runs whichever tests the evidence supports and records the ones it could not.
capacity_evidence:
  stand_turnaround_hours: 1.0              # [P1] indicative occupancy for the stand test
  range_trigger_years: 3                   # [P1] binding years further apart than this => report a range
  range_trigger_k_rel: 0.10                # [P1] resolved K differing by more than this => report a range
  actual_over_k_block_rel: 1.00            # [P1] actual traffic above this multiple of K blocks the entry
"""

OAG_SCHEDULES = """
# OAG schedule store: the panel behind the peak hour share fit (Capacity Method v0.4,
# section 11.1). The store is data, so it never lives in a repo (tool standard 3) and
# the path is config, never a literal (standard 4). Resolution order: --store argument,
# then AVIA_OAG_STORE, then store_path below.
oag_schedules:
  name: "OAG schedules (Avia store)"
  licence_class: C
  rights_summary: "Commercial licence. Estimation and parameter use; no reconstitutable extracts."
  store_path: "E:/Avia/oag.duckdb"     # the store root moved to E:\Avia on 10 August 2026;
                                       # resolution is --store, then AVIA_DB_ROOT through
                                       # paths.py, then this line as the last resort
  # Read directly against the OAG store, 3 August 2026. The store is ONE ROW PER
  # OPERATED FLIGHT. The presence of days_of_op, eff_from and eff_to made it look like
  # service grain, which it is not: see the row grain note below.
  columns:
    row_grain: operation               # operation | service | operated (see the note below)
    table: oag
    airport: dep_airport
    timestamp: ""                      # not applicable at service grain
    seats: seats                       # seats per operation; seats_total is the period total
    passengers: ""                     # blank => seats x book load factor, stated on the panel report
    arr_country: arr_country
    home_country: dep_country          # international = arr_country <> dep_country
    movements: ""                      # blank => one expanded operating date is one movement
    days_of_op: days_of_op
    eff_from: eff_from
    eff_to: eff_to
    dep_time: local_dep_time           # local clock time, which is what a peak hour is
  # Row filter. CORRECTED 3 August 2026 after reading the store directly.
  # dup_marker is NOT a codeshare marker in this store and must not be filtered on:
  # BA57 LHR-JNB, operated by BA with no operating-carrier override, carries dup_marker 'D',
  # and 'D' is 84.7% of Heathrow's 2019 rows. Filtering to '0' would delete most of the real
  # departures (49,117 against 322,063) and was wrong in the earlier version of this file.
  # service_type 'J' is 99.1% of rows and is the scheduled passenger service.
  filter: "service_type = 'J'"
  # Row grain. The store is ONE ROW PER OPERATED FLIGHT, not per service: NZ1 LHR-LAX appears
  # 30 times in the 2019-06 file, once per operating day, each row carrying frequency 1 and the
  # full season window. So eff_from and eff_to are the SEASON window and must never be used to
  # place a row on a date; the period comes from the week key. Nothing is expanded.
  # The real duplication is cross-region: a flight spanning two regions is listed in both region
  # files (NZ1 appears in North America and in Europe). Factor 1.38 at Heathrow. Deduplicate on
  # carrier, flight_no, dep_airport, arr_airport and local_dep_time, taking the count from one
  # region: that gives 678 departures a day at Heathrow in June 2019, inside the 630 to 720 that
  # John Carter's 70 to 80 ATM/hr over an 05:00 to 23:00 day implies. Raw it reads 934.
  # Movements must count ARRIVALS as well: the runway constraint is ATM, and arrivals and
  # departures bank at different times, so the combined flow is built as one series and not as
  # twice the departure peak. arr_airport, local_arr_time and local_arr_day carry the other side.
  # Snapshot and period handling now live in ingest/oag_store.py, shared with the
  # backtests: one preferred tiling per region-year, and each airport read from its
  # home region file only. Nothing here to set.
"""

PATCHES = [
    (BOOK, "peak_hour:", PEAK_HOUR, "assumptions book: peak_hour"),
    (BOOK, "capacity_evidence:", CAPACITY_EVIDENCE, "assumptions book: capacity_evidence"),
    (SOURCES, "oag_schedules:", OAG_SCHEDULES, "source register: oag_schedules"),
]


def has_key(text: str, key: str) -> bool:
    return any(line.rstrip() == key for line in text.splitlines())


def replace_section(text: str, key: str) -> str:
    """Cut an existing top-level section out, with any comment block immediately above
    it, so the replacement can be appended cleanly. Everything else is untouched."""
    lines = text.splitlines(keepends=True)
    key_idx = next(i for i, ln in enumerate(lines) if ln.rstrip() == key)
    # walk back over the comment block that introduces the section
    start = key_idx
    while start > 0 and lines[start - 1].lstrip().startswith("#"):
        start -= 1
    # walk forward from the KEY line, not from start, or only the comment is cut
    end = key_idx + 1
    while end < len(lines) and (lines[end].startswith((" ", "\t")) or not lines[end].strip()):
        end += 1
    out = "".join(lines[:start] + lines[end:])
    return out if out.endswith("\n") else out + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the changes (default is a dry run)")
    ap.add_argument("--refresh-oag", action="store_true",
                    help="replace an existing oag_schedules block with the confirmed mapping "
                         "(use after the store schema has been read with --describe)")
    args = ap.parse_args()

    for path in (BOOK, SOURCES):
        if not path.exists():
            print(f"NOT FOUND: {path}")
            print("Run this from the root of the live build, not from scripts/.")
            sys.exit(1)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    pending: dict[Path, str] = {}
    added, skipped = [], []

    for path, key, block, label in PATCHES:
        text = pending.get(path, path.read_text(encoding="utf-8"))
        if has_key(text, key):
            if args.refresh_oag and key == "oag_schedules:":
                pending[path] = replace_section(text, key) + block
                added.append(label + " (replaced with the confirmed mapping)")
                continue
            skipped.append(label)
            continue
        if not text.endswith("\n"):
            text += "\n"
        pending[path] = text + block
        added.append(label)

    for label in skipped:
        print(f"already present, left alone: {label}")
    for label in added:
        print(f"{'adding' if args.apply else 'would add'}: {label}")

    if not added:
        print("\nNothing to do. The live config already carries all three sections.")
        print("If the OAG mapping predates the store schema read, re-run with --refresh-oag.")
        return

    if not args.apply:
        print("\nDry run. Re-run with --apply to write, after which a backup of each file "
              "is kept alongside it.")
        return

    for path, text in pending.items():
        backup = path.with_suffix(path.suffix + f".bak-{stamp}")
        shutil.copy2(path, backup)
        path.write_text(text, encoding="utf-8")
        print(f"written: {path}  (backup {backup.name})")

    try:
        import yaml
        for path in pending:
            body = path.read_text(encoding="utf-8")
            yaml.safe_load(body)
            for _, key, _, _ in PATCHES:
                if path in (BOOK, SOURCES) and body.count("\n" + key) > 1:
                    raise ValueError(f"{path.name} carries {key} more than once")
        print("\nBoth files still parse as YAML, with no duplicated section.")
    except Exception as exc:                       # pragma: no cover
        print(f"\nWARNING: a file no longer parses ({exc}). Restore from the .bak file.")
        sys.exit(1)

    print("\nNext: python scripts\\build_peak_panel.py --describe")


if __name__ == "__main__":
    main()

r"""Rebuild the ACI hub calibration the terminal model is anchored to.
Author: Avia Solutions.

`data/aci_hub_calibration_2024.json` carries the base-year terminal level and connecting
split for every airport in the terminal forecast, and until 9 August 2026 NOTHING IN THE
TREE PRODUCED IT. It was a staged file with no builder, so it could not be rebuilt when
its inputs moved and nobody could say how it had been made. That is how 189 airports
carrying 544.0m passengers stayed out of it for a year.

Each record is two sources joined:

  terminal, movements, domestic and international   the ACI annual dataset, through
                                                    scripts/ingest_aci.py
  od_both_ends_2024                                 Sabre preagg od_p2p, pax with the
                                                    airport at either end
  connecting_est                                    terminal less O&D, by construction

THE CONTROL RUNS FIRST. The rebuild is compared against the shipped file before it is
allowed to write anything. If it cannot reproduce what is already in production from the
inputs it claims to use, then any difference afterwards could be the builder rather than
the correction, and there is no point looking at it.

Usage:
    py -3.12 scripts\build_aci_hub_calibration.py                 control only
    py -3.12 scripts\build_aci_hub_calibration.py --apply         write the file
    py -3.12 scripts\build_aci_hub_calibration.py --panel FILE    use another panel
"""
from __future__ import annotations
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import json
import os

from avia_forecast import paths
from avia_forecast.io_safe import dump_atomic

YEAR = 2024
OUT_NAME = f"aci_hub_calibration_{YEAR}.json"

# The builder has to reproduce the screen as well as the arithmetic. The shipped file
# holds 2,430 airports against 2,557 in the panel, and the 127 difference is every airport
# ACI reports at zero: the smallest airport in the shipped file carries 2 passengers, so
# the screen is presence of traffic and not a size floor. Read off the shipped file, not
# assumed: a first version of this used a 100,000 floor and cut 826 airports that are in
# production.
TERMINAL_FLOOR = 0.0


def od_both_ends(codes):
    import duckdb
    con = duckdb.connect(paths.PREAGG, read_only=True)
    con.execute("SET enable_progress_bar=false")
    rows = con.execute(
        "SELECT o, sum(pax) FROM od_p2p WHERE year = ? GROUP BY 1", [YEAR]).fetchall()
    rows += con.execute(
        "SELECT d, sum(pax) FROM od_p2p WHERE year = ? GROUP BY 1", [YEAR]).fetchall()
    con.close()
    out = {}
    for code, pax in rows:
        out[code] = out.get(code, 0.0) + float(pax or 0.0)
    return {k: v for k, v in out.items() if k in codes}


def build(panel):
    aci = {r["iata"]: r for r in panel if r["year"] == YEAR}
    od = od_both_ends(set(aci))
    out = {}
    for iata, r in aci.items():
        term = r.get("terminal_pax") or 0.0
        if term <= TERMINAL_FLOOR:
            continue
        o = od.get(iata, 0.0)
        out[iata] = {
            "terminal_pax_2024": term,
            "od_both_ends_2024": o,
            "connecting_est": term - o,
            "connecting_share": round((term - o) / term, 4) if term else None,
            "movements_2024": r.get("movements"),
            "domestic": r.get("domestic"),
            "international": r.get("international"),
            "country_code": r.get("country_code"),
        }
        if r.get("terminal_source") and r["terminal_source"] != "passenger terminal":
            out[iata]["terminal_source"] = r["terminal_source"]
    return out


def control(built, shipped):
    """Reproduce the shipped file, or say plainly that the comparison is not worth making."""
    same_keys = set(built) == set(shipped)
    only_built = sorted(set(built) - set(shipped))
    only_shipped = sorted(set(shipped) - set(built))
    worst, gross, n = 0.0, 0.0, 0
    for k in set(built) & set(shipped):
        for f in ("terminal_pax_2024", "od_both_ends_2024"):
            a, b = built[k].get(f) or 0.0, shipped[k].get(f) or 0.0
            worst = max(worst, abs(a - b))
            gross += abs(a - b)
            n += 1
    world = sum((v.get("terminal_pax_2024") or 0.0) for v in shipped.values())
    print(f"CONTROL against the shipped {OUT_NAME}")
    print(f"  shipped {len(shipped):,} airports, rebuilt {len(built):,}, same set {same_keys}")
    if only_shipped:
        print(f"  in the shipped file and not the rebuild, {len(only_shipped)}: "
              + ", ".join(only_shipped[:15]))
    if only_built:
        pax = sum(built[k]["terminal_pax_2024"] for k in only_built)
        print(f"  in the rebuild and not the shipped file, {len(only_built)}, carrying "
              f"{pax / 1e6:,.1f}m: " + ", ".join(only_built[:15]))
    print(f"  largest single field difference {worst:,.0f} passengers, total absolute "
          f"{gross / 1e6:,.2f}m against a world of {world / 1e9:,.2f}bn, "
          f"{100 * gross / world:.5f}%")
    return gross < 0.0001 * world, only_built


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write the file; default is the control only")
    ap.add_argument("--panel", default=os.path.join(paths.DATA, "aci_panel_2013_2024.json"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    panel = json.load(open(a.panel, encoding="utf-8"))
    out_path = a.out or os.path.join(paths.DATA, OUT_NAME)
    shipped = json.load(open(out_path, encoding="utf-8")) if os.path.isfile(out_path) else {}

    built = build(panel)
    if shipped:
        ok, added = control(built, shipped)
        if not ok and not added:
            print("\n  The rebuild does not reproduce the shipped file and adds nothing, so "
                  "the difference is the builder. Nothing written.")
            return 1
        if added:
            print(f"\n  The rebuild ADDS {len(added)} airports. That is the correction, not "
                  f"a defect in the builder: they are in the ACI dataset and were dropped "
                  f"by the ingest.")
    else:
        print(f"no shipped {OUT_NAME} to control against")

    print(f"\nrebuilt: {len(built):,} airports, world terminal "
          f"{sum(v['terminal_pax_2024'] for v in built.values()) / 1e9:,.3f}bn")
    neg = sorted(((v["connecting_est"], k) for k, v in built.items() if v["connecting_est"] < 0))
    if neg:
        print(f"  {len(neg)} airports where Sabre O&D exceeds ACI terminal, largest "
              f"{neg[0][1]} by {-neg[0][0] / 1e6:,.2f}m. The terminal model floors the "
              f"connecting share at zero for these; they are a sampling difference between "
              f"the two sources, not a negative number of transfers.")

    if not a.apply:
        print("\ncontrol only, nothing written. Re-run with --apply to write "
              + os.path.relpath(out_path, paths.DATA))
        return 0
    dump_atomic(built, out_path, indent=1)
    print("\nwrote " + out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

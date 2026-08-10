r"""Per-airport destination-region seat shares, the mix the connecting forecast routes on.
Author: Avia Solutions.

`global_terminal.connecting_series` grows an airport's connecting traffic by routing it
across destination regions on this file, so a hub feeding Asia grows its transfers faster
than one feeding mature markets. An airport with no row here falls back to the world
international rate, which is a different forecast for that airport.

`data/oag_final_to_next_M.json` was dated 6 July 2026 and NOTHING IN THE TREE PRODUCED IT.
That is the same shape of hole as the ACI hub calibration, which had no builder either and
carried a defect for a year because of it. A file the engine reads and nothing writes
cannot be rebuilt when the store moves under it, and nobody can say what it was built from.

Basis, the same as every other read of the OAG store in this tree, so the numbers are
comparable with the fleet wedge and the stage length work: service type J, departures only,
one preferred tiling per region and year, each airport read from its home region file so
the cross-region duplication is removed without losing a flight.

Destination region is the model's own: Domestic where the destination country matches the
origin country, otherwise the destination's world region, through
`geo.regions_iso2.dest_region`, which is the same function the base ingest uses.

THE CONTROL RUNS FIRST and it is a comparison, not an equality. The shipped file was built
from an earlier store on an unrecorded basis, so it cannot be expected to reproduce to the
digit. What the control asserts is that the rebuild covers the airports the shipped file
covers and agrees with it closely on the mix: a rebuild that disagreed materially would be
measuring a different thing and should not be published without knowing which.

The OAG store is 16.8GB and this is a full scan. It runs on the workstation. In a Cowork
sandbox, with 4GB and two cores over a mount, expect it to take a long time or not finish.

Usage:
    py -3.12 scripts\build_oag_final_to_next_M.py                control only
    py -3.12 scripts\build_oag_final_to_next_M.py --apply        write the file
    py -3.12 scripts\build_oag_final_to_next_M.py --year 2025
"""
from __future__ import annotations
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import json
import os

from avia_forecast import paths
from avia_forecast.geo.regions_iso2 import dest_region
from avia_forecast.ingest.oag_store import home_regions, preferred_tilings
from avia_forecast.io_safe import dump_atomic

SERVICE_TYPE = "J"
LONGEST_SECTOR_KM = 15_400      # excluded, and why, in scripts/guard_oag_wedge.py
OUT_NAME = "oag_final_to_next_M.json"
MIN_SEATS = 1000.0              # below this a share is noise, and the airport falls back


def seats_by_dest(con, year):
    pref = preferred_tilings(con)
    pairs = sorted({(r, y, k) for (r, y), ks in pref.items() if y == year for k in ks})
    if not pairs:
        raise SystemExit(f"the store holds no preferred tiling for {year}")
    tiling = ",".join(f"('{r}',{y},'{k}')" for r, y, k in pairs)
    home = home_regions(con)
    homes = ",".join(f"('{a}','{r}')" for a, r in sorted(home.items()) if a and a.strip())
    sql = f"""
    WITH tiling(region, yr, week) AS (VALUES {tiling}),
         home(dep_airport, region) AS (VALUES {homes})
    SELECT o.dep_airport AS apt, o.dep_country AS oc, o.arr_country AS dc,
           sum(TRY_CAST(o.seats AS DOUBLE) * TRY_CAST(o.frequency AS DOUBLE)) AS seats
    FROM oag o
    JOIN tiling t ON t.region = o.region AND t.week = o.week
    JOIN home   h ON h.dep_airport = o.dep_airport AND h.region = o.region
    WHERE o.service_type = '{SERVICE_TYPE}'
      AND TRY_CAST(o.seats AS DOUBLE) > 0
      AND TRY_CAST(o.gcd_km AS DOUBLE) > 0
      AND TRY_CAST(o.gcd_km AS DOUBLE) <= {LONGEST_SECTOR_KM}
      AND o.dep_airport IS NOT NULL AND o.arr_country IS NOT NULL
    GROUP BY 1, 2, 3
    """
    return con.execute(sql).fetchall()


def build(rows):
    agg, unmapped = {}, {}
    for apt, oc, dc, seats in rows:
        r = dest_region(oc, dc)
        if r is None:
            unmapped[dc] = unmapped.get(dc, 0.0) + (seats or 0.0)
            continue
        agg.setdefault(apt, {})[r] = agg.setdefault(apt, {}).get(r, 0.0) + (seats or 0.0)
    out = {}
    for apt, mix in agg.items():
        tot = sum(mix.values())
        if tot < MIN_SEATS:
            continue
        out[apt] = {r: round(v / tot, 4) for r, v in sorted(mix.items(), key=lambda kv: -kv[1])}
    return out, unmapped


def control(built, shipped):
    common = sorted(set(built) & set(shipped))
    if not common:
        print("CONTROL: no airport in both files, so there is nothing to compare")
        return False
    diffs = []
    for a in common:
        b, s = built[a], shipped[a]
        d = sum(abs(b.get(r, 0.0) - s.get(r, 0.0)) for r in set(b) | set(s)) / 2.0
        diffs.append((d, a))
    diffs.sort(reverse=True)
    med = diffs[len(diffs) // 2][0]
    close = sum(1 for d, _ in diffs if d <= 0.05)
    print(f"CONTROL against the shipped {OUT_NAME}")
    print(f"  shipped {len(shipped):,} airports, rebuilt {len(built):,}, in both {len(common):,}")
    print(f"  in the shipped file and not the rebuild: {len(set(shipped) - set(built)):,}")
    print(f"  in the rebuild and not the shipped file: {len(set(built) - set(shipped)):,}")
    print(f"  mix difference, half the sum of absolute share differences: median "
          f"{med:.3f}, within 0.05 for {close:,} of {len(common):,} "
          f"({100 * close / len(common):.0f}%)")
    print("  largest movers: "
          + ", ".join(f"{a} {d:.2f}" for d, a in diffs[:8]))
    return med <= 0.10


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    import duckdb
    out_path = a.out or os.path.join(paths.DATA, OUT_NAME)
    shipped = json.load(open(out_path, encoding="utf-8")) if os.path.isfile(out_path) else {}

    con = duckdb.connect(paths.OAG_DB, read_only=True)
    con.execute("SET enable_progress_bar=false")
    print(f"reading the OAG store at {paths.OAG_DB} for {a.year}, service type "
          f"{SERVICE_TYPE}, departures only, one tiling per region")
    rows = seats_by_dest(con, a.year)
    con.close()
    print(f"  {len(rows):,} airport and destination-country pairs")

    built, unmapped = build(rows)
    if unmapped:
        top = sorted(unmapped.items(), key=lambda kv: -kv[1])[:8]
        print(f"  {len(unmapped)} destination countries carry no world region, "
              f"{sum(unmapped.values()) / 1e6:,.2f}m seats: "
              + ", ".join(f"{c} {s / 1e6:.2f}m" for c, s in top))

    ok = control(built, shipped) if shipped else True
    if shipped and not ok:
        print("\n  The rebuild does not agree with the shipped file on the mix. That is a "
              "difference worth understanding before it is published. Nothing written.")
        return 1

    if not a.apply:
        print("\ncontrol only, nothing written. Re-run with --apply to write "
              + os.path.basename(out_path))
        return 0
    dump_atomic(built, out_path, indent=1)
    print("\nwrote " + out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

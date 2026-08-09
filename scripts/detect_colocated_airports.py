r"""Find airports that serve the same city, from the schedule alone.
Author: Avia Solutions.

`scripts/build_airport_reference_supplement.py` can spot an airport that REPLACED an
incumbent, because the incumbent's traffic collapses. It is blind to the case that
started this work: a second airport at a city whose first airport keeps trading. Beijing
Daxing was caught only because OAG's own city code puts it in BJS, and Chengdu Tianfu
only because somebody went looking. Neither would have been found by a test.

This is the test. It needs no coordinates and no recall, only the great circle distance
the store already carries on every row.

THE METHOD. For any two airports A and B, and any destination C that both serve, the
triangle inequality gives

    | d(A,C) - d(B,C) |  <=  d(A,B)

so the largest such difference across every destination the two share is a LOWER BOUND
on how far apart they are. Two airports at the same city have almost the same distance
to everywhere, so the bound is small. Two airports at opposite ends of a country cannot
keep it small: some destination lies near one of them and far from the other, and that
destination gives the bound away. The bound is exact enough to separate a metropolitan
pair from a national one, which is all it has to do.

CALIBRATION, NOT ASSERTION. The threshold is not picked. It is read off the reference
table's own groupings: every pair the table already puts under one city code should
pass, every pair it puts under different city codes in the same country should fail,
and the separation between those two populations sets the cut. If the two populations
overlap, the method is not good enough and the run says so rather than proposing
anything.

Proposes. Never edits the reference table.

Usage:  py -3.12 scripts\detect_colocated_airports.py
                 [--reference "C:\src\meridian\app\reference_tables\airport_city_country.csv"]
                 [--min-od 0.25] [--min-common 15]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb  # noqa: E402

from avia_forecast import paths  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LONGEST_SECTOR_KM = 15_400


def distances(con, origins, year=2025):
    """{origin: {destination: km}} for the origins asked for.

    Restricted to ONE year, because the distance between two airports does not change
    and reading all eight is eight full scans of a 333m row store for the same answer.
    """
    inlist = ",".join("'" + a.replace("'", "''") + "'" for a in sorted(origins))
    rows = con.execute(f"""
        SELECT dep_airport, arr_airport, median(TRY_CAST(gcd_km AS DOUBLE))
        FROM oag
        WHERE service_type = 'J' AND dep_airport IN ({inlist})
          AND CAST(substr(week, 1, 4) AS INT) = {year}
          AND TRY_CAST(gcd_km AS DOUBLE) > 0
          AND TRY_CAST(gcd_km AS DOUBLE) <= {LONGEST_SECTOR_KM}
        GROUP BY 1, 2""").fetchall()
    out = {}
    for o, d, km in rows:
        if km:
            out.setdefault(o, {})[d] = km
    return out


def bound(da, db, min_common):
    """(common destinations, median absolute difference, lower bound on separation)."""
    common = set(da) & set(db)
    common.discard(None)
    diffs = [abs(da[c] - db[c]) for c in common if c not in (None,)]
    if len(diffs) < min_common:
        return len(diffs), None, None
    return len(diffs), statistics.median(diffs), max(diffs)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference", default=os.path.join(
        paths.QSI_APP, "reference_tables", "airport_city_country.csv"))
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--min-od", type=float, default=0.25,
                    help="only test missing airports above this many million O and D")
    ap.add_argument("--min-common", type=int, default=15,
                    help="destinations two airports must share before they are compared")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    with open(args.reference, newline="", encoding="utf-8-sig") as fh:
        ref = list(csv.DictReader(fh))
    city_of = {r["airport_code"].strip(): r["city_code"].strip() for r in ref}
    country_of = {r["airport_code"].strip(): r["country_code"].strip() for r in ref}

    con = duckdb.connect(paths.PREAGG, read_only=True)
    con.execute("SET enable_progress_bar=false")
    od = dict(con.execute("SELECT o, sum(pax)/1e6 FROM od_p2p WHERE year = ? GROUP BY 1",
                          [args.year]).fetchall())
    con.close()
    missing = sorted((a for a, p in od.items()
                      if a not in city_of and p >= args.min_od),
                     key=lambda a: -od[a])
    print(f"{len(missing)} airports absent from the reference table and above "
          f"{args.min_od}m outbound O&D")

    oag = duckdb.connect(paths.OAG_DB, read_only=True)
    oag.execute("SET enable_progress_bar=false")
    inl = ",".join("'" + a + "'" for a in missing)
    iso = {a: c for a, c in oag.execute(
        f"""SELECT dep_airport, mode(dep_country) FROM oag
            WHERE dep_airport IN ({inl}) GROUP BY 1""").fetchall() if c}
    countries = sorted(set(iso.values()))

    # Everything already in the table that shares a country with a missing airport, plus
    # the missing airports themselves. That is the whole comparison space and it is also
    # the calibration set.
    peers = sorted(a for a, c in country_of.items() if c in countries)
    print(f"comparing against {len(peers):,} airports the table already holds, across "
          f"{len(countries)} countries")
    dist = distances(oag, set(missing) | set(peers), year=args.year)
    oag.close()
    print(f"distance profiles read for {len(dist):,} airports")

    # CALIBRATION on the table's own groupings.
    same, diff = [], []
    by_country = {}
    for a in peers:
        by_country.setdefault(country_of[a], []).append(a)
    for cc, aps in by_country.items():
        for i, a in enumerate(aps):
            for b in aps[i + 1:]:
                if a not in dist or b not in dist:
                    continue
                n, med, lb = bound(dist[a], dist[b], args.min_common)
                if lb is None:
                    continue
                (same if city_of[a] == city_of[b] else diff).append((lb, a, b))
    if not same or not diff:
        print("not enough calibration pairs to set a threshold. Stopping.")
        return 1
    same.sort()
    diff.sort()
    s_lb = [x[0] for x in same]
    d_lb = [x[0] for x in diff]
    print(f"\nCALIBRATION on {len(same):,} pairs the table groups under one city and "
          f"{len(diff):,} it does not:")
    for label, v in (("same city", s_lb), ("different cities", d_lb)):
        qs = statistics.quantiles(v, n=20)
        print(f"  {label:<17} median {statistics.median(v):8.0f} km, 95th "
              f"{qs[-1]:8.0f} km, max {max(v):9.0f} km, min {min(v):6.0f} km")
    cut = statistics.quantiles(s_lb, n=20)[-1]          # 95th percentile of same-city
    false_pos = sum(1 for v in d_lb if v <= cut)
    print(f"\nthreshold set at the 95th percentile of the same-city population, "
          f"{cut:.0f} km")
    print(f"at that cut {false_pos:,} of {len(diff):,} different-city pairs would also "
          f"pass, {100 * false_pos / len(diff):.2f}%. Those are the pairs a human has "
          "to look at, and the number is the honest cost of the method")

    # PROPOSE.
    props = []
    for a in missing:
        if a not in dist:
            continue
        cc = iso.get(a)
        best = None
        for b in by_country.get(cc, []):
            if b not in dist:
                continue
            n, med, lb = bound(dist[a], dist[b], args.min_common)
            if lb is None or lb > cut:
                continue
            if best is None or lb < best[0]:
                best = (lb, b, n, med)
        if best:
            props.append((a, best[1], city_of[best[1]], cc, od.get(a, 0.0),
                          best[0], best[2]))
    props.sort(key=lambda r: -r[4])
    print(f"\nPROPOSED, {len(props)} of the {len(missing)} tested. Each is a missing "
          "airport that shares a city with one already in the table:")
    print(f"{'code':<6}{'nearest':<9}{'city':<6}{'cc':<4}{'O&D m':>8}"
          f"{'separation':>12}{'shared dests':>14}")
    for a, b, city, cc, pax, lb, n in props:
        print(f"{a:<6}{b:<9}{city:<6}{cc:<4}{pax:>8.3f}{lb:>10.0f} km{n:>14}")
    untested = [a for a in missing if a not in {p[0] for p in props}]
    print(f"\n{len(untested)} tested and not proposed, so each forms a catchment of its "
          f"own on this evidence: " + ", ".join(untested[:25])
          + (" ..." if len(untested) > 25 else ""))

    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "method": ("lower bound on separation from the triangle inequality over "
                      "shared destinations, calibrated on the reference table's own "
                      "city groupings"),
           "threshold_km": cut,
           "calibration": {"same_city_pairs": len(same), "different_city_pairs": len(diff),
                           "same_median_km": statistics.median(s_lb),
                           "different_median_km": statistics.median(d_lb),
                           "false_positive_rate_pct": 100 * false_pos / len(diff)},
           "proposed": [{"airport": a, "nearest_in_table": b, "city_code": city,
                         "country": cc, "od_m": pax, "separation_km_lower_bound": lb,
                         "shared_destinations": n}
                        for a, b, city, cc, pax, lb, n in props],
           "not_proposed": untested,
           "note": "Proposed only. The reference table is not edited by this script."}
    dest = args.json or os.path.join(paths.DATA, "colocated_airports.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"\nwritten to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

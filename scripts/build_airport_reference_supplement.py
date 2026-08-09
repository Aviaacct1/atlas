r"""The rows the airport reference table is missing. Author: Avia Solutions.

`app/reference_tables/airport_city_country.csv` in Meridian is the airport to city and
country reference both tools read. Every airport absent from it is dropped from the
forecast base at `apc.get(o)` in `scripts/ingest_global_base.py`, which is how Beijing
Daxing and Chengdu Tianfu came to be outside a world forecast. See `MEASUREMENTS.md`
sections 3 and 3a.

This writes the missing rows, in the file's own five column format, from what the estate
already knows: `data/oag_airport_names.json` for the IATA city code, the OAG store for
the ISO2 country, and the reference table itself for the city and country NAMES wherever
the code is already in it. Nothing is invented. A row whose city code is new to the table
goes out with an empty city name and appears in the review list rather than carrying a
name nobody sourced.

CITY GROUPING IS THE PART THAT NEEDS A HUMAN. The reference table groups a metropolitan
area under one city code: London's five airports share LON, Beijing's share BJS, Mexico
City's share MEX. OAG does not always agree. OAG gives Chengdu Tianfu its own city code
TFU while the table has Chengdu Shuangliu as CTU, so taking OAG at face value would put
the two Chengdu airports in different catchments, which is the same class of error as
leaving Tianfu out altogether. Disagreements are listed in OVERRIDES below with a reason
each, and everything else follows OAG.

Writes the supplement and a review list. It does NOT edit the Meridian file: that is a
commit in another repository and it is John's to make.

Usage:  py -3.12 scripts\build_airport_reference_supplement.py
                 [--reference "C:\src\meridian\app\reference_tables\airport_city_country.csv"]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb  # noqa: E402

from avia_forecast import paths  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Where OAG's city grouping and the reference table's convention disagree.
#
# This started as a hand-written entry: Chengdu Tianfu into CTU, because the table
# groups a metropolitan area under one code and OAG does not. That was me asserting a
# fact about geography, which is the thing this estate is not supposed to do.
# scripts/detect_colocated_airports.py now derives the same answer from the schedule,
# putting Tianfu 57 km from Shuangliu against a threshold of 72 km read off the table's
# own groupings, so the override below is kept only as a fallback for a host with no
# detector output and every entry says which source decided it.
OVERRIDES = {
    "TFU": ("CTU", "Chengdu Tianfu serves Chengdu alongside Shuangliu. Confirmed by "
                   "scripts/detect_colocated_airports.py at 57 km separation over 74 "
                   "shared destinations"),
}


def candidate_replacements(new_codes, iso, rise_year=2025, base_year=2019,
                           collapse_to=0.25, min_new=0.5):
    """New airports that look like they replaced an existing one in the same country.

    The test is deliberately mechanical. In the same country, the new airport carries
    real capacity in 2025 and did not exist in 2019, and an incumbent has fallen to
    under a quarter of its 2019 self. That pattern is a code change or a replacement
    airport, not two independent markets. Proposed, never applied: confirming a city
    assignment is a decision about a shared reference table.
    """
    if not new_codes:
        return []
    from avia_forecast.ingest.oag_store import home_regions, preferred_tilings
    con = duckdb.connect(paths.OAG_DB, read_only=True)
    con.execute("SET enable_progress_bar=false")
    countries = sorted({iso[c] for c in new_codes if iso.get(c)})
    inl = ",".join("'" + c + "'" for c in countries)
    # Annual seats, on the store's own conventions: SUM over the weeks of one preferred
    # tiling, and each airport read from its home region file. A first version grouped
    # by week and took the MAX, which returns the busiest month rather than the year,
    # and put Cairo 2019 at 1.2m departing seats. It looked like a series and it was a
    # monthly peak, which is why the detector found nothing.
    pref, home = preferred_tilings(con), home_regions(con)
    pairs = sorted({(r, y, k) for (r, y), ks in pref.items()
                    if y in (base_year, rise_year) for k in ks})
    tiling = ",".join(f"('{r}',{y},'{k}')" for r, y, k in pairs)
    homes = ",".join(f"('{a}','{r}')" for a, r in sorted(home.items()) if a and a.strip())
    rows = con.execute(f"""
        WITH tiling(region, yr, week) AS (VALUES {tiling}),
             home(dep_airport, region) AS (VALUES {homes})
        SELECT o.dep_airport, mode(o.dep_country), t.yr,
               sum(TRY_CAST(o.seats AS DOUBLE) * TRY_CAST(o.frequency AS DOUBLE))/1e6
        FROM oag o
        JOIN tiling t ON t.region = o.region AND t.week = o.week
        JOIN home   h ON h.dep_airport = o.dep_airport AND h.region = o.region
        WHERE o.service_type = 'J' AND o.dep_country IN ({inl})
        GROUP BY 1, 3""").fetchall()
    con.close()
    seats = {}
    for a, cc, yr, s in rows:
        seats.setdefault(a, {"cc": cc})[yr] = seats.get(a, {}).get(yr, 0.0) + (s or 0.0)
    out = []
    for new in new_codes:
        rec = seats.get(new, {})
        n25, n19 = rec.get(rise_year, 0.0), rec.get(base_year, 0.0)
        if n25 < min_new or n19 > 0.1 * n25:
            continue
        cc = iso.get(new)
        best = None
        for old, r in seats.items():
            if old == new or r.get("cc") != cc:
                continue
            o19, o25 = r.get(base_year, 0.0), r.get(rise_year, 0.0)
            if o19 >= min_new and o25 < collapse_to * o19:
                if best is None or o19 > best[1]:
                    best = (old, o19, o25)
        if best:
            out.append((new, best[0], cc, n25, best[1], best[2]))
    # One new airport may claim one closed airport. Without this every small Chinese
    # field that opened since 2019 claims Beijing Nanyuan, which closed when Daxing
    # opened and is the largest closure in the country. The largest claimant wins and
    # the rest are dropped, which is a tie break and not evidence.
    claimed, kept = set(), []
    for r in sorted(out, key=lambda r: -r[3]):
        if r[1] in claimed:
            continue
        claimed.add(r[1])
        kept.append(r)
    kept.sort(key=lambda r: -r[3])
    return kept


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference", default=os.path.join(
        paths.QSI_APP, "reference_tables", "airport_city_country.csv"))
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--review-above", type=float, default=0.25,
                    help="list for review any missing airport above this many million "
                         "outbound O and D")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if not os.path.exists(args.reference):
        raise SystemExit(f"reference table not found at {args.reference}. Point "
                         "--reference at the Meridian clone.")
    with open(args.reference, newline="", encoding="utf-8-sig") as fh:
        ref = list(csv.DictReader(fh))
    fields = list(ref[0].keys())
    have = {r["airport_code"].strip() for r in ref}
    city_name = {}
    country_name = {}
    for r in ref:
        city_name.setdefault(r["city_code"].strip(), r.get("city_name", "").strip())
        country_name.setdefault(r["country_code"].strip(),
                                r.get("country_name", "").strip())
    print(f"reference table: {len(ref):,} rows, {len(have):,} airports, "
          f"{len(city_name):,} city codes, {len(country_name):,} countries")

    # City code from the STORE, not from data/oag_airport_names.json. The two disagree:
    # the JSON gives Dakar Blaise Diagne its own city code DSS while the store's
    # dep_city puts it in DKR with the airport it replaced. The store is the source the
    # JSON was derived from, so the store wins, and every disagreement is reported
    # rather than resolved quietly.
    with open(os.path.join(REPO, "data", "oag_airport_names.json"),
              "r", encoding="utf-8") as fh:
        json_city = {k: v.get("city") for k, v in json.load(fh).items()}

    con = duckdb.connect(paths.PREAGG, read_only=True)
    con.execute("SET enable_progress_bar=false")
    od = dict(con.execute("SELECT o, sum(pax)/1e6 FROM od_p2p WHERE year = ? GROUP BY 1",
                          [args.year]).fetchall())
    codes = set(od) | {d for (d,) in con.execute(
        "SELECT DISTINCT d FROM od_p2p WHERE year = ?", [args.year]).fetchall()}
    con.close()
    missing = sorted(c for c in codes if c and c not in have)
    print(f"od_p2p {args.year}: {len(codes):,} airport codes, {len(missing):,} absent "
          f"from the reference table")

    oag = duckdb.connect(paths.OAG_DB, read_only=True)
    oag.execute("SET enable_progress_bar=false")
    inlist = ",".join("'" + c.replace("'", "''") + "'" for c in missing)
    iso, oag_city = {}, {}
    for a, cc, ct in oag.execute(
            f"""SELECT dep_airport, mode(dep_country), mode(dep_city) FROM oag
                WHERE dep_airport IN ({inlist}) GROUP BY 1""").fetchall():
        if cc:
            iso[a] = cc
        if ct:
            oag_city[a] = ct
    for a, cc, ct in oag.execute(
            f"""SELECT arr_airport, mode(arr_country), mode(arr_city) FROM oag
                WHERE arr_airport IN ({inlist}) GROUP BY 1""").fetchall():
        iso.setdefault(a, cc) if cc else None
        oag_city.setdefault(a, ct) if ct else None
    oag.close()
    disagree = [(a, oag_city[a], json_city[a]) for a in oag_city
                if json_city.get(a) and json_city[a] != oag_city[a]]
    if disagree:
        print(f"\ndata/oag_airport_names.json disagrees with the store's dep_city on "
              f"{len(disagree)} of the missing airports. The store is used. "
              + ", ".join(f"{a} store {s} against JSON {j}"
                          for a, s, j in sorted(disagree)[:8])
              + (" ..." if len(disagree) > 8 else ""))

    # Measured city assignments, where the detector has run. These take precedence over
    # OAG's city code, because OAG's is a commercial metropolitan definition and the
    # catchment logic needs a physical one. Each carries its measured separation, so a
    # reader can see what decided it rather than taking it on trust.
    coloc = {}
    coloc_path = os.path.join(paths.DATA, "colocated_airports.json")
    if os.path.exists(coloc_path):
        with open(coloc_path, "r", encoding="utf-8") as fh:
            cj = json.load(fh)
        for p in cj.get("proposed", []):
            coloc[p["airport"]] = (
                p["city_code"],
                f"measured {p['separation_km_lower_bound']:.0f} km from "
                f"{p['nearest_in_table']} over {p['shared_destinations']} shared "
                f"destinations, against a threshold of {cj['threshold_km']:.0f} km read "
                "off the reference table's own city groupings")
        print(f"\nscripts/detect_colocated_airports.py has run: {len(coloc)} city "
              f"assignments come from measurement rather than from OAG's city code")
    else:
        print(f"\nno detector output at {coloc_path}. City codes follow OAG except for "
              f"the {len(OVERRIDES)} hand-written override(s). Run "
              "scripts/detect_colocated_airports.py first.")

    rows, unresolved, review, new_cities = [], [], [], set()
    for a in missing:
        cc = iso.get(a)
        if not cc:
            unresolved.append(a)
            continue
        city, why = coloc.get(a) or OVERRIDES.get(a, (None, None))
        city = city or oag_city.get(a) or a
        joins = city in city_name
        if not joins:
            new_cities.add(city)
        row = {f: "" for f in fields}
        row["airport_code"] = a
        row["city_code"] = city
        row["city_name"] = city_name.get(city, "")
        row["country_code"] = cc
        row["country_name"] = country_name.get(cc, "")
        rows.append(row)
        pax = od.get(a, 0.0)
        if pax >= args.review_above or why:
            review.append((a, city, cc, pax, joins, why))

    print(f"resolved to a country: {len(rows):,}. Unresolved and left out: "
          f"{len(unresolved):,}, none of which has a scheduled service in the OAG store")
    print(f"city codes new to the reference table: {len(new_cities):,}, so those rows "
          f"carry an empty city name rather than an invented one")

    # A new airport that REPLACED an existing one is the dangerous case. Astana moved
    # from TSE to NQZ and Dakar from DKR to DSS; if the new code forms a catchment of
    # its own, one city becomes two, one of them with a collapsing history and the other
    # with no history at all, which is the Chengdu error in a different shape. Detected
    # rather than asserted: same country, the new airport rising while an existing one
    # falls away over the same years. Proposed for confirmation, never applied.
    print("\nCandidate replacements, detected from the schedule and NOT applied. An "
          "airport here probably belongs in the other one's city code:")
    cand = candidate_replacements([a for a, _, _, p, joins, _ in review
                                   if not joins and p >= args.review_above], iso)
    if cand:
        print(f"{'new':<6}{'old':<6}{'cc':<4}{'new 2025':>10}{'old 2019':>10}"
              f"{'old 2025':>10}{'new/old':>9}  departing seats m")
        for new, old, cc, n25, o19, o25 in cand:
            print(f"{new:<6}{old:<6}{cc:<4}{n25:>10.2f}{o19:>10.2f}{o25:>10.2f}"
                  f"{n25 / o19 if o19 else 0:>9.2f}")
        print("  A ratio near one is a clean handover. Well away from one means the "
              "pair is probably coincidence, two airports in one country that happened "
              "to move in opposite directions, and needs a human before it is believed.")
    else:
        print("  none")

    review.sort(key=lambda r: -r[3])
    print(f"\nFor review, every missing airport above {args.review_above}m outbound O&D "
          "and every override:")
    print(f"{'code':<6}{'city':<6}{'cc':<4}{'O&D m':>8}  catchment")
    for a, city, cc, pax, joins, why in review:
        note = ("joins the existing " + city + " catchment" if joins
                else "forms a new catchment of its own")
        print(f"{a:<6}{city:<6}{cc:<4}{pax:>8.3f}  {note}")
        if why:
            print(f"        not OAG's city code: {why}")

    out = args.out or os.path.join(REPO, "data",
                                   f"airport_reference_supplement_{args.year}.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"\n{len(rows):,} rows written to {out}")
    print("Merge into the Meridian reference table, fill the empty city names, and "
          "commit there before re-running scripts/ingest_global_base.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

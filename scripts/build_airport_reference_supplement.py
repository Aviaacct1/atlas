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


def load_names(path):
    """{IATA: city name} from a supplied reference, whatever its column names.

    Written to take OAG's airport reference or the OurAirports airports.csv without a
    conversion step, because a conversion step is where a column gets picked wrongly and
    nobody notices. The IATA column and the name column are found by header, and if
    neither is present it says so rather than returning an empty mapping that would look
    like a file with no matches.
    """
    iata_names = ("iata_code", "iata", "airport_code", "code", "airport")
    city_names = ("municipality", "city_name", "city", "cityname", "town", "place")
    if not os.path.exists(path):
        raise SystemExit(
            f"--names file not found: {path}\n"
            "Supply OAG's own airport reference, from the same subscription the "
            "schedules come from, or the OurAirports airports.csv, public domain and "
            "already used in this estate for the runway cache:\n"
            "  https://davidmegginson.github.io/ourairports-data/airports.csv\n"
            "Save it outside the repository, for example "
            r"E:\Avia\Global\data\airports_ourairports.csv, and point --names at it.")
    # Fallbacks, in order, and both were added after the first pass left 45 airports
    # unnamed. Every one of those 45 turned out to carry scheduled passenger service in
    # the OAG store, so none was a rail or bus point and the blanks were a matching
    # problem rather than a data-quality one. Two causes: OurAirports files a small
    # regional field under its local or ICAO code with iata_code left empty, and it
    # often has no municipality for an outback strip although it does have a name.
    alt_code = ("local_code", "gps_code", "ident", "icao_code")
    facility = (" airport", " airstrip", " heliport", " airfield", " air base",
                " air force station", " international", " municipal", " regional")
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rdr = csv.DictReader(fh)
        cols = {c.strip().lower(): c for c in (rdr.fieldnames or [])}
        ic = next((cols[c] for c in iata_names if c in cols), None)
        nc = next((cols[c] for c in city_names if c in cols), None)
        if not ic or not nc:
            raise SystemExit(
                f"{path} carries no IATA column and city name column this can read. "
                f"Headers are: {', '.join(rdr.fieldnames or [])}. Expected one of "
                f"{iata_names} and one of {city_names}.")
        alts = [cols[c] for c in alt_code if c in cols]
        kw = cols.get("keywords")
        nm = cols.get("name")
        out, derived = {}, set()
        for r in rdr:
            place = (r.get(nc) or "").strip()
            src_derived = False
            if not place and nm:
                # The airport's own name with the facility word removed. "Cooktown
                # Airport" is Cooktown. Derived, so it is counted separately and can be
                # reviewed; it is not presented as though OurAirports supplied a city.
                t = (r.get(nm) or "").strip()
                low = t.lower()
                for f in facility:
                    if low.endswith(f):
                        t = t[: -len(f)].strip()
                        low = t.lower()
                place, src_derived = t, bool(t)
            if not place:
                continue
            codes = [(r.get(ic) or "").strip().upper()]
            codes += [(r.get(c) or "").strip().upper() for c in alts]
            if kw:
                codes += [k.strip().upper() for k in (r.get(kw) or "").split(",")]
            for code in codes:
                if len(code) == 3 and code.isalpha() and code not in out:
                    out[code] = place
                    if src_derived:
                        derived.add(code)
    print(f"{os.path.basename(path)}: {len(out):,} three letter codes with a place name, "
          f"read from {ic} and {nc}, with {', '.join(alts)}"
          + (f" and {kw}" if kw else "") + " as fallback codes. "
          f"{len(derived):,} of the names are derived from the airport name because the "
          f"{nc} field is empty")
    return out


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
    ap.add_argument("--min-scope", type=float, default=2.0,
                    help="the scope.selection inclusion floor in million outbound O and "
                         "D, so a blank name below it can be reported as harmless")
    ap.add_argument("--review-above", type=float, default=0.25,
                    help="list for review any missing airport above this many million "
                         "outbound O and D")
    ap.add_argument("--names", default=None,
                    help="a CSV carrying a city or municipality name against an IATA "
                         "code, used to fill city_name for city codes the reference "
                         "table has never seen. OAG's own airport reference is the "
                         "right source, because it is the same vendor as the schedule "
                         "and the codes agree by construction. The OurAirports "
                         "airports.csv, public domain and already used in this estate "
                         "for runway data, works too: iata_code and municipality")
    ap.add_argument("--allow-blank-names", action="store_true",
                    help="hand over rows with no city name. Off by default: a blank in "
                         "a shared reference table is a defect somebody else inherits")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    # Both input files are checked before any query runs. The first version checked the
    # names file where it was used, which is after several minutes of reading the store,
    # so a typed path cost the whole run before it said anything.
    if not os.path.exists(args.reference):
        raise SystemExit(f"reference table not found at {args.reference}. Point "
                         "--reference at the Meridian clone.")
    names = load_names(args.names) if args.names else {}
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

    # City names for the codes the table has never seen. Nothing is invented: either a
    # supplied reference carries the name or the row is reported as incomplete.
    if names:
        filled = 0
        for r in rows:
            if not r["city_name"] and names.get(r["airport_code"]):
                r["city_name"] = names[r["airport_code"]]
                filled += 1
        print(f"\ncity names filled from {os.path.basename(args.names)}: {filled:,}")
    blank = [r for r in rows if not r["city_name"]]
    if blank:
        exposure = sorted(((od.get(r["airport_code"], 0.0), r["airport_code"])
                           for r in blank), reverse=True)
        over = [(p, a) for p, a in exposure if p >= args.min_scope]
        print("\nStill unnamed, largest first. The working assumption was that a code "
              "no airport reference carries would be a rail or bus point, since Sabre "
              "codes those into O&D. It was wrong: every one of the 45 left after the "
              "first pass carried scheduled passenger service in the OAG store, so "
              "these are real airports that no reference has filed under this code, "
              "not surface transport to be excluded.")
        print("  " + ", ".join(f"{a} {p:.3f}m" for p, a in exposure[:45]))
        print(f"\n{len(blank):,} rows still carry no city name. "
              f"{len(over)} of them are above the {args.min_scope}m scope floor and "
              f"would be modelled as airports in their own right"
              + (": " + ", ".join(f"{a} {p:.2f}m" for p, a in over[:12]) if over
                 else ", so every one of them falls into a residual pseudo-airport"))
        if not args.allow_blank_names:
            print(f"\nNot writing. A blank city name in a shared reference table is a "
                  f"defect the next person inherits, and this would be {len(blank):,} "
                  "of them. Supply --names with OAG's airport reference, or the "
                  "OurAirports airports.csv, or pass --allow-blank-names deliberately.")
            return 1

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

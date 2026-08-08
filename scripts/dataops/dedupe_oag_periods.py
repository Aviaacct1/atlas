"""Remove superseded period keys from oag.duckdb once monthly re-pulls complete a
region-year. The capped annual ('2018') and half-year ('2018-H1/H2') slices for
NA/SWP/LatAm (and any others re-pulled monthly) must go, or seats sums count the
year twice. A legacy key is deleted ONLY when the same region-year has a full
12-month tiling (split-month parts count when both halves present).
Author: Avia Solutions.

  py -3.12 dedupe_oag_periods.py            # dry run - shows what would be deleted
  py -3.12 dedupe_oag_periods.py --apply    # actually delete
"""
import sys
import duckdb

APPLY = "--apply" in sys.argv
con = duckdb.connect("oag.duckdb", read_only=not APPLY)

rows = con.execute("""SELECT region, CAST(substr(week,1,4) AS INT) AS yr, list(DISTINCT week)
                      FROM oag WHERE week NOT LIKE '20__-__-__' GROUP BY 1,2""").fetchall()
todo = []
for region, yr, keys in rows:
    ks = set(keys)
    full_months = {k[5:7] for k in ks if len(k) == 7 and k[4] == "-" and k[5:].isdigit()}
    parts = {}
    for k in ks:
        if len(k) > 7 and k[7] == "p":
            parts.setdefault(k[5:7], set()).add(k)
    part_months = {mm for mm, s in parts.items() if len(s) >= 2}
    legacy = [k for k in ks if len(k) == 4 or k.endswith("H1") or k.endswith("H2")]
    if legacy and len(full_months | part_months) == 12:
        todo.append((region, yr, sorted(legacy)))

# permanent collision check (6 Aug): a month present as BOTH a full file and split
# parts double-counts every sum over its keys - flag loudly, deletion is a manual call
coll = con.execute("""SELECT region, substr(week,1,7) ym,
                             list(DISTINCT week) FROM oag
                      WHERE week NOT LIKE '20__-__-__' AND length(week) >= 7
                        AND substr(week,6,2) BETWEEN '01' AND '12'
                      GROUP BY 1,2
                      HAVING COUNT(DISTINCT length(week)) > 1""").fetchall()
for region, ym, keys in coll:
    print(f"MONTH COLLISION: {region} {ym} loaded as both full and split {sorted(keys)} "
          f"- sums over this month DOUBLE-COUNT; delete one form manually")

if not todo:
    print("nothing to dedupe: no region-year has both a full monthly set and legacy keys")
for region, yr, legacy in todo:
    for k in legacy:
        n = con.execute("SELECT COUNT(*) FROM oag WHERE region=? AND week=?", [region, k]).fetchone()[0]
        if APPLY:
            con.execute("DELETE FROM oag WHERE region=? AND week=?", [region, k])
            print(f"DELETED  {region} {k}  ({n:,} rows) - superseded by complete monthly {yr}")
        else:
            print(f"would delete  {region} {k}  ({n:,} rows) - superseded by complete monthly {yr}")
con.close()
print("APPLIED" if APPLY else "dry run only - rerun with --apply to delete")

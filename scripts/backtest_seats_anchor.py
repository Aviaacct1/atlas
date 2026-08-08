"""backtest_seats_anchor - one command: regenerate the seats-vs-GDP airport backtest
(the "5.4% vs 12.3%" evidence behind the C2 year-1 schedule anchor) from the OAG store
and the ACI panel. Author: Avia Solutions.

Method: for each airport with ACI actuals and OAG seats at base and target year,
  seats-driven forecast  = pax_base x (seats_target / seats_base)
  naive GDP benchmark    = pax_base x (GDP_target / GDP_base), country real GDP
scored as WMAPE and median APE across airports. Seats are computed on two bases:
  annual  - the full-year slices (monthly/half-year/annual files; complete schedules)
  weekly  - the two snapshot weeks per year (the basis of the original 13 Jul run)
Inter-regional double counting removed by taking each dep airport's HOME region file
(the region where its row-sum is largest; that file holds all its departures).
Writes data/backtest_seats_exhibit.json. Score pairs auto-extend as years land.

  py -3.12 scripts\\backtest_seats_anchor.py            [--db C:\\Avia\\oag.duckdb]
"""
from __future__ import annotations
import json, os, statistics, sys

import duckdb

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from avia_forecast.io_safe import dump_atomic
from avia_forecast.paths import DATA, OAG_DB

# Resolution order: AVIA_OAG_STORE (the one name for the store file, also read by
# avia_forecast/ingest/oag_peak.py), then the central resolver. No session name is
# written here: a literal /sessions/<name>/ path pins the script to one session and
# is dead the moment that session ends. Only paths.py may name a mount, by glob.
DB_CANDIDATES = [os.environ.get("AVIA_OAG_STORE"), OAG_DB]
SCORE_PAIRS = [(2015, 2019), (2015, 2018), (2019, 2023), (2019, 2024),
               (2023, 2024), (2024, 2025)]   # (2019,2023) = recovery completion;
                                             # (2023,2024) = modern-era t+1, the product's first-year claim


def _preferred_tilings(con):
    """Per (region, year): the ONE set of non-weekly keys to sum - full monthly set
    (split-month parts count when both halves present) if it tiles the year, else
    both halves, else the annual key. Prevents double counting when monthly re-pulls
    coexist with superseded annual/half keys (dedupe_oag_periods.py removes those
    from the store; this guard makes the backtest safe either way)."""
    comp, pref = set(), {}
    q = """SELECT region, CAST(substr(week,1,4) AS INT) AS yr, list(DISTINCT week)
           FROM oag WHERE week NOT LIKE '20__-__-__' GROUP BY 1, 2"""
    for region, yr, keys in con.execute(q).fetchall():
        ks = set(keys)
        monthly = {k for k in ks if len(k) == 7 and k[4] == "-" and k[5:].isdigit()}
        parts = {}
        for k in ks:
            if len(k) > 7 and k[7] == "p":
                parts.setdefault(k[5:7], set()).add(k)
        month_cov = {k[5:7] for k in monthly} | {mm for mm, s in parts.items() if len(s) >= 2}
        halves = {k for k in ks if k.endswith("H1") or k.endswith("H2")}
        annual = {k for k in ks if len(k) == 4}
        if len(month_cov) == 12:
            part_keys = set().union(*[s for mm, s in parts.items() if len(s) >= 2]) if parts else set()
            pref[(region, int(yr))] = monthly | part_keys
            comp.add((region, int(yr)))
        elif len({k[-2:] for k in halves}) == 2:
            pref[(region, int(yr))] = halves
            comp.add((region, int(yr)))
        elif annual:
            pref[(region, int(yr))] = annual
            comp.add((region, int(yr)))
    # density EXCLUSION on the preferred tiling totals. Norm = the region's MAXIMUM
    # year (a capped majority poisons a median norm - NA 2015-17 proved it); a year
    # below 60% of the max is a truncated load and is EXCLUDED from scoring, because a
    # capped base year against a complete target year inflates ratios ~10x and wrecks
    # the weighted metric (the 227% artefact of 27 Jul).
    tot = {}
    for region, yr, week, s in con.execute(
            """SELECT region, CAST(substr(week,1,4) AS INT), week, SUM(try_cast(seats AS DOUBLE))
               FROM oag WHERE week NOT LIKE '20__-__-__' GROUP BY 1, 2, 3""").fetchall():
        key = (region, int(yr))
        if key in pref and week in pref[key] and s:
            tot[key] = tot.get(key, 0.0) + s
    mx = {}
    for (r, y), t in tot.items():
        mx[r] = max(mx.get(r, 0.0), t)
    for (r, y) in sorted(comp):
        t = tot.get((r, y), 0)
        if mx.get(r) and t < 0.6 * mx[r]:
            print(f"EXCLUDED: {r} {y} seats total {t/1e6:,.0f}m is <60% of the region's best year "
                  f"({mx[r]/1e6:,.0f}m) - truncated load, dropped from annual scoring")
            pref.pop((r, y), None)
    return pref


def seats_by_basis(con):
    """{basis: {iata: {year: seats}}} - home-region MAX removes cross-file duplicates;
    annual basis sums ONLY each region-year's preferred tiling."""
    pref = _preferred_tilings(con)
    out = {}
    # weekly basis: unchanged
    d = {}
    q = """SELECT dep_airport, yr, MAX(s) FROM (
             SELECT dep_airport, region, CAST(substr(week,1,4) AS INT) AS yr,
                    SUM(try_cast(seats AS DOUBLE)) AS s
             FROM oag WHERE week LIKE '20__-__-__' AND dep_airport IS NOT NULL
             GROUP BY 1, 2, 3) GROUP BY 1, 2"""
    for iata, yr, s in con.execute(q).fetchall():
        if s and s > 0:
            d.setdefault(iata, {})[int(yr)] = float(s)
    out["weekly"] = d
    # annual basis: each airport is scored from its HOME region only (the region file
    # holding its full departure schedule = the one with the greatest seats across all
    # years). If the home region-year is excluded as truncated, the airport-year is
    # absent and the score pair skips it - a partial appearance in another region's
    # file must never stand in for the base year.
    rows2 = con.execute("""SELECT dep_airport, region, CAST(substr(week,1,4) AS INT) AS yr, week,
                                  SUM(try_cast(seats AS DOUBLE)) AS s
                           FROM oag WHERE week NOT LIKE '20__-__-__' AND dep_airport IS NOT NULL
                           GROUP BY 1, 2, 3, 4""").fetchall()
    region_tot = {}
    for iata, region, yr, week, s in rows2:
        if s and s > 0:
            region_tot[(iata, region)] = region_tot.get((iata, region), 0.0) + float(s)
    home = {}
    for (iata, region), t in region_tot.items():
        if iata not in home or t > home[iata][1]:
            home[iata] = (region, t)
    d = {}
    for iata, region, yr, week, s in rows2:
        if not s or s <= 0 or home[iata][0] != region:
            continue
        key = (region, int(yr))
        if key not in pref or week not in pref[key]:
            continue
        d.setdefault(iata, {})[int(yr)] = d.get(iata, {}).get(int(yr), 0.0) + float(s)
    out["annual"] = d
    return out


def load_actuals():
    fp = next(p for p in (os.path.join(DATA, "aci_panel_long.json"),
                          os.path.join(REPO, "data", "aci_panel_long.json")) if os.path.exists(p))
    panel = json.load(open(fp))
    rows = panel if isinstance(panel, list) else panel.get("rows", panel)
    pax, ctry = {}, {}
    for r in rows:
        v = r.get("terminal_pax") or r.get("total_pax")
        if not v:
            continue
        pax.setdefault(r["iata"], {})[int(r["year"])] = float(v)
        if r.get("country_code"):
            ctry[r["iata"]] = r["country_code"]
    return pax, ctry


def main():
    db = next(p for p in DB_CANDIDATES if p and os.path.exists(p))
    con = duckdb.connect(db, read_only=True)
    seats = seats_by_basis(con)
    pax, ctry = load_actuals()
    gfp = next(p for p in (os.path.join(DATA, "oef_gdp_pop_by_iso2.json"),
                           os.path.join(REPO, "data", "oef_gdp_pop_by_iso2.json")) if os.path.exists(p))
    gdp = json.load(open(gfp))["gdp"]

    exhibit = {"db": db, "summary": {}}
    for basis in ("annual", "weekly"):
        S = seats[basis]
        for b, t in SCORE_PAIRS:
            errs_s, errs_n, tot_a, tot_es, tot_en, n = [], [], 0.0, 0.0, 0.0, 0
            for iata, sy in S.items():
                if b not in sy or t not in sy or iata not in pax:
                    continue
                p = pax[iata]
                if b not in p or t not in p or p[b] <= 0 or p[t] <= 0:
                    continue
                g = gdp.get(ctry.get(iata, ""), {})
                if not (g.get(str(b)) and g.get(str(t))):
                    continue
                f_seats = p[b] * (sy[t] / sy[b])
                f_naive = p[b] * (g[str(t)] / g[str(b)])
                tot_a += p[t]
                tot_es += abs(f_seats - p[t]); tot_en += abs(f_naive - p[t])
                errs_s.append(abs(f_seats - p[t]) / p[t]); errs_n.append(abs(f_naive - p[t]) / p[t])
                n += 1
            if n < 25:
                continue
            key = f"{basis} {b}->{t}"
            w20 = sum(1 for e in errs_s if e <= 0.20) / n
            w10 = sum(1 for e in errs_s if e <= 0.10) / n
            exhibit["summary"][key] = {
                "n": n, "wmape_seats": round(tot_es / tot_a, 4), "wmape_naive_gdp": round(tot_en / tot_a, 4),
                "median_ape_seats": round(statistics.median(errs_s), 4),
                "median_ape_naive": round(statistics.median(errs_n), 4),
                "within_20pct": round(w20, 4), "within_10pct": round(w10, 4),
                "beats_naive": tot_es < tot_en}
            s = exhibit["summary"][key]
            print(f"{key}: n={n}  WMAPE seats {s['wmape_seats']*100:.1f}% vs naive GDP "
                  f"{s['wmape_naive_gdp']*100:.1f}%  | median APE {s['median_ape_seats']*100:.1f}% "
                  f"vs {s['median_ape_naive']*100:.1f}%  | WITHIN +-20%: {w20*100:.0f}%  +-10%: {w10*100:.0f}%"
                  f"  | beats naive: {s['beats_naive']}")
    out = os.path.join(REPO, "data", "backtest_seats_exhibit.json")
    dump_atomic(exhibit, out, indent=1)
    print("exhibit ->", out)


if __name__ == "__main__":
    main()

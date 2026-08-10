"""World Bank population and GDP per capita PPP ingest, for every country in the base.
Author: Avia Solutions.

Why this exists. `global_demand.country_headroom` returns None when a country carries no
population and GDP per capita record, so the propensity ceiling cannot bind and the
country compounds at its regional GDP growth with no saturation at all. On 9 August 2026
`data/worldbank_pop_gdppc.json` held 30 countries, covering 2,607m of 3,341m outbound
O&D. The other 734m, 22% of the world, ran unceilinged. The same record also sets
maturity in `global_demand._maturity`, so a missing country takes its region's default
rather than its own GDP per head. See MEASUREMENTS.md section 4.

What it does. Reads the base to learn which countries the forecast actually needs, pulls
the most recent non-empty observation per country for each indicator from the World Bank
API, checks the result against the base BEFORE writing anything, and writes only on
--apply.

The guard runs before the write, not after it. On 9 August an ingest wrote its output and
then complained about it, which left the bad file on disk for the next step.

Usage:
    py -3.12 scripts\\ingest_worldbank.py                 check only, writes nothing
    py -3.12 scripts\\ingest_worldbank.py --apply         write data/worldbank_pop_gdppc.json
    py -3.12 scripts\\ingest_worldbank.py --out FILE      write somewhere else, for a measurement

Network: the World Bank API is not reachable from a Cowork sandbox, so this runs on the
workstation.
"""
from __future__ import annotations
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import datetime as dt
import json
import os
import urllib.request

from avia_forecast.io_safe import dump_atomic

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")
OUT_DEFAULT = os.path.join(DATA, "worldbank_pop_gdppc.json")
OVERRIDES = os.path.join(DATA, "worldbank_overrides.json")

POP = "SP.POP.TOTL"                 # population, total, persons
GDP = "NY.GDP.PCAP.PP.CD"           # GDP per capita, PPP, current international $

API = "https://api.worldbank.org/v2/country/all/indicator/{ind}?format=json&mrnev=1&per_page=400&page={page}"

# Plausibility bounds. A value outside these is a read error rather than a country, so it
# is named and the run stops rather than reaching the engine.
POP_MIN, POP_MAX = 1_000, 1_600_000_000
GDPPC_MIN, GDPPC_MAX = 200.0, 250_000.0
MAX_AGE_YEARS = 6                   # an observation older than this is named in the report

# A country the base carries and the ingest cannot fill is a stopping error above this
# outbound O&D, in millions, and a named line in the report below it. An aggregate of
# "3.22% unmapped" is what hid Beijing Daxing, so nothing here reports a percentage
# without naming what is inside it.
FAIL_M = 5.0


def fetch_indicator(ind, timeout=60):
    """Most recent non-empty observation per country, with the year it comes from."""
    out, page, pages = {}, 1, 1
    while page <= pages:
        with urllib.request.urlopen(API.format(ind=ind, page=page), timeout=timeout) as r:
            payload = json.loads(r.read())
        head, rows = payload[0], (payload[1] or [])
        pages = int(head.get("pages", 1))
        for row in rows:
            iso2 = (row.get("country") or {}).get("id")
            val = row.get("value")
            if not iso2 or val is None:
                continue
            out[iso2.upper()] = {"value": float(val), "year": int(row["date"])}
        page += 1
    return out


def base_countries():
    """Country -> outbound O&D in millions, from the base the forecast is built on."""
    base = json.load(open(os.path.join(DATA, "global_base_od_2025.json")))
    meta = json.load(open(os.path.join(DATA, "global_airport_meta_2025.json")))
    tot = {}
    for iata, regs in base.items():
        c = meta[iata]["country"]
        tot[c] = tot.get(c, 0.0) + sum(regs.values())
    return tot


def load_overrides():
    """Countries the World Bank does not publish, each with a named source. Taiwan is the
    one that matters at 27.0m outbound O&D. Nothing is invented here: an empty file means
    the country is reported as unfilled, not quietly given a number."""
    if not os.path.isfile(OVERRIDES):
        return {}
    return json.load(open(OVERRIDES)).get("data", {})


def build(pop, gdp, overrides):
    recs, notes = {}, []
    for iso2 in sorted(set(pop) | set(gdp)):
        p, g = pop.get(iso2), gdp.get(iso2)
        if not p or not g:
            continue
        recs[iso2] = {"pop": int(round(p["value"])), "gdp_pc_ppp": round(g["value"]),
                      "pop_year": p["year"], "gdp_year": g["year"], "source": "World Bank"}
    for iso2, rec in overrides.items():
        if iso2 in recs:
            notes.append(f"override for {iso2} ignored: the World Bank publishes it")
            continue
        if not (rec.get("pop") and rec.get("gdp_pc_ppp") and rec.get("source")):
            notes.append(f"override for {iso2} skipped: pop, gdp_pc_ppp and source are all required")
            continue
        recs[iso2] = dict(rec)
    return recs, notes


def check(recs, need, shipped):
    """Everything that could make the written file wrong, before it is written."""
    errors, warnings, lines = [], [], []
    world = sum(need.values())

    bad = []
    for iso2, r in recs.items():
        if not (POP_MIN <= r["pop"] <= POP_MAX):
            bad.append(f"{iso2} population {r['pop']:,}")
        if not (GDPPC_MIN <= r["gdp_pc_ppp"] <= GDPPC_MAX):
            bad.append(f"{iso2} GDP per capita PPP {r['gdp_pc_ppp']:,}")
    if bad:
        errors.append("values outside the plausible band: " + "; ".join(bad))

    missing = {c: m for c, m in need.items() if c not in recs}
    big = {c: m for c, m in missing.items() if m >= FAIL_M}
    if big:
        errors.append("countries in the base with no record, each above the "
                      f"{FAIL_M:.0f}m stopping threshold: "
                      + ", ".join(f"{c} {m:.1f}m" for c, m in sorted(big.items(), key=lambda kv: -kv[1])))

    lost = [c for c in shipped if c not in recs]
    if lost:
        errors.append("countries the shipped file covered and this run does not: " + ", ".join(sorted(lost)))

    stale = sorted((r.get("gdp_year") or 0, iso2) for iso2, r in recs.items() if iso2 in need)
    cutoff = dt.date.today().year - MAX_AGE_YEARS
    old = [f"{iso2} {yr}" for yr, iso2 in stale if yr and yr < cutoff]
    if old:
        warnings.append(f"GDP per capita observation older than {cutoff}: " + ", ".join(old[:20])
                        + (f" and {len(old) - 20} more" if len(old) > 20 else ""))

    covered = sum(m for c, m in need.items() if c in recs)
    lines.append(f"countries in the base                {len(need)}")
    lines.append(f"records written                      {len(recs)}")
    lines.append(f"base countries covered               {len(need) - len(missing)} "
                 f"({covered:,.1f}m of {world:,.1f}m outbound O&D, {100 * covered / world:.1f}%)")
    lines.append(f"base countries still uncovered       {len(missing)} "
                 f"({sum(missing.values()):,.1f}m, {100 * sum(missing.values()) / world:.1f}%)")
    if missing:
        named = sorted(missing.items(), key=lambda kv: -kv[1])
        lines.append("  uncovered, largest first: "
                     + ", ".join(f"{c} {m:.1f}m" for c, m in named[:25]))
    return errors, warnings, lines


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the file; default is check only")
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--from-pull", default=None,
                    help="build from a staged pull of the two series rather than calling "
                         "the API, in the form {'pop': {ISO2: {'value','year'}}, 'gdp': ...}. "
                         "The API is not reachable from a Cowork sandbox, so a pull taken "
                         "elsewhere can be replayed through the same checks and produce the "
                         "same file")
    a = ap.parse_args()

    need = base_countries()
    shipped = json.load(open(OUT_DEFAULT))["data"] if os.path.isfile(OUT_DEFAULT) else {}

    if a.from_pull:
        raw = json.load(open(a.from_pull))
        pop, gdp = raw["pop"], raw["gdp"]
        print(f"replaying the staged pull at {a.from_pull}")
        print(f"  {raw.get('_source', 'no source line in the pull')}")
    else:
        print(f"fetching {POP} and {GDP} from the World Bank API, most recent non-empty per country")
        pop, gdp = fetch_indicator(POP), fetch_indicator(GDP)
    print(f"  population {len(pop)} countries, GDP per capita PPP {len(gdp)} countries")

    recs, notes = build(pop, gdp, load_overrides())
    errors, warnings, lines = check(recs, need, shipped)

    print()
    for ln in lines:
        print("  " + ln)
    for n in notes:
        print("  note: " + n)
    for w in warnings:
        print("  warning: " + w)
    if errors:
        print()
        for e in errors:
            print("  ERROR: " + e)
        print("\nnothing written.")
        return 1

    if not a.apply:
        print("\ncheck only, nothing written. Re-run with --apply to write "
              + os.path.relpath(a.out, REPO))
        return 0

    src = (f"World Bank API, population {POP} and GDP per capita PPP {GDP}, most recent "
           f"non-empty observation per country. Retrieved "
           f"{dt.date.today().strftime('%d %B %Y')} by scripts/ingest_worldbank.py.")
    if a.from_pull:
        src = (json.load(open(a.from_pull)).get("_source") or src) + \
              " Built by scripts/ingest_worldbank.py --from-pull. Countries the World Bank " \
              "does not publish are filled from data/worldbank_overrides.json, each with its " \
              "own source on the record."
    payload = {
        "_source": src,
        "_keys": "ISO2 -> {pop (persons), gdp_pc_ppp (current intl $), pop_year, gdp_year, source}",
        "data": recs,
    }
    dump_atomic(payload, a.out, indent=1)
    print("\nwrote " + os.path.relpath(a.out, REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

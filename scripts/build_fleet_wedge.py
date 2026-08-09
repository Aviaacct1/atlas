r"""The fleet productivity wedge, against Boeing's Market Overview pages 24 and 25.
Author: Avia Solutions.

Boeing shows three lines and names the space between them. Over 2004-2023 their single
aisle ASK grows 5.7%, seats 4.8% and fleet 3.1%, and the difference is densification,
up-gauging, longer stage lengths and more flights a day. We produce the ASK and imply
the fleet, and until now have not explained the space between them.

The wedge is an identity, and it holds exactly rather than approximately:

    ASK  =  departures  x  seats per departure  x  stage length

so, over any window,

    (1 + g_ASK)  =  (1 + g_departures) x (1 + g_gauge) x (1 + g_stage)

Every term on the right is measured from the OAG schedule rather than assumed. Gauge is
then split by shift-share into up-gauging, which is carriers moving departures onto
larger types, and densification, which is more seats fitted inside a given type:

    G_T - G_0  =  SUM (w_iT - w_i0) s_i0        up-gauging, the mix moving
                + SUM w_i0 (s_iT - s_i0)        densification, within the type
                + SUM (w_iT - w_i0)(s_iT - s_i0) interaction, reported and not allocated

where w_i is type i's share of departures and s_i its seats per departure.

WHAT THIS CANNOT PRODUCE, and it is the fourth of Boeing's four terms. Flights per
aircraft per day needs a count of aircraft in service, and no fleet data reaches Atlas.
The dashboard's implied fleet divides ASK by PROD_NB = 330 and PROD_WB = 1,050 million
ASK per aircraft per year, two constants typed into webapp/dashboard.html. Using those
to derive utilisation and then reading utilisation as a finding would be circular: the
answer would be whatever was typed in. So three of Boeing's four terms are measured
here and the fourth is named as an acquisition item, alongside the fleet age slide.

WINDOW. Boeing run 2004-2023. The OAG store holds 2015 to 2019 and 2023 to 2025, eight
years, with 2020 to 2022 excluded by policy. We cannot reproduce their window and do not
pretend to. The default windows are 2015-2019, five clean pre-COVID years, and 2019-2025,
which spans the shock. Both are stated on the output and must be stated on the slide.

Reads the guard report and refuses to run if it failed. Run scripts\guard_oag_wedge.py
first.

Usage:  py -3.12 scripts\build_fleet_wedge.py [--windows 2015:2019 2019:2025]
                                              [--skip-guard-check]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb  # noqa: E402
import yaml  # noqa: E402

from avia_forecast import paths  # noqa: E402
from avia_forecast.ingest.oag_store import preferred_tilings, home_regions  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICE_TYPE = "J"
LONGEST_SECTOR_KM = 15_400      # excluded, and why, in scripts/guard_oag_wedge.py

# Boeing, Market Overview 2025, European Consultant Conference, March 2025, pages 24
# and 25, Wendy Sowers. Window 2004-2023, which is not ours. Carried so the two sit on
# the same page and the window difference is impossible to miss.
BOEING = {
    "source": ("Boeing, Market Overview 2025, European Consultant Conference, "
               "March 2025, pages 24 and 25"),
    "window": "2004-2023",
    "single_aisle": {"ask": 0.057, "seats": 0.048, "fleet": 0.031},
}

SEGMENTS = {
    "single_aisle": lambda m: m["aisles"] == 1 and m["class"] == "mainline_jet",
    "widebody": lambda m: m["aisles"] == 2,
    "regional_jet": lambda m: m["class"] == "regional_jet",
    "turboprop": lambda m: m["class"] == "turboprop",
}


def load_body_map():
    with open(os.path.join(REPO, "config", "aircraft_body_types.yaml"),
              "r", encoding="utf-8") as fh:
        return (yaml.safe_load(fh) or {}).get("codes", {})


def check_guard(skip):
    path = os.path.join(paths.DATA, "oag_wedge_guard.json")
    if skip:
        print("guard check skipped by flag")
        return
    if not os.path.exists(path):
        raise SystemExit(f"no guard report at {path}. Run scripts/guard_oag_wedge.py "
                         "before building the wedge.")
    with open(path, "r", encoding="utf-8") as fh:
        rep = json.load(fh)
    if rep.get("verdict") == "FAIL":
        bad = [c["check"] for c in rep.get("checks", []) if c["status"] == "FAIL"]
        raise SystemExit(f"the guard report at {path} is FAIL on: {', '.join(bad)}. "
                         "Fix the store or the guard before building the wedge.")
    print(f"guard report {rep.get('verdict')}, generated {rep.get('generated')}")


def build_panel(con, years):
    """One row per year, segment and aircraft code: departures, seats, ASK."""
    pref = preferred_tilings(con)
    home = home_regions(con)
    pairs = sorted({(r, y, k) for (r, y), ks in pref.items() if y in years for k in ks})
    tiling = ",".join(f"('{r}',{y},'{k}')" for r, y, k in pairs)
    homes = ",".join(f"('{a}','{r}')" for a, r in sorted(home.items()) if a and a.strip())
    sql = f"""
    WITH tiling(region, yr, week) AS (VALUES {tiling}),
         home(dep_airport, region) AS (VALUES {homes})
    SELECT t.yr                                                    AS yr,
           o.region                                                AS region,
           o.aircraft_code                                         AS code,
           o.carrier_category                                      AS cat,
           sum(TRY_CAST(o.frequency AS BIGINT))                    AS departures,
           sum(TRY_CAST(o.seats AS DOUBLE)
               * TRY_CAST(o.frequency AS DOUBLE))                  AS seats,
           sum(TRY_CAST(o.seats AS DOUBLE) * TRY_CAST(o.frequency AS DOUBLE)
               * TRY_CAST(o.gcd_km AS DOUBLE))                     AS ask_km
    FROM oag o
    JOIN tiling t ON t.region = o.region AND t.week = o.week
    JOIN home   h ON h.dep_airport = o.dep_airport AND h.region = o.region
    WHERE o.service_type = '{SERVICE_TYPE}'
      AND TRY_CAST(o.gcd_km AS DOUBLE) > 0
      AND TRY_CAST(o.gcd_km AS DOUBLE) <= {LONGEST_SECTOR_KM}
      AND TRY_CAST(o.seats AS DOUBLE) > 0
    GROUP BY 1, 2, 3, 4
    """
    return con.execute(sql).fetchall()


def boeing_regions():
    """{ISO2: Boeing CMO region}, from config/region_schemes.yaml, plus the default."""
    with open(os.path.join(REPO, "config", "region_schemes.yaml"),
              "r", encoding="utf-8") as fh:
        book = yaml.safe_load(fh) or {}
    sch = book["schemes"]["boeing_cmo"]
    out = {}
    for region, codes in sch["regions"].items():
        for c in codes:
            out[str(c).upper()] = region
    return out, sch.get("default", "Unassigned")


def stage_length_by_boeing_region(con, years):
    """Departing seats and ASK by year and Boeing CMO region, so the measured stage
    length can be set beside the fixed per-region constant the RPK conversion applies.

    This is the term that decides whether our RPK growth can be compared with Boeing's
    at all. Our conversion multiplies passengers by a constant, so our RPK CAGR is our
    passenger CAGR to the decimal place. Boeing's RPK CAGR carries their stage length
    growth inside it. The two are therefore not like for like, and the size of the
    difference is measured here rather than argued about.
    """
    meta_path = os.path.join(REPO, "data", "global_airport_meta_2025.json")
    with open(meta_path, "r", encoding="utf-8") as fh:
        meta = json.load(fh)
    iso, default = boeing_regions()
    pref = preferred_tilings(con)
    home = home_regions(con)
    pairs = sorted({(r, y, k) for (r, y), ks in pref.items() if y in years for k in ks})
    tiling = ",".join(f"('{r}',{y},'{k}')" for r, y, k in pairs)
    homes = ",".join(f"('{a}','{r}')" for a, r in sorted(home.items()) if a and a.strip())
    sql = f"""
    WITH tiling(region, yr, week) AS (VALUES {tiling}),
         home(dep_airport, region) AS (VALUES {homes})
    SELECT t.yr AS yr, o.dep_airport AS apt,
           sum(TRY_CAST(o.seats AS DOUBLE) * TRY_CAST(o.frequency AS DOUBLE)) AS seats,
           sum(TRY_CAST(o.seats AS DOUBLE) * TRY_CAST(o.frequency AS DOUBLE)
               * TRY_CAST(o.gcd_km AS DOUBLE)) AS ask_km
    FROM oag o
    JOIN tiling t ON t.region = o.region AND t.week = o.week
    JOIN home   h ON h.dep_airport = o.dep_airport AND h.region = o.region
    WHERE o.service_type = '{SERVICE_TYPE}'
      AND TRY_CAST(o.gcd_km AS DOUBLE) > 0
      AND TRY_CAST(o.gcd_km AS DOUBLE) <= {LONGEST_SECTOR_KM}
      AND TRY_CAST(o.seats AS DOUBLE) > 0
    GROUP BY 1, 2
    """
    agg, unmapped = {}, {}
    for yr, apt, seats, ask in con.execute(sql).fetchall():
        rec = meta.get(apt)
        if rec is None:
            unmapped[apt] = unmapped.get(apt, 0) + (seats or 0)
            continue
        reg = iso.get(str(rec.get("country") or "").upper(), default)
        d = agg.setdefault(reg, {}).setdefault(yr, [0.0, 0.0])
        d[0] += seats or 0
        d[1] += ask or 0
        w = agg.setdefault("World", {}).setdefault(yr, [0.0, 0.0])
        w[0] += seats or 0
        w[1] += ask or 0
    return agg, unmapped


def segment_of(code, bmap):
    m = bmap.get(code)
    if not m:
        return None
    for name, test in SEGMENTS.items():
        if test(m):
            return name
    return None


def totals_by(rows, bmap, key):
    """{key -> {year: (departures, seats, ask)}} summed over aircraft codes."""
    out = {}
    for yr, region, code, cat, dep, seats, ask in rows:
        seg = segment_of(code, bmap)
        if seg is None:
            continue
        k = key(seg, region, cat)
        if k is None:
            continue
        d = out.setdefault(k, {}).setdefault(yr, [0.0, 0.0, 0.0])
        d[0] += dep or 0
        d[1] += seats or 0
        d[2] += ask or 0
    return out


def cagr(a, b, n):
    if not a or not b or n <= 0:
        return None
    return (b / a) ** (1.0 / n) - 1.0


def wedge(series, y0, y1):
    """The identity, term by term, over one window."""
    if y0 not in series or y1 not in series:
        return None
    d0, s0, a0 = series[y0]
    d1, s1, a1 = series[y1]
    if min(d0, s0, a0, d1, s1, a1) <= 0:
        return None
    n = y1 - y0
    g0, g1 = s0 / d0, s1 / d1                      # seats per departure
    l0, l1 = a0 / s0, a1 / s1                      # seat-km per seat, the stage length
    out = {
        "years": [y0, y1],
        "ask_bn_start": a0 / 1e9, "ask_bn_end": a1 / 1e9,
        "departures_start": d0, "departures_end": d1,
        "seats_m_start": s0 / 1e6, "seats_m_end": s1 / 1e6,
        "gauge_start": g0, "gauge_end": g1,
        "stage_km_start": l0, "stage_km_end": l1,
        "g_ask": cagr(a0, a1, n),
        "g_seats": cagr(s0, s1, n),
        "g_departures": cagr(d0, d1, n),
        "g_gauge": cagr(g0, g1, n),
        "g_stage": cagr(l0, l1, n),
    }
    check = ((1 + out["g_departures"]) * (1 + out["g_gauge"]) * (1 + out["g_stage"])
             - 1 - out["g_ask"])
    out["identity_residual"] = check
    return out


def shift_share(rows, bmap, segment, y0, y1, region=None):
    """Gauge growth split into up-gauging, densification and the interaction."""
    per = {}
    for yr, reg, code, cat, dep, seats, ask in rows:
        if segment_of(code, bmap) != segment:
            continue
        if region and reg != region:
            continue
        if yr not in (y0, y1):
            continue
        d = per.setdefault(yr, {}).setdefault(code, [0.0, 0.0])
        d[0] += dep or 0
        d[1] += seats or 0
    if y0 not in per or y1 not in per:
        return None
    d0 = sum(v[0] for v in per[y0].values())
    d1 = sum(v[0] for v in per[y1].values())
    g0 = sum(v[1] for v in per[y0].values()) / d0
    g1 = sum(v[1] for v in per[y1].values()) / d1
    codes = set(per[y0]) | set(per[y1])
    mix = dens = inter = 0.0
    contrib = []
    for c in codes:
        a = per[y0].get(c, [0.0, 0.0])
        b = per[y1].get(c, [0.0, 0.0])
        w0, w1 = a[0] / d0, b[0] / d1
        s0 = a[1] / a[0] if a[0] else 0.0
        s1 = b[1] / b[0] if b[0] else 0.0
        # A type absent at the start has no start-year seat count, so its whole effect
        # is a mix effect at its own gauge. Using zero would credit the arrival of the
        # A320neo to densification, which it is not.
        base = s0 if a[0] else s1
        m = (w1 - w0) * base
        dn = w0 * (s1 - s0) if a[0] and b[0] else 0.0
        it = (w1 - w0) * (s1 - s0) if a[0] and b[0] else 0.0
        mix += m
        dens += dn
        inter += it
        contrib.append({"code": c, "name": (bmap.get(c) or {}).get("name", c),
                        "share_start": w0, "share_end": w1,
                        "seats_start": s0, "seats_end": s1,
                        "mix_seats": m, "dens_seats": dn})
    n = y1 - y0
    total = g1 - g0
    contrib.sort(key=lambda r: -(abs(r["mix_seats"]) + abs(r["dens_seats"])))

    def rate(part):
        """The CAGR the gauge would have shown had only this part moved."""
        return cagr(g0, g0 + part, n)

    return {
        "segment": segment, "region": region or "world", "years": [y0, y1],
        "gauge_start": g0, "gauge_end": g1, "gauge_change_seats": total,
        "up_gauging_seats": mix, "densification_seats": dens, "interaction_seats": inter,
        "up_gauging_cagr": rate(mix), "densification_cagr": rate(dens),
        "interaction_cagr": rate(inter),
        "unexplained_seats": total - mix - dens - inter,
        "top_types": contrib[:15],
    }


def fmt_pct(v):
    return "n/a" if v is None else f"{v * 100:.1f}%"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--windows", nargs="*", default=["2015:2019", "2019:2025"])
    ap.add_argument("--skip-guard-check", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    check_guard(args.skip_guard_check)
    windows = [tuple(int(x) for x in w.split(":")) for w in args.windows]
    years = sorted({y for w in windows for y in w})

    bmap = load_body_map()
    con = duckdb.connect(paths.OAG_DB, read_only=True)
    con.execute("SET enable_progress_bar=false")
    print(f"reading {paths.OAG_DB} for {years}")
    rows = build_panel(con, years)
    print(f"{len(rows):,} panel rows")

    by_seg = totals_by(rows, bmap, lambda s, r, c: s)
    by_all = totals_by(rows, bmap, lambda s, r, c: "all_segments")
    by_seg_region = totals_by(rows, bmap, lambda s, r, c: (s, r))

    out = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": ("Avia Solutions analysis of the OAG schedule store, service type J, "
                   "departures only, one tiling per region-year, each airport read from "
                   "its home region file"),
        "boeing": BOEING,
        "note_fleet": ("Flights per aircraft per day is Boeing's fourth term and is not "
                       "produced here. It needs a count of aircraft in service, which "
                       "Atlas does not hold. Deriving it from the dashboard's PROD_NB "
                       "and PROD_WB constants would return whatever was typed in."),
        "windows": {}, "shift_share": {}, "by_region": {},
    }

    for y0, y1 in windows:
        key = f"{y0}-{y1}"
        out["windows"][key] = {}
        print(f"\n=== {y0} to {y1}, Avia, OAG schedule, departures only ===")
        print(f"{'segment':<14}{'ASK':>8}{'seats':>8}{'departs':>9}{'gauge':>8}"
              f"{'stage':>8}{'residual':>10}")
        for seg in list(SEGMENTS) + ["all_segments"]:
            series = (by_all.get("all_segments", {}) if seg == "all_segments"
                      else by_seg.get(seg, {}))
            w = wedge(series, y0, y1)
            if not w:
                continue
            out["windows"][key][seg] = w
            print(f"{seg:<14}{fmt_pct(w['g_ask']):>8}{fmt_pct(w['g_seats']):>8}"
                  f"{fmt_pct(w['g_departures']):>9}{fmt_pct(w['g_gauge']):>8}"
                  f"{fmt_pct(w['g_stage']):>8}{w['identity_residual'] * 100:>9.4f}pp")
        for seg in ("single_aisle", "widebody"):
            ss = shift_share(rows, bmap, seg, y0, y1)
            if ss:
                out["shift_share"].setdefault(key, {})[seg] = ss
                print(f"  {seg}: gauge {ss['gauge_start']:.1f} to {ss['gauge_end']:.1f} "
                      f"seats a departure. Up-gauging "
                      f"{fmt_pct(ss['up_gauging_cagr'])} a year, densification "
                      f"{fmt_pct(ss['densification_cagr'])}, interaction "
                      f"{fmt_pct(ss['interaction_cagr'])}")
        for (seg, reg), series in sorted(by_seg_region.items()):
            w = wedge(series, y0, y1)
            if w:
                out["by_region"].setdefault(key, {}).setdefault(seg, {})[reg] = w

    # Stage length by Boeing region, the term that decides whether an RPK CAGR built on
    # a constant stage length can be compared with one that is not.
    sl_years = sorted({y for w in windows for y in w})
    sl, unmapped = stage_length_by_boeing_region(con, sl_years)
    out["stage_length_by_boeing_region"] = {}
    tot_unmapped = sum(unmapped.values())
    print(f"\n=== measured stage length by Boeing CMO region, km per departing seat ===")
    print(f"{len(unmapped)} departure airports carry no record in "
          f"data/global_airport_meta_2025.json, {tot_unmapped / 1e6:.1f}m seats, "
          f"excluded and listed in the JSON")
    hdr = "  ".join(f"{y}" for y in sl_years)
    print(f"{'region':<16}{hdr:>28}" + "".join(f"{f'{a}-{b}':>12}" for a, b in windows))
    for reg in sorted(sl, key=lambda r: (r == "World", r)):
        ser = sl[reg]
        lens = {y: (ser[y][1] / ser[y][0]) for y in sl_years if y in ser and ser[y][0]}
        row = {"km_per_seat": lens, "cagr": {}}
        line = f"{reg:<16}" + "  ".join(f"{lens.get(y, 0):8.0f}" for y in sl_years)
        for a, b in windows:
            g = cagr(lens.get(a), lens.get(b), b - a)
            row["cagr"][f"{a}-{b}"] = g
            line += f"{fmt_pct(g):>12}"
        out["stage_length_by_boeing_region"][reg] = row
        print(line)
    out["unmapped_airports_seats"] = {k: v for k, v in
                                      sorted(unmapped.items(), key=lambda kv: -kv[1])[:60]}

    dest = args.json or os.path.join(paths.DATA, "fleet_wedge.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"\nwritten to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

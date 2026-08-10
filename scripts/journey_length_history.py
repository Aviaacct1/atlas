r"""How far people fly, measured over the longest history we hold, and what it is a
function of. Author: Avia Solutions.

Why this exists. The RPK conversion holds stage length constant, so our RPK CAGR is our
passenger CAGR while Boeing's carries their stage length growth. Replacing the constant
needs a path, and a path extrapolated from a ten-year rate is a shape somebody chose.
This looks for the relationship underneath it instead: average journey length against
real income per head, estimated over the longest run we hold, so the forecast path falls
out of the GDP path the model already carries and decelerates as income growth does.

What it measures. Sabre `od_p2p` holds true origin and destination passengers by year
from 2013. Great circle distance comes from the airport coordinates in
`E:\Avia\Global\data\airports.csv`. Average journey length is the passenger-weighted
great circle distance, by year, for the world and for each Boeing region of the origin
country. Real GDP per head comes from the Oxford Economics country file, which runs from
1988 to 2050, so the same relationship can be carried forward.

What it is not. This is O&D great circle distance, not flown sector distance. A
connecting itinerary flies further than the great circle between its endpoints, so the
LEVEL here sits below Boeing's stage length. The two should track in GROWTH unless the
connecting share is itself moving, and the cross-check against the OAG measured stage
length is printed so that assumption is tested rather than assumed.

2020, 2021 and 2022 are excluded, the same policy the OAG store carries. The Sabre 2021
slice reports more passengers than 2022 and nearly as many as 2019, which is not a
pandemic year and is another reason not to use it.

The guards run before any elasticity is printed. Coordinate coverage, a fixed panel of
O&D pairs present in every year, a distance sanity check and the year list are all
reported first, because a coverage change between years reads exactly like a change in
how far people fly.

Usage:
    py -3.12 scripts\journey_length_history.py
    py -3.12 scripts\journey_length_history.py --json out.json
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import yaml  # noqa: E402

from avia_forecast import paths  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXCLUDE_YEARS = {2020, 2021, 2022}
MIN_COORD_COVERAGE = 0.97      # below this the year is not measuring journey length
EARTH_MAX_KM = 20015.0


def haversine(lat1, lon1, lat2, lon2):
    r1, r2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(r1) * math.cos(r2) * math.sin(dlam / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(h)))


def load_coords():
    fp = os.path.join(paths.DATA, "airports.csv")
    out = {}
    with open(fp, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            code = (row.get("iata_code") or "").strip()
            if len(code) != 3:
                continue
            try:
                out[code] = (float(row["latitude_deg"]), float(row["longitude_deg"]))
            except (TypeError, ValueError):
                continue
    return out, fp


def load_airport_country():
    fp = os.path.join(paths.QSI_APP, "reference_tables", "airport_city_country.csv")
    with open(fp, encoding="utf-8-sig") as fh:
        return {r["airport_code"].strip(): r["country_code"].strip()
                for r in csv.DictReader(fh)}, fp


def boeing_regions():
    with open(os.path.join(REPO, "config", "region_schemes.yaml"), encoding="utf-8") as fh:
        sch = (yaml.safe_load(fh) or {})["schemes"]["boeing_cmo"]
    out = {}
    for region, codes in sch["regions"].items():
        for c in codes:
            out[str(c).upper()] = region
    return out, sch.get("default", "Unassigned")


def ols(x, y):
    """Slope, intercept and R2 for a single regressor."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    A = np.vstack([x, np.ones_like(x)]).T
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ coef
    ss = ((y - y.mean()) ** 2).sum()
    return float(coef[0]), float(coef[1]), float(1 - (resid ** 2).sum() / ss) if ss else float("nan")


def within_ols(groups, with_trend=False):
    """Pooled elasticity with a fixed effect per group: demean inside each group, then one
    slope through the lot. This is the relationship over TIME, not across regions.

    With `with_trend`, a common annual term is estimated alongside the income term. Income
    is not the only thing that lengthened a journey between 2013 and 2025: longer range
    narrowbodies, low cost long haul and route liberalisation all did, and none of them is
    a function of GDP per head. Leaving them out loads them onto the income coefficient or
    onto nothing at all, and which of the two happens is what the trend term reveals."""
    xs, ts, ys = [], [], []
    for _, (x, y, t) in groups.items():
        if len(x) < 3:
            continue
        x, y, t = (np.asarray(v, float) for v in (x, y, t))
        xs.append(x - x.mean())
        ys.append(y - y.mean())
        ts.append(t - t.mean())
    if not xs:
        return None
    x, y, t = np.concatenate(xs), np.concatenate(ys), np.concatenate(ts)
    A = np.vstack([x, t]).T if with_trend else x.reshape(-1, 1)
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ coef
    ss = (y ** 2).sum()
    r2 = float(1 - (resid ** 2).sum() / ss) if ss else float("nan")
    return (float(coef[0]), float(coef[1]) if with_trend else 0.0, r2, len(y))


def region_trend_table(reg_series, use):
    """Annual growth in journey length per region, estimated on every observation with a
    region fixed effect, tested against one common rate, and shrunk towards it.

    The shrinkage weight is not chosen. It is the share of the observed spread between
    regional estimates that survives once the estimation error in each is removed:
    tau2 / (tau2 + se2), with tau2 the spread of the estimates less the sampling variance.
    A region whose own estimate is precise keeps it; a set of estimates no more spread out
    than their own error collapses to the common rate."""
    regs = sorted(r for r in reg_series if r != "World")

    def fit(years, own_trends):
        y, ridx, t = [], [], []
        for i, r in enumerate(regs):
            for yr in years:
                y.append(math.log(reg_series[r][yr]))
                ridx.append(i)
                t.append(float(yr - years[-1]))
        y, ridx, t = np.array(y), np.array(ridx), np.array(t)
        n, k = len(y), len(regs)
        fe = np.zeros((n, k))
        fe[np.arange(n), ridx] = 1.0
        if own_trends:
            x = np.hstack([fe, np.zeros((n, k))])
            for i in range(k):
                x[ridx == i, k + i] = t[ridx == i]
        else:
            x = np.hstack([fe, t.reshape(-1, 1)])
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        resid = y - x @ coef
        rss = float(resid @ resid)
        df = x.shape[1]
        s2 = rss / (n - df)
        se = np.sqrt(np.diag(np.linalg.pinv(x.T @ x)) * s2)
        return coef, se, rss, n, df, k

    c_own, se_own, rss_own, n, df_own, k = fit(use, True)
    c_com, se_com, rss_com, _, df_com, _ = fit(use, False)
    f_stat = ((rss_com - rss_own) / (df_own - df_com)) / (rss_own / (n - df_own))
    try:
        from scipy import stats
        p = float(1 - stats.f.cdf(f_stat, df_own - df_com, n - df_own))
    except Exception:
        p = float("nan")

    est = {regs[i]: math.exp(c_own[k + i]) - 1 for i in range(k)}
    ses = {regs[i]: float(se_own[k + i]) for i in range(k)}
    common = math.exp(c_com[k]) - 1
    mean = float(np.mean(list(est.values())))
    var = float(np.var(list(est.values()), ddof=1))
    se_bar = float(np.mean(list(ses.values())))
    tau2 = max(0.0, var - se_bar ** 2)
    w = tau2 / (tau2 + se_bar ** 2) if (tau2 + se_bar ** 2) else 0.0

    pre_years = [y for y in use if y <= 2019]
    c_pre, _, _, _, _, _ = fit(pre_years, True)
    pre = {regs[i]: math.exp(c_pre[k + i]) - 1 for i in range(k)}

    return {"regions": {r: {"trend": est[r], "se": ses[r],
                            "shrunk": mean + w * (est[r] - mean)} for r in regs},
            "common": common, "common_se": float(se_com[k]),
            "shrink_weight": w, "mean": mean, "pre2019": pre,
            "F": f_stat, "F_df1": df_own - df_com, "F_df2": n - df_own, "p": p}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", default=None)
    ap.add_argument("--wedge-json", default=os.path.join(paths.DATA, "fleet_wedge.json"))
    a = ap.parse_args(argv)

    import duckdb

    coords, coord_fp = load_coords()
    apc, apc_fp = load_airport_country()
    iso, default = boeing_regions()
    oef = json.load(open(os.path.join(paths.DATA, "oef_gdp_pop_by_iso2.json")))

    con = duckdb.connect(paths.PREAGG, read_only=True)
    con.execute("SET enable_progress_bar=false")
    years = [r[0] for r in con.execute(
        "SELECT DISTINCT year FROM od_p2p ORDER BY 1").fetchall()]
    use = [y for y in years if y not in EXCLUDE_YEARS]
    print("Average journey length from Sabre od_p2p and great circle distance")
    print(f"  passengers   {paths.PREAGG}")
    print(f"  coordinates  {coord_fp}")
    print(f"  countries    {apc_fp}")
    print(f"  income       {os.path.join(paths.DATA, 'oef_gdp_pop_by_iso2.json')}, "
          f"{oef['_source']}")
    print(f"\nYears in the store: {', '.join(str(y) for y in years)}")
    print(f"Years used: {', '.join(str(y) for y in use)}. "
          f"Excluded: {', '.join(str(y) for y in sorted(EXCLUDE_YEARS)) } "
          f"(the OAG policy, and the Sabre 2021 slice reports more passengers than 2022)")
    missing = [y for y in range(min(years), max(years) + 1) if y not in years]
    if missing:
        print(f"Absent from the store entirely: {', '.join(str(y) for y in missing)}")

    rows = con.execute(
        "SELECT year, o, d, pax FROM od_p2p WHERE year NOT IN "
        f"({','.join(str(y) for y in sorted(EXCLUDE_YEARS))})").fetchall()
    con.close()

    dist_cache = {}
    pax_by_year = defaultdict(float)
    ok_by_year = defaultdict(float)
    pairs_by_year = defaultdict(set)
    long_pax = 0.0
    same = 0.0
    agg = defaultdict(lambda: [0.0, 0.0])          # (year, region) -> [pax, pax*km]
    per_pair = defaultdict(lambda: defaultdict(float))
    for y, o, d, pax in rows:
        pax_by_year[y] += pax
        if o == d:
            same += pax
            continue
        key = (o, d) if o < d else (d, o)
        km = dist_cache.get(key)
        if km is None:
            a1, a2 = coords.get(o), coords.get(d)
            if not a1 or not a2:
                dist_cache[key] = False
                continue
            km = haversine(a1[0], a1[1], a2[0], a2[1])
            dist_cache[key] = km
        if km is False:
            continue
        if km > EARTH_MAX_KM:
            long_pax += pax
            continue
        ok_by_year[y] += pax
        pairs_by_year[y].add(key)
        reg = iso.get(str(apc.get(o) or "").upper(), default)
        v = agg[(y, reg)]
        v[0] += pax
        v[1] += pax * km
        w = agg[(y, "World")]
        w[0] += pax
        w[1] += pax * km
        per_pair[key][y] += pax

    print("\nGUARDS")
    bad = []
    for y in use:
        cov = ok_by_year[y] / pax_by_year[y] if pax_by_year[y] else 0.0
        if cov < MIN_COORD_COVERAGE:
            bad.append((y, cov))
        print(f"  {y}  passengers {pax_by_year[y] / 1e6:8,.1f}m   with both endpoints "
              f"located {100 * cov:5.1f}%")
    if same:
        print(f"  same airport at both ends, excluded: {same / 1e6:,.2f}m passengers")
    if long_pax:
        print(f"  distance above {EARTH_MAX_KM:,.0f} km, excluded: {long_pax / 1e6:,.2f}m")
    if bad:
        print(f"  ERROR: coordinate coverage below {100 * MIN_COORD_COVERAGE:.0f}% in "
              + ", ".join(f"{y} at {100 * c:.1f}%" for y, c in bad)
              + ". A year that locates fewer passengers is not measuring journey length. "
                "Stopping.")
        return 1

    panel = [k for k, v in per_pair.items() if all(y in v for y in use)]
    panel_share = {y: sum(per_pair[k][y] for k in panel) / ok_by_year[y] for y in use}
    print(f"  O&D pairs present in every year used: {len(panel):,} of {len(per_pair):,}, "
          f"carrying {100 * min(panel_share.values()):.1f}% to "
          f"{100 * max(panel_share.values()):.1f}% of located passengers")

    def ajl(y, reg):
        v = agg.get((y, reg))
        return v[1] / v[0] if v and v[0] else None

    panel_ajl = {}
    for y in use:
        p = sum(per_pair[k][y] for k in panel)
        km = sum(per_pair[k][y] * dist_cache[k] for k in panel)
        panel_ajl[y] = km / p if p else None

    print("\nWORLD AVERAGE JOURNEY LENGTH, km, passenger weighted, one way")
    print(f"  {'year':<6}{'all pairs':>12}{'fixed panel':>14}")
    for y in use:
        print(f"  {y:<6}{ajl(y, 'World'):>12,.0f}{panel_ajl[y]:>14,.0f}")

    def cagr(s, y0, y1):
        if y0 not in s or y1 not in s or not s[y0] or not s[y1]:
            return None
        return (s[y1] / s[y0]) ** (1.0 / (y1 - y0)) - 1.0

    wser = {y: ajl(y, "World") for y in use}
    windows = [(min(use), 2019), (2015, 2019), (2023, max(use)), (2015, max(use)),
               (min(use), max(use))]
    print("\n  growth, all pairs and fixed panel:")
    for y0, y1 in windows:
        if y0 not in wser or y1 not in wser:
            continue
        ga, gp = cagr(wser, y0, y1), cagr(panel_ajl, y0, y1)
        print(f"    {y0}-{y1}   all pairs {ga * 100:>6.2f}%   fixed panel {gp * 100:>6.2f}%")

    if os.path.isfile(a.wedge_json):
        wedge = json.load(open(a.wedge_json))
        oag = wedge["stage_length_by_boeing_region"]["World"]["cagr"].get("2015-2025")
        mine = cagr(wser, 2015, max(use))
        if oag is not None and mine is not None:
            print(f"\n  CROSS-CHECK. OAG measured stage length growth 2015-2025 is "
                  f"{oag * 100:.2f}% a year. Sabre O&D journey length over the same window "
                  f"is {mine * 100:.2f}%. Difference {abs(oag - mine) * 100:.2f}pp. Two "
                  f"different measures of distance, from two different sources, over the "
                  f"same window.")

    # The Boeing scheme's default is Eurasia, not an unassigned bucket, so the default
    # region is a real region and is kept. Excluding it dropped Eurasia entirely from a
    # first version of this table, which is the shape of error that reads as a data gap.
    regions = sorted({r for (_, r) in agg if r != "World"})
    print("\nBY BOEING REGION OF THE ORIGIN COUNTRY, km")
    print(f"  {'region':<16}" + "".join(f"{y:>8}" for y in use) + f"{'CAGR':>9}")
    reg_series = {}
    for reg in regions + ["World"]:
        s = {y: ajl(y, reg) for y in use}
        if any(v is None for v in s.values()):
            continue
        reg_series[reg] = s
        g = cagr(s, min(use), max(use))
        print(f"  {reg:<16}" + "".join(f"{s[y]:>8,.0f}" for y in use)
              + f"{g * 100:>8.2f}%")

    gdp_pc = {}
    for reg in reg_series:
        codes = [c for c, r in iso.items() if r == reg] if reg != "World" else list(iso)
        by_year = {}
        for y in list(use) + list(range(2025, 2051)):
            gsum = psum = 0.0
            for c in codes:
                g = (oef["gdp"].get(c) or {}).get(str(y))
                p = (oef["pop"].get(c) or {}).get(str(y))
                if g and p:
                    gsum += g
                    psum += p
            if gsum and psum:
                by_year[y] = gsum / psum
        gdp_pc[reg] = by_year

    print("\nTHE TREND, estimated rather than read off two endpoints")
    print("  ln(journey length) on a year term, region fixed effects, every year used. An "
          "endpoint\n  CAGR throws away eight of the ten observations and carries whatever "
          "happened in the\n  two it keeps.")
    trend = region_trend_table(reg_series, use)
    print(f"  {'region':<16}{'trend':>9}{'se':>8}{'shrunk':>9}{'2013-2019':>11}")
    for reg in sorted(trend["regions"]):
        t = trend["regions"][reg]
        pre_t = trend["pre2019"].get(reg)
        print(f"  {reg:<16}{t['trend'] * 100:>8.2f}%{t['se'] * 100:>7.2f}"
              f"{t['shrunk'] * 100:>8.2f}%"
              + (f"{pre_t * 100:>10.2f}%" if pre_t is not None else f"{'n/a':>11}"))
    print(f"  {'COMMON':<16}{trend['common'] * 100:>8.2f}%{trend['common_se'] * 100:>7.2f}")
    print(f"\n  One rate for every region is rejected: F({trend['F_df1']},{trend['F_df2']}) "
          f"= {trend['F']:.2f}, p = {trend['p']:.4f}. The regional differences are real on "
          f"this window.")
    print(f"  They are not stable across sub-windows. South Asia is "
          f"{trend['pre2019']['South Asia'] * 100:.2f}% on 2013-2019 and "
          f"{trend['regions']['South Asia']['trend'] * 100:.2f}% on the full window, "
          f"Northeast Asia {trend['pre2019']['Northeast Asia'] * 100:.2f}% and "
          f"{trend['regions']['Northeast Asia']['trend'] * 100:.2f}%. That instability is "
          f"why each\n  region's own estimate is pulled towards the common rate in "
          f"proportion to its precision,\n  at a weight of {trend['shrink_weight']:.2f} "
          f"read from the spread of the estimates and their standard error, not chosen.")

    print("\nTHE RELATIONSHIP: ln(average journey length) on ln(real GDP per head)")
    print("  Two elasticities, and they answer different questions. WITHIN is the same "
          "region\n  getting richer over time, which is what a forecast path needs. "
          "BETWEEN is richer\n  regions flying further than poorer ones at a point in "
          "time.")
    def build_groups(years):
        g, mx, my, lab = {}, [], [], []
        for reg, s in reg_series.items():
            if reg == "World":
                continue
            yy = [y for y in years if y in gdp_pc[reg] and y in s]
            if len(yy) < 3:
                continue
            g[reg] = ([math.log(gdp_pc[reg][y]) for y in yy],
                      [math.log(s[y]) for y in yy],
                      [float(y) for y in yy])
            mx.append(np.mean(g[reg][0]))
            my.append(np.mean(g[reg][1]))
            lab.append(reg)
        return g, mx, my, lab

    groups, xs, ys, labels = build_groups(use)
    w = within_ols(groups)
    wt = within_ols(groups, with_trend=True)
    pre = [y for y in use if y <= 2019]
    g_pre, _, _, _ = build_groups(pre)
    w_pre = within_ols(g_pre)
    wt_pre = within_ols(g_pre, with_trend=True)
    b_slope, _, b_r2 = ols(xs, ys)
    print(f"\n  WITHIN, region fixed effects, {w[3]} observations over {len(groups)} "
          f"regions")
    print(f"    income only          elasticity {w[0]:>6.3f}                       "
          f"R2 {w[2]:.3f}")
    print(f"    income and a trend   elasticity {wt[0]:>6.3f}   trend "
          f"{wt[1] * 100:>5.2f}% a year   R2 {wt[2]:.3f}")
    print(f"  WITHIN on {pre[0]}-{pre[-1]} only, the years before the pandemic break, "
          f"{w_pre[3]} observations")
    print(f"    income only          elasticity {w_pre[0]:>6.3f}                       "
          f"R2 {w_pre[2]:.3f}")
    print(f"    income and a trend   elasticity {wt_pre[0]:>6.3f}   trend "
          f"{wt_pre[1] * 100:>5.2f}% a year   R2 {wt_pre[2]:.3f}")
    print(f"  BETWEEN, region means, {len(labels)} regions: elasticity "
          f"{b_slope:.3f}, R2 {b_r2:.3f}")
    print(f"\n  {'region':<16}{'own elasticity':>16}{'R2':>8}{'observations':>14}")
    per_region = {}
    for reg, (x, yv, _t) in groups.items():
        sl, _, r2 = ols(x, yv)
        per_region[reg] = {"elasticity": sl, "r2": r2, "n": len(x)}
        print(f"  {reg:<16}{sl:>16.3f}{r2:>8.3f}{len(x):>14}")

    print("\nWHAT IT IMPLIES FOR THE FORECAST PATH")
    print("  Stage length growth = elasticity x forecast real GDP per head growth, so the "
          "path\n  is endogenous and decelerates as income growth does. Oxford Economics "
          "to 2050;\n  the last five years of their path carry the rate beyond it.")
    print(f"  {'region':<16}{'GDPpc 25-44':>13}{'income only':>13}{'plus trend':>12}"
          f"{'measured OAG':>14}{'km/seat 2025':>14}{'km/seat 2044':>14}")
    implied = {}
    wedge_sl = (json.load(open(a.wedge_json))["stage_length_by_boeing_region"]
                if os.path.isfile(a.wedge_json) else {})
    el_within, el_trend, common_trend = w[0], wt[0], wt[1]
    for reg in sorted(list(groups) + ["World"]):
        gp = gdp_pc.get(reg, {})
        if 2025 not in gp or 2044 not in gp:
            continue
        g_gdp = (gp[2044] / gp[2025]) ** (1 / 19) - 1
        applied = el_within * g_gdp
        applied_t = el_trend * g_gdp + common_trend
        meas = (wedge_sl.get(reg, {}).get("cagr", {}) or {}).get("2015-2025")
        km25 = (wedge_sl.get(reg, {}).get("km_per_seat", {}) or {}).get("2025")
        implied[reg] = {"gdp_pc_cagr": g_gdp, "applied_cagr": applied,
                        "applied_cagr_with_trend": applied_t, "measured_oag_cagr": meas}
        km44 = km25 * (1 + applied) ** 19 if km25 else None
        print(f"  {reg:<16}{g_gdp * 100:>12.2f}%{applied * 100:>12.2f}%"
              f"{applied_t * 100:>11.2f}%"
              + (f"{meas * 100:>13.2f}%" if meas is not None else f"{'n/a':>14}")
              + (f"{km25:>14,.0f}" if km25 else f"{'n/a':>14}")
              + (f"{km44:>14,.0f}" if km44 else f"{'n/a':>14}"))

    if a.json:
        json.dump({"years_used": use, "world_ajl": {str(y): wser[y] for y in use},
                   "panel_ajl": {str(y): panel_ajl[y] for y in use},
                   "panel_pairs": len(panel), "pairs_total": len(per_pair),
                   "region_ajl": {r: {str(y): s[y] for y in use}
                                  for r, s in reg_series.items()},
                   "region_trends": trend,
                   "elasticity_within": w[0], "elasticity_within_r2": w[2],
                   "elasticity_within_with_trend": wt[0], "trend_with_income": wt[1],
                   "elasticity_within_pre2019": w_pre[0],
                   "elasticity_within_pre2019_with_trend": wt_pre[0],
                   "trend_pre2019": wt_pre[1],
                   "elasticity_between": b_slope, "elasticity_between_r2": b_r2,
                   "per_region": per_region, "implied_path": implied},
                  open(a.json, "w"), indent=1)
        print(f"\nwritten: {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

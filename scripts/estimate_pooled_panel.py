"""The pooled panel fit: the instrument that completes the maturity architecture.

MEASUREMENTS 15 settled the architecture provisionally: the mature/emerging split is
unsupported by four discriminator tests, but per-country O&D fits are underpowered on
ten observations, so no evidenced replacement level existed. This is the instrument
named there: every country's O&D history in ONE regression,

    ln(pax_ct) = a_c + bG * ln(GDP_ct) + delta * post_covid + e_ct

with country fixed effects (within-transform), so circa 1,500 observations identify
the common income elasticity that ten could not, and interacted variants test the
split with power at last.

DECISION RULES, stated before any result (John's method, 23 August 2026):
  1. The SPLIT: estimate separate slopes for the mature and emerging groups exactly
     as the engine currently classifies countries (saturation weight at 0.5). If the
     group slopes differ significantly (p < 0.05) AND in the expected order
     (mature < emerging), the split is evidenced and its two levels are read from
     this fit. If not, the split collapses to a single elasticity at the pooled
     estimate.
  2. The LEVEL: whichever structure survives, the applied values scale so the
     traffic-weighted world aggregate equals the fitted value(s); the book's segment
     relativities (Domestic : Intl Short Haul : Long Haul) are preserved, because the
     panel is country-aggregate and cannot see segments.
  3. The FARE TERM: world real fare (data/fare_levels_exhibit.json) enters as a
     covariate. It varies only by year, so within-country it is identified only off
     the common time path and is expected to be confounded with GDP; if its
     coefficient is not significant with a sane sign, the affordability term stays
     OUT of the demand model with this run recorded as the reason, which closes the
     question rather than deferring it.
  4. Whatever the outcome, the effect on the forecast is measured through run_global
     before anything ships, John sees the numbers, and the band position is NOT a
     selection criterion, it is reported.

Also prints the 2018 diagnostic for the fare series (rows by source_year around the
kink) and the traffic-weighted sensitivity of the pooled fit.

Measurement only: nothing on disk changes. Runs where E: is local:

    py -3.12 scripts\\estimate_pooled_panel.py

Author: Avia Solutions. 23 August 2026.
"""
from __future__ import annotations
import csv
import json
import math
import os
import sys
from collections import defaultdict

import duckdb
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from avia_forecast.paths import DATA, PREAGG, QSI_APP, SABRE_DB
from avia_forecast.config import get

EXCLUDE_YEARS = (2020, 2021, 2022)


def build_panel():
    ref = os.path.join(QSI_APP, "reference_tables", "airport_city_country.csv")
    iso = {r["airport_code"].strip(): r["country_code"].strip()
           for r in csv.DictReader(open(ref, encoding="utf-8-sig"))}
    con = duckdb.connect(PREAGG, read_only=True)
    rows = con.execute("SELECT year, o, sum(pax) FROM od_p2p GROUP BY 1, 2").fetchall()
    con.close()
    series = defaultdict(lambda: defaultdict(float))
    for year, o, pax in rows:
        if int(year) in EXCLUDE_YEARS:
            continue
        c = iso.get(o)
        if c:
            series[c][int(year)] += pax
    gdp = json.load(open(os.path.join(DATA, "oef_gdp_pop_by_iso2.json")))["gdp"]

    fare = json.load(open(os.path.join(REPO, "data", "fare_levels_exhibit.json")))["world"]
    lnfare = {int(y): math.log(w["fare_real_usd_2024"]) for y, w in fare.items()
              if w.get("fare_real_usd_2024")}

    # maturity grouping EXACTLY as the engine classifies today (saturation weight >= 0.5)
    wb = json.load(open(os.path.join(REPO, "data", "worldbank_pop_gdppc.json")))["data"]
    base = json.load(open(os.path.join(REPO, "data", "global_base_od_2025.json")))
    meta = json.load(open(os.path.join(REPO, "data", "global_airport_meta_2025.json")))
    asym_tbl = get("propensity.region_asymptote_trips_pc")
    od25, regw = defaultdict(float), defaultdict(lambda: defaultdict(float))
    for iata, r in base.items():
        m = meta.get(iata, {})
        if m.get("country"):
            od25[m["country"]] += sum(r.values())
            regw[m["country"]][m.get("region")] += sum(r.values())

    def mature(c):
        rec = wb.get(c)
        if not (rec and rec.get("pop") and od25.get(c)):
            return None
        region = max(regw[c], key=regw[c].get)
        asym = asym_tbl.get(region, asym_tbl.get("default"))
        return ((od25[c] * 1e6 / rec["pop"]) / asym) >= 0.5

    panel = []
    for c, ys in series.items():
        g = gdp.get(c)
        m = mature(c)
        if not g or m is None:
            continue
        for y, p in ys.items():
            gv = g.get(str(y), g.get(y))
            if p > 0 and gv and gv > 0 and (int(y) in lnfare or True):
                panel.append({"c": c, "y": int(y), "lnp": math.log(p), "lng": math.log(gv),
                              "covid": 1.0 if int(y) >= 2023 else 0.0,
                              "lnf": lnfare.get(int(y)), "mature": m,
                              "w": od25.get(c, 1.0)})
    return panel


def within_ols(panel, xcols, weights=None):
    """Country-demeaned OLS. Returns coef, se (classical), n, and the R2 of the
    within regression. xcols: list of keys into each row."""
    byc = defaultdict(list)
    for r in panel:
        byc[r["c"]].append(r)
    Y, X, W = [], [], []
    for c, rows in byc.items():
        if len(rows) < 4:
            continue
        my = sum(r["lnp"] for r in rows) / len(rows)
        mx = [sum(r[k] for r in rows) / len(rows) for k in xcols]
        for r in rows:
            Y.append(r["lnp"] - my)
            X.append([r[k] - mx[j] for j, k in enumerate(xcols)])
            W.append(r["w"] if weights else 1.0)
    Y, X, W = np.array(Y), np.array(X), np.array(W)
    Xw = X * W[:, None]; Yw = Y * W
    beta, *_ = np.linalg.lstsq(Xw.T @ X, Xw.T @ Y, rcond=None)
    resid = Y - X @ beta
    dof = len(Y) - X.shape[1] - len(byc)
    s2 = float(resid @ (resid * W)) / max(dof, 1) / (W.mean())
    cov = s2 * np.linalg.inv(Xw.T @ X) @ (Xw.T @ Xw) @ np.linalg.inv(Xw.T @ X) \
        if weights else s2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    r2 = 1 - float(resid @ resid) / float(Y @ Y) if len(Y) else 0.0
    return beta, se, len(Y), len(byc), r2


def main():
    panel = build_panel()
    nm = sum(1 for r in panel if r["mature"])
    print(f"panel: {len(panel)} country-years, {len({r['c'] for r in panel})} countries "
          f"({nm} mature rows, {len(panel)-nm} emerging rows, engine classification)")

    # 1. pooled common elasticity
    b, se, n, nc, r2 = within_ols(panel, ["lng", "covid"])
    print(f"\n1. POOLED: bG {b[0]:.3f} (se {se[0]:.3f}, t {b[0]/se[0]:.1f})  "
          f"covid {b[1]:+.3f}  n={n} countries={nc}  within-R2 {r2:.3f}")
    bw, sew, *_ = within_ols(panel, ["lng", "covid"], weights=True)
    print(f"   traffic-weighted sensitivity: bG {bw[0]:.3f} (se {sew[0]:.3f})")

    # 2. the split test, with power at last
    for r in panel:
        r["lng_m"] = r["lng"] if r["mature"] else 0.0
        r["lng_e"] = r["lng"] if not r["mature"] else 0.0
    b2, se2, n2, nc2, r22 = within_ols(panel, ["lng_e", "lng_m", "covid"])
    diff = b2[0] - b2[1]
    sed = math.sqrt(se2[0] ** 2 + se2[1] ** 2)
    print(f"\n2. SPLIT TEST: bG_emerging {b2[0]:.3f} (se {se2[0]:.3f})  "
          f"bG_mature {b2[1]:.3f} (se {se2[1]:.3f})")
    print(f"   difference {diff:+.3f} (se {sed:.3f}, t {diff/sed:+.2f})  "
          f"[rule: split survives only if significant AND mature < emerging]")

    # 3. the fare term
    fp = [r for r in panel if r["lnf"] is not None]
    b3, se3, n3, nc3, r23 = within_ols(fp, ["lng", "lnf", "covid"])
    print(f"\n3. FARE TERM (world real fare, year-level covariate): "
          f"bG {b3[0]:.3f} (se {se3[0]:.3f})  bF {b3[1]:+.3f} (se {se3[1]:.3f}, "
          f"t {b3[1]/se3[1]:+.2f})  n={n3}")
    print("   [rule: enters the model only if significant with a sane negative sign; "
          "year-level identification is weak by construction and that is the point]")

    # 4. the 2018 fare-series diagnostic
    try:
        con = duckdb.connect(SABRE_DB, read_only=True)
        rows = con.execute("""
            SELECT year, source_year, count(*) AS n, sum(passengers) AS pax,
                   sum(CASE WHEN avg_total_fare_usd>0 THEN total_revenue_usd END)
                   / sum(CASE WHEN avg_total_fare_usd>0 THEN passengers END) AS fare
            FROM sabre WHERE year IN (2017, 2018, 2019) GROUP BY 1, 2 ORDER BY 1, 2""").fetchall()
        con.close()
        print("\n4. 2018 KINK DIAGNOSTIC (year, source_year, rows, pax m, avg fare USD):")
        for y, sy, nn, pax, fare in rows:
            print(f"   {y}  src {sy}  rows {nn:,}  pax {pax/1e6:8.1f}m  fare {fare:7.2f}")
        print("   [a 2018 fare out of line within one source_year and not the other "
              "names the file; in line in both says the market moved]")
    except Exception as e:
        print(f"\n4. 2018 diagnostic unavailable: {e}")

    print("\nNothing written. The decision applies through the book with this run "
          "cited, the forecast effect measured through run_global, and John's eyes "
          "on the numbers before any commit.")


if __name__ == "__main__":
    main()

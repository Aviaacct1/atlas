#!/usr/bin/env python3
"""Avia Solutions - BT2 launch-forecast model: train/export and standalone scorer.
Author: Avia Solutions. Version 1.0, 29 July 2026.

Train (this repo):   python3 bt2_model.py --train
Score (any repo):    from bt2_model import load, forecast
                     m = load("bt2_model.pkl")
                     f = forecast(m, route)   # dict, see FEATURES below

Model: capacity anchor. forecast_pax = seats_planned x exp(GBM median log O&D-per-seat).
Trained on 2,208 OAG-confirmed launches, cohorts 2016-2019 (bt2_experiments.log).
Accuracy (blind, leave-one-cohort-out): 51% of routes within +-20%, median error 19%;
tier A (iqr_log <= IQR_TIER_A): 79.5% within +-20%. FITTED (history known): 89.8%.
Requires scikit-learn (pin the version recorded in the pickle metadata).

FEATURES (route dict keys, all launch-conditioned i.e. the candidate's planned values):
  seats_ly   planned seats, both directions, for the forecast window (like-for-like)
  base_mkt   Sabre total O&D pax, latest full year, both directions
  capa       QSI capture at the candidate's planned frequency (0-1)
  freq       planned weekly frequency per direction
  legs_n     count of distinct scheduled legs touching either endpoint in the
             reference week (schedule density / hubness; BT2 stage-4 definition)
  months     months the route will operate in the forecast window (12 = full year)
  gcd        great-circle km
  typ        "LCC" or "FSC"
  dom        True if both endpoints in the same country
  gauge      planned seats per operation
  ncar       carriers expected on the pair (new launch = 1)
  launch_mon 1-12 calendar launch month
  qcx        connection-competition strength, BT2 definition:
             sum over both directions of S_online + 0.75*S_alliance + 0.25*S_interline
  mkt_growth base market growth, latest-year over year-before (1.0 if unknown)
  carrier    operating carrier IATA code (identity effect if >=15 launches in training)
"""
import argparse, math, pickle
import numpy as np

IQR_TIER_A = 0.088   # ex-ante tier-A cut: narrowest 10% of predicted log-IQR

def _vec(r, carid):
    return [math.log(r["seats_ly"]), math.log(r["base_mkt"]), r["capa"],
            math.log(max(r["freq"], .5)), math.log(1 + r["legs_n"]),
            math.log(r["months"]), math.log(max(r["gcd"], 100)),
            1.0 if r["typ"] == "LCC" else 0.0, 1.0 if r["dom"] else 0.0,
            r["gauge"], r["ncar"], math.log(r["seats_ly"] / r["base_mkt"]),
            int(r["launch_mon"]),
            math.log(1 + r["qcx"]),
            math.log(max(min(r.get("mkt_growth", 1.0), 5.0), 0.2)),
            carid.get(r.get("carrier", ""), 0)]

def load(path):
    with open(path, "rb") as f:
        return pickle.load(f)

# ---- v1.2 (bt2_model_v1_2.pkl) ----------------------------------------------
# Trained on cohorts 2016-2019 + 2025, mixed outturn basis (US domestic 2016-2019
# graded against US DOT DB1B, all else Sabre MIDT). FIVE additional route keys are
# required beyond the v1.0/v1.1 FEATURES list:
#   base_seats_a   launching carrier's departing seats at endpoint a, pre-launch month
#   base_seats_b   same at endpoint b
#   airport_seats_a  ALL carriers' departing seats at endpoint a, same month
#   airport_seats_b  same at endpoint b
#   sister_flag    True if the metro-pair (city-pair) already had an established
#                  nonstop at sister airports (>1,500 pax in the prior year)
# Accuracy (bt2_experiments.log, 5 Aug 2026): blind LOCO 53.7% within +-20%
# (Sabre basis; US-vs-DOT 50.1%); fitted (light-reg) 88.8%. Tier A = narrowest 10%
# predicted IQR with sister_flag demoted: 75.4% blind within +-20% (67.1% on the
# 2025-only era test) - ship as the confidence band, not as a route-level claim.

def forecast_v12(m, route):
    """v1.2 scorer. route needs the v1.0 FEATURES keys plus the five v1.2 keys above."""
    f = _vec(route, m["carid"])
    sa, sb = route["base_seats_a"], route["base_seats_b"]
    ta, tb = route["airport_seats_a"], route["airport_seats_b"]
    f += [math.log1p(min(sa, sb)), math.log1p(max(sa, sb)),
          (sa/ta if ta else 0), (sb/tb if tb else 0),
          1.0 if route.get("sister_flag") else 0.0]
    x = np.array([f])
    p50 = float(m["q50"].predict(x)[0]); p25 = float(m["q25"].predict(x)[0])
    p75 = float(m["q75"].predict(x)[0])
    iqr = p75 - p25
    tier = "A" if (iqr <= 0.090 and not route.get("sister_flag")) else "B"
    return {"pax": route["seats_ly"] * math.exp(p50),
            "lo": route["seats_ly"] * math.exp(p25),
            "hi": route["seats_ly"] * math.exp(p75),
            "iqr_log": iqr, "tier": tier}

def forecast(m, route):
    """Returns dict: pax, lo (q25), hi (q75), iqr_log, tier ('A' or 'B')."""
    x = np.array([_vec(route, m["carid"])])
    p50 = float(m["q50"].predict(x)[0]); p25 = float(m["q25"].predict(x)[0])
    p75 = float(m["q75"].predict(x)[0])
    iqr = p75 - p25
    return {"pax": route["seats_ly"] * math.exp(p50),
            "lo": route["seats_ly"] * math.exp(p25),
            "hi": route["seats_ly"] * math.exp(p75),
            "iqr_log": iqr, "tier": "A" if iqr <= IQR_TIER_A else "B"}

def train():
    import sklearn
    from sklearn.ensemble import HistGradientBoostingRegressor
    import bt2_lib as B
    from bt2_gbm import rows, carid
    X = np.array([_vec({**r, "launch_mon": int(r["launch_month"][5:7]),
                        "carrier": r["oag_carrier"]}, carid) for r in rows])
    y = np.array([math.log(r["actual"] / r["seats_ly"]) for r in rows])
    m = {"carid": carid, "version": "1.0 29Jul2026", "author": "Avia Solutions",
         "sklearn": sklearn.__version__, "n_train": len(rows), "iqr_tier_a": IQR_TIER_A,
         "provenance": "BT2 monthly-cohort backtest, cohorts 2016-2019, C:\\Avia\\bt2; "
                       "blind 51.0% within +-20% (LOCO), tier-A 79.5%, fitted 89.8%"}
    for q, nm in ((0.5, "q50"), (0.25, "q25"), (0.75, "q75")):
        g = HistGradientBoostingRegressor(loss="quantile", quantile=q, learning_rate=0.04,
              max_iter=600, max_leaf_nodes=31, min_samples_leaf=60,
              l2_regularization=5.0, random_state=7)
        g.fit(X, y); m[nm] = g
    with open("bt2_model.pkl", "wb") as f:
        pickle.dump(m, f)
    # self-test round trip
    m2 = load("bt2_model.pkl")
    r0 = rows[0]
    rt = {**r0, "launch_mon": int(r0["launch_month"][5:7]), "carrier": r0["oag_carrier"]}
    out = forecast(m2, rt)
    print(f"trained n={len(rows)} sklearn={m['sklearn']}; self-test {r0['a']}-{r0['b']} "
          f"{r0['cohort']}: fc {out['pax']:.0f} vs actual {r0['actual']:.0f} tier {out['tier']}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--train", action="store_true")
    if ap.parse_args().train: train()

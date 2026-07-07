"""Synthetic worked examples with known truth (Elasticity Design v0.1 section 7).

This is the estimation module's first test case: generate a cell with known true
elasticities and confirm the machinery recovers truth and that T1-T6 behave as
documented. The UK pilot repeats the exercise on real CAA data.

Data-generating process (7.1):
  true bG = 1.30, bF = -0.60; 26 years (2000-2025); a 2008-09 fuel spike in fares;
  a GFC dip in GDP; a pandemic collapse to 45% of trend in 2020-2022; 5%
  multiplicative noise.
The 2013 base-opening variant (7.2) adds a permanent +85% level shift with no
change in GDP or fares.

Author: Avia Solutions.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

TRUE_BG = 1.30
TRUE_BF = -0.60
PANDEMIC_FACTOR = 0.45          # gamma_true = ln(0.45) = -0.799
NOISE_SD_LOG = 0.05             # 5% multiplicative noise
BASE_OPEN_YEAR = 2013
BASE_OPEN_UPLIFT = 0.85         # +85% permanent

YEARS = list(range(2000, 2026))


def _gdp_index() -> pd.Series:
    """Real GDP index, 2000=100, ~2.8%/yr trend with a GFC dip and a modest
    pandemic macro dip (the demand collapse beyond GDP is carried by the dummy)."""
    g = {y: 0.028 for y in YEARS}
    g[2008], g[2009] = 0.004, -0.035          # global financial crisis
    g[2020], g[2021] = -0.045, 0.060          # pandemic macro dip then rebound
    idx, level = {}, 100.0
    for y in YEARS:
        if y > 2000:
            level *= (1.0 + g[y])
        idx[y] = level
    return pd.Series(idx)


def _fare_index() -> pd.Series:
    """Real fare index, 2000=100. Gentle real-yield decline with a 2008-09 fuel
    spike that then unwinds; this fuel-driven variation is largely independent of
    GDP and is what identifies the fare elasticity."""
    f = {y: -0.005 for y in YEARS}            # structural real-yield decline
    f[2008], f[2009] = 0.130, 0.060           # fuel spike into fares
    f[2010], f[2011] = -0.100, -0.050         # unwind
    idx, level = {}, 100.0
    for y in YEARS:
        if y > 2000:
            level *= (1.0 + f[y])
        idx[y] = level
    return pd.Series(idx)


def make_clean_cell(seed: int = 0, base_pax: float = 4_000_000.0) -> pd.DataFrame:
    """Section 7.1: the airport that earns its own elasticities."""
    rng = np.random.default_rng(seed)
    G = _gdp_index()
    F = _fare_index()
    g0, f0 = G.iloc[0], F.iloc[0]
    rows = []
    for y in YEARS:
        pandemic = PANDEMIC_FACTOR if y in (2020, 2021, 2022) else 1.0
        noise = float(np.exp(rng.normal(0.0, NOISE_SD_LOG)))
        P = base_pax * (G[y] / g0) ** TRUE_BG * (F[y] / f0) ** TRUE_BF * pandemic * noise
        rows.append({"year": y, "P": P, "G": G[y], "F": F[y]})
    return pd.DataFrame(rows)


def make_base_opening_cell(seed: int = 0, base_pax: float = 4_000_000.0) -> pd.DataFrame:
    """Section 7.2: same cell plus a 2013 low-cost base opening, +85% permanent,
    with no change in GDP or fares. Also returns the E2013 event dummy column."""
    df = make_clean_cell(seed=seed, base_pax=base_pax)
    df["E2013"] = (df["year"] >= BASE_OPEN_YEAR).astype(float)
    df["P"] = df["P"] * np.where(df["year"] >= BASE_OPEN_YEAR, 1.0 + BASE_OPEN_UPLIFT, 1.0)
    return df


# ---- Fare-elasticity strategy proof (Fable Part B.4) ----

def _fare_cost_path():
    """Cost-driven ('normal-supply') fare index: gentle real-yield decline with a
    2008 fuel spike and the clean 2014-16 oil collapse that carries identification."""
    import numpy as np
    f = {y: -0.005 for y in YEARS}
    f[2008], f[2009] = 0.130, 0.060           # fuel spike (contaminated by GFC)
    f[2010], f[2011] = -0.100, -0.050
    f[2014], f[2015] = -0.120, -0.060         # clean oil collapse, stable demand
    f[2016] = 0.020
    idx, level = {}, 100.0
    for y in YEARS:
        if y > 2000:
            level *= (1.0 + f[y])
        idx[y] = level
    return __import__("pandas").Series(idx)


def make_fare_anomaly_cell(seed: int = 0, base_pax: float = 4_000_000.0):
    """A cell whose 2020-24 OBSERVED fares are supply-anomalous by construction,
    while demand followed 'normal-supply' (cost-driven) fares. Returns a frame with
    both fare series so the strategy can be proven: naive estimation on observed
    fares mis-estimates bF; the recipe (counterfactual estimation series + the
    D_supply dummy) recovers it.

    Anomaly: 2020 fire-sale fares; 2021-24 supply-constrained fare premium (GTF
    groundings, maintenance backlogs). Demand is depressed 2020-22 (pandemic) and
    mildly supply-suppressed 2023-24, independent of the observed fare spike."""
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(seed)
    G = _gdp_index()
    F_cost = _fare_cost_path()          # = estimation ('normal') fares
    g0, f0 = G.iloc[0], F_cost.iloc[0]
    anomaly = {2020: 0.70, 2021: 1.28, 2022: 1.32, 2023: 1.22, 2024: 1.10}
    rows = []
    for y in YEARS:
        pandemic = PANDEMIC_FACTOR if y in (2020, 2021, 2022) else 1.0
        supply = 0.93 if y in (2023, 2024) else 1.0    # mild supply suppression of demand
        noise = float(np.exp(rng.normal(0.0, NOISE_SD_LOG)))
        # demand responds to NORMAL fares, not the observed anomaly
        P = base_pax * (G[y]/g0)**TRUE_BG * (F_cost[y]/f0)**TRUE_BF * pandemic * supply * noise
        F_obs = F_cost[y] * anomaly.get(y, 1.0)
        rows.append({"year": y, "P": P, "G": G[y], "F_est": F_cost[y], "F_obs": F_obs})
    return pd.DataFrame(rows)

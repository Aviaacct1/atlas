"""Level 1 airport-cell estimation (Method Spec 4.3, Elasticity Design 2;
Fable Part B restricted regression). Author: Avia Solutions.

Two anomaly dummies come from the assumptions book: D_covid (2020-2022, demand
collapse) and D_supply (2023-2024, revenge demand against GTF/maintenance-
constrained supply). They are opposite-signed, so they are separate dummies.

Production Level 1 is a RESTRICTED regression (Fable Part B.1.3): the fare
elasticity is fixed at its segment value and the airport regression estimates the
income elasticity on the fare-adjusted series

    ln P - bF_seg * ln F = alpha + bG ln G + gamma D_covid + gamma_s D_supply + sum delta_k E_k + e

which removes the collinearity that was distorting airport bG. The unrestricted
fit_cell is retained for diagnostics and for the synthetic worked example.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
import statsmodels.api as sm

from ..config import get

_DUMMY_YEARS = {"covid": "estimation.pandemic_years", "supply": "estimation.supply_anomaly_years"}


@dataclass
class Level1Fit:
    bG: float
    bF: float
    gamma: float                 # D_covid coefficient
    se_bG: float
    se_bF: float
    t_bG: float
    t_bF: float
    r2: float
    durbin_watson: float
    n_obs: int
    resid: np.ndarray
    spec_used: list = field(default_factory=list)
    event_shift: dict = field(default_factory=dict)
    supply_gamma: float = float("nan")   # D_supply coefficient
    fare_fixed: bool = False             # True for the restricted production fit


def _index_to_base(series: pd.Series) -> pd.Series:
    return series / series.iloc[0] * get("estimation.index_base_value")


def _dummy_frame(d: pd.DataFrame, dummies) -> pd.DataFrame:
    cols = {}
    for name in dummies:
        years = set(get(_DUMMY_YEARS[name]))
        cols[{"covid": "D", "supply": "DS"}[name]] = d["year"].isin(years).astype(float)
    return pd.DataFrame(cols, index=d.index)


def _finish(model, d, event_cols, bG_key, bF_value, spec, fare_fixed):
    resid = np.asarray(model.resid)
    dw = float(np.sum(np.diff(resid) ** 2) / np.sum(resid ** 2))
    shifts = {c: float(np.exp(model.params[c]) - 1.0) for c in event_cols}
    return Level1Fit(
        bG=float(model.params[bG_key]),
        bF=(float(model.params["lnF"]) if bF_value is None else float(bF_value)),
        gamma=float(model.params.get("D", float("nan"))),
        se_bG=float(model.bse[bG_key]),
        se_bF=(float(model.bse["lnF"]) if bF_value is None else float("nan")),
        t_bG=float(model.tvalues[bG_key]),
        t_bF=(float(model.tvalues["lnF"]) if bF_value is None else float("nan")),
        r2=float(model.rsquared),
        durbin_watson=dw,
        n_obs=int(model.nobs),
        resid=resid,
        spec_used=spec,
        event_shift=shifts,
        supply_gamma=float(model.params.get("DS", float("nan"))),
        fare_fixed=fare_fixed,
    )


def fit_cell(df: pd.DataFrame, event_cols=None, dummies=("covid",)) -> Level1Fit:
    """Unrestricted diagnostic fit: estimates bG and bF. df columns: year, P, G, F."""
    event_cols = list(event_cols or [])
    d = df.sort_values("year").reset_index(drop=True).copy()
    lnP = np.log(_index_to_base(d["P"]))
    lnG = np.log(_index_to_base(d["G"]))
    lnF = np.log(_index_to_base(d["F"]))
    X = pd.DataFrame({"lnG": lnG, "lnF": lnF})
    X = pd.concat([X, _dummy_frame(d, dummies)], axis=1)
    for c in event_cols:
        X[c] = d[c].astype(float)
    X = sm.add_constant(X)
    model = sm.OLS(lnP, X).fit(cov_type="HC3")
    spec = ["lnG", "lnF"] + [{"covid": "D", "supply": "DS"}[x] for x in dummies] + event_cols
    return _finish(model, d, event_cols, "lnG", None, spec, fare_fixed=False)


def fit_cell_restricted(df: pd.DataFrame, bF_segment: float, event_cols=None,
                        dummies=("covid", "supply")) -> Level1Fit:
    """Restricted production fit (Fable Part B.1.3): bF fixed at the segment value;
    estimate bG on the fare-adjusted series ln P - bF*ln F."""
    event_cols = list(event_cols or [])
    d = df.sort_values("year").reset_index(drop=True).copy()
    lnP = np.log(_index_to_base(d["P"]))
    lnG = np.log(_index_to_base(d["G"]))
    lnF = np.log(_index_to_base(d["F"]))
    y = lnP - bF_segment * lnF
    X = pd.DataFrame({"lnG": lnG})
    X = pd.concat([X, _dummy_frame(d, dummies)], axis=1)
    for c in event_cols:
        X[c] = d[c].astype(float)
    X = sm.add_constant(X)
    model = sm.OLS(y, X).fit(cov_type="HC3")
    spec = ["lnG(restricted)"] + [{"covid": "D", "supply": "DS"}[x] for x in dummies] + event_cols
    return _finish(model, d, event_cols, "lnG", bF_segment, spec, fare_fixed=True)

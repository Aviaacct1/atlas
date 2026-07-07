"""coherence - sense checks on the forecast shape (Method Spec 8.2). Author: Avia Solutions.

Two checks, both reported not raised (a coherence flag is analyst evidence, not a
build stop): rolling-decade CAGR must sit inside a plausible band, and the model's
long-run growth is compared with an external reference (Boeing GMF / Airbus GMF).
Per John (6 July) external alignment is a horizon GOAL, not a constraint: the check
reports the divergence, it never forces the model onto the OEM number.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from ..config import get


def cagr(v0: float, v1: float, years: int) -> float:
    if v0 <= 0 or v1 <= 0 or years <= 0:
        return float("nan")
    return (v1 / v0) ** (1.0 / years) - 1.0


def rolling_decade_cagrs(series: dict, span: int = 10):
    """Every `span`-year CAGR in the series, as [(start, end, cagr), ...]."""
    yrs = sorted(series)
    out = []
    for y in yrs:
        if y + span in series:
            out.append((y, y + span, cagr(series[y], series[y + span], span)))
    return out


@dataclass
class CoherenceResult:
    windows: list                    # (start, end, cagr)
    flags: list = field(default_factory=list)   # windows outside the band
    ok: bool = True


def check_rolling_cagr(series: dict, span: int = 10,
                       lo: float | None = None, hi: float | None = None) -> CoherenceResult:
    """Flag any rolling-decade CAGR outside the plausible band (Method Spec 8.2).
    Reported, not raised."""
    lo = get("coherence.rolling_decade_cagr_min") if lo is None else lo
    hi = get("coherence.rolling_decade_cagr_max") if hi is None else hi
    windows = rolling_decade_cagrs(series, span)
    flags = [w for w in windows if w[2] == w[2] and (w[2] < lo or w[2] > hi)]
    return CoherenceResult(windows, flags, ok=(not flags))


@dataclass
class DivergenceResult:
    model_cagr: float
    external_cagr: float
    gap_pp: float                    # model minus external, percentage points
    within_goal: bool                # inside the soft goal band (reporting only)


def external_divergence(series: dict, external_cagr: float,
                        goal_band_pp: float = 0.5) -> DivergenceResult:
    """Compare the model's whole-horizon CAGR with an external reference (Boeing/
    Airbus). Reporting only: within_goal marks whether the model sits inside a soft
    band of the OEM figure, but nothing acts on it - alignment is a horizon goal per
    John, and the coherence report simply states the gap."""
    yrs = sorted(series)
    m = cagr(series[yrs[0]], series[yrs[-1]], yrs[-1] - yrs[0]) if len(yrs) >= 2 else float("nan")
    gap_pp = (m - external_cagr) * 100.0
    return DivergenceResult(m, external_cagr, gap_pp, abs(gap_pp) <= goal_band_pp)

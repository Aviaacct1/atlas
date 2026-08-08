"""shocks/resilience - premium traffic through demand shocks (Ben Leon question,
23 July 2026).

The module measures, for each shock, how far demand fell from its pre-shock peak
and how long it took to recover to that peak, then turns the observed falls and
recoveries into a forward shock template the forecast engine can apply to a
hypothetical future shock. It runs on any ordered demand series, so premium and
economy are measured on the same basis and compared.

Licensing. The premium/economy split is estimated from Sabre GDD, which is class
C and used for internal parameter estimation only (see ingest/sabre.py). What the
product displays is a demand index rebased to 100 at the pre-shock peak,
reconciled to class-A totals, never raw Sabre passenger counts. An index is also
the correct analytical form here: it puts every shock on one scale, so the depth
of the fall and the length of the recovery are comparable across events.

Onset labels below are historical event dates, not data claims. Depth and
recovery for each shock are read from the supplied series, never asserted.

Author: Avia Solutions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class Shock:
    """A demand shock, identified by the period label at which it begins.

    onset must be a period label that exists in the series index (an annual label
    such as "2001", or a monthly label such as "2001-09"). The window used to
    measure trough and recovery runs from onset up to the next shock's onset, or
    to the end of the series for the last shock.
    """
    name: str
    onset: str
    note: str = ""


# Event markers for the shocks Ben asked about. Onset years are the well-known
# event dates; the fall and recovery for each are computed from the data.
DEFAULT_SHOCKS: list[Shock] = [
    Shock("Gulf War", "1990", "Iraq invasion of Kuwait, Aug 1990"),
    Shock("9/11", "2001", "11 September 2001 attacks"),
    Shock("SARS", "2003", "SARS outbreak"),
    Shock("Global financial crisis", "2008", "from Sep 2008"),
    Shock("COVID-19", "2020", "from Mar 2020"),
]


def _as_pairs(series: Mapping[str, float] | Sequence[tuple[str, float]]):
    """Coerce a series to an ordered list of (period, value) pairs.

    A mapping keeps insertion order (Python 3.7+); a sequence of pairs is taken
    as given. Order is the caller's responsibility and is treated as the time
    axis.
    """
    if hasattr(series, "items"):
        return list(series.items())
    return list(series)


def to_index(series: Mapping[str, float], base_period: str) -> dict[str, float]:
    """Rebase a series to 100 at base_period. Raises if the base value is zero or
    the base period is absent."""
    pairs = _as_pairs(series)
    lookup = dict(pairs)
    if base_period not in lookup:
        raise KeyError(f"base_period {base_period!r} is not in the series")
    base = lookup[base_period]
    if base == 0:
        raise ValueError("base_period value is zero; cannot rebase to an index")
    return {p: 100.0 * v / base for p, v in pairs}


def _index_of(periods: list[str], label: str) -> int:
    try:
        return periods.index(label)
    except ValueError as exc:
        raise KeyError(f"onset {label!r} is not in the series index") from exc


def resilience_metrics(
    series: Mapping[str, float],
    shocks: Iterable[Shock] = DEFAULT_SHOCKS,
    *,
    recovery_ratio: float = 1.0,
    recovery_window: str = "to_end",
) -> list[dict]:
    """Measure the fall and recovery around each shock.

    For each shock the pre-shock peak is the highest level reached between the
    previous shock's onset and this onset. The trough is the lowest level from
    this onset up to the next onset (or the end), so it is attributed to this
    shock and not to a later one. Recovery is the first period at or after the
    trough where the level returns to recovery_ratio times the peak.

    recovery_window controls how far the recovery is searched. "to_end" (the
    default) searches to the end of the series, which answers "how long did it
    take to come back to the pre-shock level", the natural read even when a later
    shock intervenes. "to_next" bounds the search at the next shock's onset.

    Returns one row per shock present in the series, with the depth of the fall
    as a fraction of the peak and the number of periods peak-to-trough,
    trough-to-recovery and peak-to-recovery. recovered is False where the series
    has not returned to the peak within the search window.
    """
    if recovery_window not in ("to_end", "to_next"):
        raise ValueError("recovery_window must be 'to_end' or 'to_next'")
    pairs = _as_pairs(series)
    periods = [p for p, _ in pairs]
    values = [float(v) for _, v in pairs]

    present = [s for s in shocks if s.onset in periods]
    onsets = [_index_of(periods, s.onset) for s in present]

    rows: list[dict] = []
    for k, shock in enumerate(present):
        onset_i = onsets[k]
        prev_i = onsets[k - 1] if k > 0 else 0
        next_i = onsets[k + 1] if k + 1 < len(present) else len(periods)

        # pre-shock peak: highest level from the previous onset up to this onset
        peak_slice = range(prev_i, onset_i + 1)
        peak_i = max(peak_slice, key=lambda i: values[i])
        peak_v = values[peak_i]

        # trough: lowest level from this onset up to the next onset (or the end)
        window = range(onset_i, next_i)
        trough_i = min(window, key=lambda i: values[i])
        trough_v = values[trough_i]

        drop_frac = (peak_v - trough_v) / peak_v if peak_v else None

        # recovery: first period at or after the trough back to the peak level
        target = recovery_ratio * peak_v
        search_end = len(periods) if recovery_window == "to_end" else next_i
        recovery_i = None
        for i in range(trough_i, search_end):
            if values[i] >= target:
                recovery_i = i
                break

        rows.append({
            "shock": shock.name,
            "onset": shock.onset,
            "note": shock.note,
            "peak_period": periods[peak_i],
            "peak_value": peak_v,
            "trough_period": periods[trough_i],
            "trough_value": trough_v,
            "drop_frac": drop_frac,
            "periods_peak_to_trough": trough_i - peak_i,
            "recovered": recovery_i is not None,
            "recovery_period": periods[recovery_i] if recovery_i is not None else None,
            "periods_trough_to_recovery": (recovery_i - trough_i) if recovery_i is not None else None,
            "periods_peak_to_recovery": (recovery_i - peak_i) if recovery_i is not None else None,
        })
    return rows


def compare_premium_economy(
    premium: Mapping[str, float],
    economy: Mapping[str, float],
    shocks: Iterable[Shock] = DEFAULT_SHOCKS,
    *,
    recovery_ratio: float = 1.0,
) -> list[dict]:
    """Run resilience_metrics on premium and economy and merge shock-by-shock,
    with the premium-minus-economy differences in fall depth and recovery length.

    A positive drop_frac_diff means premium fell further. A positive
    recovery_diff means premium took longer periods to return to its own
    pre-shock peak. Rows are keyed on the shock name.
    """
    shocks = list(shocks)
    prem = {r["shock"]: r for r in resilience_metrics(premium, shocks, recovery_ratio=recovery_ratio)}
    econ = {r["shock"]: r for r in resilience_metrics(economy, shocks, recovery_ratio=recovery_ratio)}

    rows: list[dict] = []
    for s in shocks:
        p, e = prem.get(s.name), econ.get(s.name)
        if p is None or e is None:
            continue
        drop_diff = (p["drop_frac"] - e["drop_frac"]) if (p["drop_frac"] is not None and e["drop_frac"] is not None) else None
        rec_diff = (
            p["periods_peak_to_recovery"] - e["periods_peak_to_recovery"]
            if (p["periods_peak_to_recovery"] is not None and e["periods_peak_to_recovery"] is not None)
            else None
        )
        rows.append({
            "shock": s.name,
            "onset": s.onset,
            "premium_drop_frac": p["drop_frac"],
            "economy_drop_frac": e["drop_frac"],
            "drop_frac_diff": drop_diff,
            "premium_periods_to_recovery": p["periods_peak_to_recovery"],
            "economy_periods_to_recovery": e["periods_peak_to_recovery"],
            "recovery_diff": rec_diff,
            "premium_recovered": p["recovered"],
            "economy_recovered": e["recovered"],
        })
    return rows


def forward_shock_template(
    metrics_rows: Sequence[Mapping],
    *,
    path_length: int | None = None,
) -> dict:
    """Build a forward shock overlay from the observed falls and recoveries.

    Averages, across the shocks that recovered, the depth of the fall and the
    number of periods peak-to-trough and trough-to-recovery, then draws a
    normalised path indexed to 100 at the pre-shock peak: a linear decline to the
    mean trough, then an exponential return to 100 over the mean recovery length.
    The path is a working template for a hypothetical future shock, to be scaled
    and dated per scenario, not a forecast of any specific event.

    Returns the mean parameters, the sample size, and the normalised path as a
    list of index values starting at the peak (100.0).
    """
    used = [r for r in metrics_rows if r.get("recovered") and r.get("drop_frac") is not None]
    n = len(used)
    if n == 0:
        return {"n": 0, "mean_drop_frac": None, "mean_periods_to_trough": None,
                "mean_periods_to_recovery": None, "path": []}

    mean_drop = sum(r["drop_frac"] for r in used) / n
    mean_ptt = sum(r["periods_peak_to_trough"] for r in used) / n
    mean_ttr = sum(r["periods_trough_to_recovery"] for r in used) / n

    ptt = max(1, round(mean_ptt))
    ttr = max(1, round(mean_ttr))
    total = path_length if path_length is not None else ptt + ttr

    trough_level = 100.0 * (1.0 - mean_drop)
    path: list[float] = []
    for t in range(total + 1):
        if t <= ptt:
            level = 100.0 - (100.0 - trough_level) * (t / ptt)
        else:
            # exponential approach from the trough back to 100 over ttr periods
            frac = min(1.0, (t - ptt) / ttr)
            level = trough_level + (100.0 - trough_level) * (1.0 - (1.0 - frac) ** 2)
        path.append(round(level, 3))

    return {
        "n": n,
        "mean_drop_frac": mean_drop,
        "mean_periods_to_trough": mean_ptt,
        "mean_periods_to_recovery": mean_ttr,
        "path": path,
    }

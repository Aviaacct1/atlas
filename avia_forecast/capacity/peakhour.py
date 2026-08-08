"""capacity/peakhour - peak hour share estimation and projection
(Capacity Method and Evidence Record v0.4, section 11.1). Author: Avia Solutions.

The peak hour share of annual traffic is not a constant and must not be read off
one year and held flat. It falls as an airport grows: traffic spreads into the
shoulder hours because the peak is full, aircraft upgauge, and the schedule
matures. Holding the share flat brings every constraint forward and overstates
the capacity requirement everywhere.

Two rules this module exists to respect.

1. At a peak-constrained airport the filed peak equals the declared coordination
   parameter almost by construction. Such an airport tells us about the
   declaration, not about demand, so it is excluded from the estimation sample.
   It still carries a projected share of its own; it just does not inform the
   relationship.

2. The panel supplies the ELASTICITY (how share moves with size). The airport
   supplies the LEVEL, from its own observed base-year share, wherever that
   observation is unconstrained. Imposing a cross-sectional level on an airport
   with idiosyncratic structure is the commoner and larger error.

Functional form, fitted by ordinary least squares in logs across the panel:

    ln(peak_hour) = ln a + b ln(annual) + c intl_share + d seasonality

so the share, peak_hour / annual, is proportional to annual^(b - 1) and declines
for b < 1. Every numeric threshold is read from the assumptions book; nothing is
hard coded here.

This module does NOT compute the peak hour itself. Peak hour rates arrive from
the DDFS convention catalogue on a named convention (v0.4 section 10) and are
consumed here. The convention name travels with the fit so a resolution can
never silently mix two conventions.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math

import numpy as np

from ..config import get


# --------------------------------------------------------------------------
# Panel observations
# --------------------------------------------------------------------------

@dataclass
class PeakObs:
    """One airport-year of the schedule panel, on a single named convention.

    annual_pax_m     annual passengers, m
    peak_hour_pax    passengers in the design peak hour, absolute
    intl_share       international share of annual passengers, 0-1
    seasonality      peak-month share of annual traffic, 0-1 (1/12 = flat)
    constrained      True where the filed peak is set by a declared parameter
    """
    iata: str
    year: int
    annual_pax_m: float
    peak_hour_pax: float
    intl_share: float = 0.0
    seasonality: float = 1.0 / 12.0
    constrained: bool = False
    convention: str = ""
    #: movements alongside the passenger basis, so the airfield test and the
    #: constrained flag can use the same panel without a second pass
    peak_hour_mvts: float = 0.0
    annual_mvts: float = 0.0

    @property
    def share(self) -> float:
        """Observed peak hour share of annual traffic."""
        if self.annual_pax_m <= 0:
            return float("nan")
        return self.peak_hour_pax / (self.annual_pax_m * 1e6)


@dataclass
class PeakShareFit:
    convention: str
    ln_a: float
    b: float                      # elasticity of peak hour to annual traffic
    c: float                      # international share coefficient
    d: float                      # seasonality coefficient
    n_obs: int
    n_airports: int
    r2: float
    resid_sd: float
    fitted_ok: bool               # False => the fit is not usable as estimated
    se_b: float = float("nan")    # standard error of b, clustered by airport
    fallback_used: bool = False   # True only where the book elasticity replaced the fit
    excluded: dict = field(default_factory=dict)
    notes: str = ""

    @property
    def share_elasticity(self) -> float:
        """d ln(share) / d ln(annual). Negative where the peak grows more slowly
        than annual traffic, which is the expected sign."""
        return self.b - 1.0


# --------------------------------------------------------------------------
# Sample construction
# --------------------------------------------------------------------------

def filter_sample(obs, convention: str | None = None):
    """Split the panel into the estimation sample and the exclusions, with a
    reason recorded against every dropped observation.

    Exclusions, all thresholds from the book:
      constrained     the filed peak is set by a declared parameter (rule 1)
      below_floor     annual traffic below the floor, where the peak is erratic
      bad_value       non-positive or non-finite annual or peak
      convention      a different convention from the one being fitted
      thin_airport    fewer than the minimum airport-years after the above
    """
    floor = float(get("peak_hour.min_annual_pax_m", 0.25))
    min_years = int(get("peak_hour.min_obs_per_airport", 3))

    kept, excluded = [], {}

    def drop(o, reason):
        excluded.setdefault(reason, []).append((o.iata, o.year))

    for o in obs:
        if convention and o.convention and o.convention != convention:
            drop(o, "convention")
        elif o.constrained:
            drop(o, "constrained")
        elif not (math.isfinite(o.annual_pax_m) and math.isfinite(o.peak_hour_pax)) \
                or o.annual_pax_m <= 0 or o.peak_hour_pax <= 0:
            drop(o, "bad_value")
        elif o.annual_pax_m < floor:
            drop(o, "below_floor")
        else:
            kept.append(o)

    counts = {}
    for o in kept:
        counts[o.iata] = counts.get(o.iata, 0) + 1
    thin = {i for i, n in counts.items() if n < min_years}
    if thin:
        kept2 = []
        for o in kept:
            if o.iata in thin:
                drop(o, "thin_airport")
            else:
                kept2.append(o)
        kept = kept2

    return kept, excluded


# --------------------------------------------------------------------------
# Estimation
# --------------------------------------------------------------------------

def fit_peak_share(obs, convention: str | None = None) -> PeakShareFit:
    """Fit the panel relationship. Falls back to the book elasticity, flagged,
    where the sample is too thin or the fit is not usable. Never raises: a bad
    fit is a flagged output, not an exception, so the pipeline reports it."""
    convention = convention or str(get("peak_hour.convention", "busy_30th"))
    fallback_b = float(get("peak_hour.fallback_elasticity", 0.90))
    min_r2 = float(get("peak_hour.min_r2", 0.80))
    min_obs = int(get("peak_hour.min_obs_total", 30))

    kept, excluded = filter_sample(obs, convention)
    n_airports = len({o.iata for o in kept})

    def fallback(note):
        return PeakShareFit(convention=convention, ln_a=float("nan"), b=fallback_b,
                            c=0.0, d=0.0, n_obs=len(kept), n_airports=n_airports,
                            r2=float("nan"), resid_sd=float("nan"), fitted_ok=False,
                            se_b=float("nan"), fallback_used=True,
                            excluded={k: len(v) for k, v in excluded.items()}, notes=note)

    if len(kept) < min_obs:
        return fallback(f"sample of {len(kept)} below the minimum of {min_obs}; "
                        f"book fallback elasticity {fallback_b} in use")

    y = np.array([math.log(o.peak_hour_pax) for o in kept], dtype=float)
    X = np.column_stack([
        np.ones(len(kept)),
        np.array([math.log(o.annual_pax_m * 1e6) for o in kept], dtype=float),
        np.array([o.intl_share for o in kept], dtype=float),
        np.array([o.seasonality for o in kept], dtype=float),
    ])

    try:
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    except np.linalg.LinAlgError:
        return fallback("least squares did not converge; book fallback elasticity in use")

    resid = y - X @ beta
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    dof = max(1, len(kept) - X.shape[1])
    resid_sd = math.sqrt(ss_res / dof)

    ln_a, b, c, d = (float(v) for v in beta)

    # Standard error of b. Within a size class the spread of log annual traffic is
    # narrow, so r2 falls even where the slope is well determined; the standard error
    # is the diagnostic that survives narrowing the range, and it is what tells you
    # whether two classes really differ.
    # pinv rather than inv: where a covariate is constant across the sample, as
    # seasonality is at a single-season airport, X.T X is singular and inv would give
    # up entirely. The pseudo-inverse still returns the slope's own variance.
    try:
        xtx_inv = np.linalg.pinv(X.T @ X)
        se_b = float(math.sqrt(max(0.0, resid_sd ** 2 * float(xtx_inv[1, 1]))))
    except Exception:
        se_b = float("nan")

    notes = ""
    ok, used_fallback = True, False
    if not (0.0 < b < 1.0):
        ok, used_fallback = False, True
        notes = (f"estimated elasticity {b:.3f} outside (0, 1), which would imply the "
                 f"peak growing faster than annual traffic; book fallback {fallback_b} in use")
        b = fallback_b
    elif math.isfinite(r2) and r2 < min_r2:
        ok = False
        notes = (f"fit r2 of {r2:.3f} below the book minimum of {min_r2}. The ESTIMATE IS "
                 f"STILL USED; within a narrow size class r2 falls because the spread of "
                 f"annual traffic is small, so read the standard error of b rather than r2")

    return PeakShareFit(convention=convention, ln_a=ln_a, b=b, c=c, d=d,
                        n_obs=len(kept), n_airports=n_airports, r2=r2,
                        resid_sd=resid_sd, fitted_ok=ok, se_b=se_b,
                        fallback_used=used_fallback,
                        excluded={k: len(v) for k, v in excluded.items()}, notes=notes)


# --------------------------------------------------------------------------
# Application
# --------------------------------------------------------------------------

def fitted_share(fit: PeakShareFit, annual_pax_m: float,
                 intl_share: float = 0.0, seasonality: float = 1.0 / 12.0) -> float:
    """Cross-sectional share from the fit alone. Used only where an airport has
    no usable unconstrained observation of its own to anchor on."""
    if annual_pax_m <= 0 or not math.isfinite(fit.ln_a):
        return float("nan")
    annual = annual_pax_m * 1e6
    ln_peak = fit.ln_a + fit.b * math.log(annual) + fit.c * intl_share + fit.d * seasonality
    return math.exp(ln_peak) / annual


def project_share(fit: PeakShareFit, base_share: float, base_annual_m: float,
                  target_annual_m: float) -> float:
    """Project an airport's own observed share forward on the panel elasticity:

        share(target) = share(base) x (annual_target / annual_base) ^ (b - 1)

    The airport supplies the level, the panel supplies the slope (rule 2). The
    result is floored at the book minimum so the projection cannot decay to an
    implausible share over a long horizon."""
    if base_annual_m <= 0 or target_annual_m <= 0 or not math.isfinite(base_share):
        return float("nan")
    share = base_share * (target_annual_m / base_annual_m) ** fit.share_elasticity
    floor = get("peak_hour.projection_floor_share")
    if floor is not None:
        share = max(float(floor), share)
    return share


def share_path(fit: PeakShareFit, base_share: float, base_annual_m: float,
               annual_path: dict) -> dict:
    """Year-indexed share path from a year-indexed annual traffic path."""
    return {y: project_share(fit, base_share, base_annual_m, a)
            for y, a in annual_path.items()}


@dataclass
class Anchor:
    share: float
    basis: str        # "observed" | "fitted"
    reason: str


def anchor_share(fit: PeakShareFit, base_annual_m: float,
                 observed_share: float | None, constrained: bool,
                 intl_share: float = 0.0, seasonality: float = 1.0 / 12.0) -> Anchor:
    """Choose the level to project from, and say which was used and why.

    A constrained airport's observed share reflects its declared parameter and
    not its demand, so the fitted level is used instead. This is the circularity
    guard: without it, the peak of a Level 3 airport would be projected forward
    from the very constraint the test is meant to detect."""
    if observed_share is not None and math.isfinite(observed_share) and observed_share > 0 \
            and not constrained:
        return Anchor(observed_share, "observed",
                      "unconstrained observation available, airport supplies the level")
    reason = ("peak set by a declared parameter, so the observed share reports the "
              "declaration and not demand") if constrained else "no usable observation"
    return Anchor(fitted_share(fit, base_annual_m, intl_share, seasonality), "fitted", reason)


def flag_capped_from_panel(obs, tol: float | None = None) -> set:
    """Airports whose peak hour reports a ceiling rather than demand, to be excluded
    from the estimation sample under rule 1.

    Derived from capacity_screen so there is ONE rule rather than two. An earlier
    version carried its own copy and, on the first full-set run, excluded 813 airports
    while the screen called 43. Two rules for the same question will always drift, and
    the drift shows up as a number that looks reasonable.
    """
    return {r.iata for r in capacity_screen(obs) if r.state in ("at_ceiling", "tightening")}


@dataclass
class ScreenRow:
    iata: str
    first_year: int
    last_year: int
    annual_mvts: float          # last observed year
    peak_hour_mvts: float       # last observed year
    annual_growth: float        # across the observed window
    peak_growth: float
    absorption: float           # peak growth as a share of annual growth
    share: float                # peak hour share of annual passengers, last year
    state: str                  # at_ceiling | tightening | headroom | too_short
    note: str = ""


def capacity_screen(obs) -> list:
    """Classify every airport in the panel by how its peak hour has behaved.

    This exists because the capacity register will take months to populate and the
    forecast needs something in the meantime for the airports nobody has looked at.
    It needs no declared rate: it reads how an airport has actually responded to its
    own growth.

      at_ceiling   a large airport whose peak hour has not moved. There is nowhere
                   left to put a flight in the busy hour.
      tightening   annual traffic still growing, but the peak is absorbing little of
                   it, so the growth is going into the shoulders. This is what an
                   airport approaching its ceiling looks like before it reaches one.
      headroom     the peak is growing roughly in step with annual traffic, so the
                   busy hour is not the binding thing yet.

    `absorption` is the number to read: peak hour growth divided by annual growth.
    Near 1 the airport is still taking growth in the peak. Near 0 it is not.

    This matters as much for the airports with room as for the ones without. When a
    constrained airport spills traffic, the engine has to send it somewhere in the
    catchment, and it can only do that if it knows which neighbours have headroom.
    A screen of the largest few hundred airports cannot answer that; the whole set can.

    Behavioural, not institutional, and weaker than a coordinator's declaration. It is
    a starting position for airports the register has not reached, and it should be
    overwritten wherever a declared rate exists.
    """
    static = float(get("peak_hour.capped_static_growth", 0.02))
    tol = float(get("peak_hour.capped_growth_ratio", 0.35))
    # Two different floors, because they answer two different questions. A STATIC peak
    # only means a ceiling at a large airport, so the ceiling call keeps the high floor.
    # But "does this airport have room" is a fair question far lower down, and it is the
    # question that matters for spill: when a hub fills up the engine has to know which
    # of its neighbours can take the traffic, and those neighbours are not all large.
    ceiling_floor = float(get("peak_hour.capped_size_floor_mvts", 150000))
    screen_floor = float(get("peak_hour.screen_min_mvts", 20000))

    by: dict = {}
    for o in obs:
        if getattr(o, "annual_mvts", 0) > 0 and getattr(o, "peak_hour_mvts", 0) > 0:
            by.setdefault(o.iata, []).append(o)

    out = []
    for iata, rows in sorted(by.items()):
        rows = sorted(rows, key=lambda o: o.year)
        if len(rows) < 2:
            out.append(ScreenRow(iata, rows[0].year, rows[0].year, rows[0].annual_mvts,
                                 rows[0].peak_hour_mvts, float("nan"), float("nan"),
                                 float("nan"), rows[0].share, "too_short",
                                 "one observed year, no trend to read"))
            continue
        first, last = rows[0], rows[-1]
        ann_g = last.annual_mvts / first.annual_mvts - 1.0
        peak_g = last.peak_hour_mvts / first.peak_hour_mvts - 1.0
        # Absorption is peak growth over annual growth, so it is meaningless when the
        # denominator is near zero, which is precisely the case at a saturated airport.
        # Heathrow grew 1% in movements across 2015 to 2019; a 0.65% fall in its peak
        # then reads as an absorption of -0.65, which says nothing. Reported as not
        # meaningful rather than as a number, and never used in the classification.
        absorption = (peak_g / ann_g) if abs(ann_g) > static else float("nan")
        size = max(first.annual_mvts, last.annual_mvts)
        big, assessable = size >= ceiling_floor, size >= screen_floor

        if not assessable:
            # Below the screen floor the busy hour is a handful of movements, so a year
            # on year change in it is noise. Saying nothing is the honest output; the
            # register will have to look at these one by one if they ever matter.
            state, note = "not_assessed", "below the screen floor, peak too small to read a trend"
        elif big and abs(peak_g) < static:
            state, note = "at_ceiling", "large airport, peak hour static across the window"
        elif ann_g > static and peak_g < tol * ann_g:
            state, note = "tightening", "growth going into the shoulder hours, not the peak"
        elif ann_g <= static:
            state, note = "headroom", "traffic broadly flat, nothing to read into the peak"
        else:
            state, note = "headroom", "peak growing broadly in step with annual traffic"

        out.append(ScreenRow(iata, first.year, last.year, last.annual_mvts,
                             last.peak_hour_mvts, ann_g, peak_g, absorption,
                             last.share, state, note))
    return out


@dataclass
class CurvedFit:
    """Elasticity as a smooth function of size rather than as steps.

    Fitted 3 August 2026 after the class table showed a gradient the classes could not
    resolve. Adjacent classes were not separable (5m to 15m against 15m to 40m gave
    t = 1.6; 15m to 40m against 40m and above gave t = 1.5) while the ends of the range
    were emphatically so (t = 4.7). That is the signature of a continuous relationship
    being forced through arbitrary boundaries: each step is inside the noise, the trend
    across them is not, and an airport at 14.9m passengers gets a different parameter
    from one at 15.1m for no reason in the data.

    Model:  ln(peak) = a + b1 ln(annual) + b2 ln(annual)^2 + c intl + d seasonality
    so the elasticity at any size is  b1 + 2 b2 ln(annual),  which varies smoothly.
    """
    convention: str
    a: float
    b1: float
    b2: float
    c: float
    d: float
    n_obs: int
    n_airports: int
    r2: float
    se_b2: float
    fitted_ok: bool
    notes: str = ""

    def elasticity_at(self, annual_pax_m: float) -> float:
        """Elasticity of peak hour to annual traffic at a given airport size."""
        if annual_pax_m <= 0:
            return float("nan")
        return self.b1 + 2.0 * self.b2 * math.log(annual_pax_m * 1e6)

    def share_elasticity_at(self, annual_pax_m: float) -> float:
        return self.elasticity_at(annual_pax_m) - 1.0


def fit_curved(obs, convention: str | None = None) -> CurvedFit:
    """Fit the elasticity as a smooth function of size. Use this in preference to the
    step classes: it removes the boundaries, which the data does not support."""
    convention = convention or str(get("peak_hour.convention", "busy_30th"))
    kept, _ = filter_sample(obs, convention)
    if len(kept) < int(get("peak_hour.min_obs_total", 30)):
        return CurvedFit(convention, *([float("nan")] * 5), len(kept),
                         len({o.iata for o in kept}), float("nan"), float("nan"), False,
                         "sample too thin for a curved fit")
    lnA = np.array([math.log(o.annual_pax_m * 1e6) for o in kept], dtype=float)
    y = np.array([math.log(o.peak_hour_pax) for o in kept], dtype=float)
    X = np.column_stack([np.ones(len(kept)), lnA, lnA ** 2,
                         np.array([o.intl_share for o in kept], dtype=float),
                         np.array([o.seasonality for o in kept], dtype=float)])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    dof = max(1, len(kept) - X.shape[1])
    resid_sd = math.sqrt(ss_res / dof)
    try:
        se_b2 = float(math.sqrt(max(0.0, resid_sd ** 2 * float(np.linalg.pinv(X.T @ X)[2, 2]))))
    except Exception:
        se_b2 = float("nan")
    a, b1, b2, c, d = (float(v) for v in beta)
    ok = math.isfinite(se_b2) and abs(b2) > 2 * se_b2
    note = ("" if ok else "the curvature term is not distinguishable from zero; a single "
                          "elasticity is adequate on this sample")
    return CurvedFit(convention, a, b1, b2, c, d, len(kept),
                     len({o.iata for o in kept}), r2, se_b2, ok, note)


SIZE_CLASSES = [("under 1m", 0.0, 1.0), ("1m to 5m", 1.0, 5.0), ("5m to 15m", 5.0, 15.0),
                ("15m to 40m", 15.0, 40.0), ("40m and above", 40.0, float("inf"))]


def fit_by_size_class(obs, convention: str | None = None) -> dict:
    """Fit the relationship separately within each size class.

    A single log-linear line is being asked to describe airports from a quarter of a
    million passengers to eighty million, and it does not. A small airport runs one or
    two banks a day, so its peak hour share is structurally higher and behaves
    differently from a hub whose traffic is already spread across the day. Fitting one
    line across the whole range produces a slope that belongs to no part of it, and the
    answer moves with whichever end of the range happens to dominate the sample.

    Read this before choosing a single b. For capacity work the elasticity that matters
    is the one at the sizes where constraints actually bite.
    """
    out = {}
    for label, lo, hi in SIZE_CLASSES:
        sub = [o for o in obs if lo <= o.annual_pax_m < hi]
        if sub:
            out[label] = fit_peak_share(sub, convention)
    return out


def describe(fit: PeakShareFit) -> str:
    """One-paragraph plain-English account of the fit, for the drill-down and the
    assumptions log. Generated, not typed."""
    if not fit.fitted_ok:
        return (f"Peak hour share projected on the assumptions-book fallback elasticity of "
                f"{fit.b:.3f} against the {fit.convention} convention. {fit.notes}")
    return (f"Peak hour share projected on an elasticity of {fit.b:.3f} of peak hour "
            f"passengers to annual passengers, fitted across {fit.n_obs:,} airport-years "
            f"for {fit.n_airports:,} airports on the {fit.convention} convention, r2 "
            f"{fit.r2:.3f}. Peak-constrained airports are excluded from the estimation "
            f"sample because their filed peak reports the declared parameter rather than "
            f"demand. Share therefore falls as traffic grows, at "
            f"{fit.share_elasticity:.3f} per unit of log annual traffic."
            + (f" {fit.notes}" if fit.notes else ""))

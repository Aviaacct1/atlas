"""capacity/constrain - the end to end wiring: schedules to a constrained forecast.
Author: Avia Solutions.

Everything else in capacity/ is a part. This is the part that joins them, so there is
one place to read to see how a forecast becomes a constrained forecast:

    schedules  ->  peak hour panel        (ingest.oag_peak)
               ->  elasticity             (capacity.peakhour.fit_peak_share)
               ->  share path per airport (capacity.peakhour.project_share)
               ->  capacity tests         (capacity.evidence.resolve)
               ->  binding year and K     with a range, not a point
               ->  spill and retention    (capacity.spill.airport_solve)

Three things this module exists to keep true.

1. The share is anchored on the airport's OWN observed base year wherever that
   observation is unconstrained, and on the fitted level where it is not. A slot
   constrained airport's filed peak reports its declaration rather than its demand,
   so projecting from it would carry the constraint into the thing meant to detect it.

2. The binding year is reported as a RANGE. The share is projected, not observed, and
   its median error against a held out year is 15%. Capacity moves inversely with the
   share, so that is a 15% error on capacity, which at 3% growth is about 4.7 years on
   the binding year. A single year is not supported by the evidence.

3. Nothing downstream changes. capacity_for() hands spill.airport_solve a practical
   capacity in pax/yr exactly as the v0.1 register loader did.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from ..config import get
from . import evidence, peakhour, spill


@dataclass
class ConstrainedAirport:
    iata: str
    resolution: evidence.Resolution
    share_path: dict                    # year -> projected peak hour share
    share_basis: str                    # observed | fitted
    share_reason: str
    capacity: dict = field(default_factory=dict)        # year -> m pax, rises as the share falls
    unconstrained: dict = field(default_factory=dict)   # year -> m pax
    constrained: dict = field(default_factory=dict)     # year -> m pax after spill
    spill: dict = field(default_factory=dict)           # year -> m pax that cannot be accommodated

    @property
    def binding_year(self):
        return self.resolution.binding_year

    @property
    def binding_range(self):
        return (self.resolution.binding_year_early, self.resolution.binding_year_late)


def build_share_path(fit: peakhour.PeakShareFit, base_obs, demand: dict,
                     constrained_airport: bool = False):
    """Project an airport's peak hour share across the forecast years.

    Returns (path, basis, reason). The elasticity comes from the panel; the LEVEL comes
    from the airport itself wherever its base year is unconstrained, because imposing a
    cross sectional level on an airport with its own structure is the larger error.
    """
    anchor = peakhour.anchor_share(
        fit, base_obs.annual_pax_m,
        observed_share=base_obs.share,
        constrained=constrained_airport or base_obs.constrained,
        intl_share=base_obs.intl_share, seasonality=base_obs.seasonality)
    path = peakhour.share_path(fit, anchor.share, base_obs.annual_pax_m, demand)
    return path, anchor.basis, anchor.reason


def constrain_airport(iata: str, observations, demand: dict, base_obs,
                      fit: peakhour.PeakShareFit, committed_steps=None,
                      seats_per_mvt: float | None = None,
                      load_factor: float | None = None) -> ConstrainedAirport:
    """One airport, from an unconstrained demand path to a constrained one."""
    share, basis, reason = build_share_path(fit, base_obs, demand)
    res = evidence.resolve(iata, observations, demand, share,
                           seats_per_mvt=seats_per_mvt, load_factor=load_factor,
                           committed_steps=committed_steps)

    out = ConstrainedAirport(iata=iata, resolution=res, share_path=share,
                             share_basis=basis, share_reason=reason,
                             unconstrained=dict(demand))
    # K per YEAR, not one K held flat. The rate based tests turn an hourly declaration
    # into an annual figure through the peak hour share, and the share falls as the
    # airport grows, so the same runway carries more passengers a year later on. Using
    # a single K would discard the entire elasticity result.
    k_by_year = evidence.capacity_by_year(res)
    out.capacity = {y: k / 1e6 for y, k in k_by_year.items()}
    fallback_K = evidence.capacity_for(res)
    for y, u in demand.items():
        K = k_by_year.get(y, fallback_K)
        solve = spill.airport_solve(u * 1e6, K)
        out.constrained[y] = solve.C / 1e6
        out.spill[y] = solve.spill / 1e6
    return out


def constrain_all(observations, demand_by_airport: dict, panel, fit,
                  base_year: int | None = None, committed_steps_by_airport=None):
    """Every airport in one pass. demand_by_airport is {iata: {year: m pax}}.

    Airports with no usable base observation are returned unconstrained and flagged,
    which is the honest treatment: the tool should say it does not know rather than
    assume an airport has room.
    """
    base_year = base_year or max(o.year for o in panel)
    base = {o.iata: o for o in panel if o.year == base_year}
    steps = committed_steps_by_airport or {}
    out, skipped = {}, {}
    for iata, demand in demand_by_airport.items():
        b = base.get(iata)
        if b is None or b.share <= 0:
            skipped[iata] = f"no usable peak hour observation in {base_year}"
            continue
        out[iata] = constrain_airport(iata, observations, demand, b, fit,
                                      committed_steps=steps.get(iata))
    return out, skipped


def capacity_requirement(results: dict, year: int) -> float:
    """Total traffic in a given year that cannot be accommodated, m pax.

    This is the number the product sells: not the forecast, but how much of it the
    infrastructure cannot take. Summing spill across a region or the world gives the
    capacity requirement, which is the sentence that starts a capital programme
    conversation.
    """
    return sum(r.spill.get(year, 0.0) for r in results.values())


def headroom_ranking(results: dict, year: int, limit: int = 25):
    """Airports with the most unused capacity in a given year, most first.

    The other half of the picture, and the one a top-200 view cannot give. When a hub
    fills up the engine has to send the spilt traffic somewhere in the catchment, and
    it can only do that if it knows which neighbours have room.
    """
    rows = []
    for iata, r in results.items():
        K = r.capacity.get(year, evidence.capacity_for(r.resolution) / 1e6) * 1e6
        if K <= 0:
            continue
        used = r.constrained.get(year, 0.0) * 1e6
        rows.append((iata, (K - used) / 1e6, used / K if K else float("nan")))
    rows.sort(key=lambda t: -t[1])
    return rows[:limit]

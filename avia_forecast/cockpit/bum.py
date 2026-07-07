"""cockpit/bum - the 2-year bottom-up model (Cockpit build update C).

A route x airline x aircraft-variant x weekly-frequency x load-factor schedule for
the base year and the year after. The base year is legitimately analyst-editable
because ingest is two schedule snapshot weeks: the gap between the base-year pax
input and the schedule total is shown and attributed by reason code, never
silently rescaled (C2). Aircraft come from the operating carrier's own fleet, and
upgauging recalculates pax at that carrier's gauge (C3). QSI candidates are
deduplicated against the schedule and reconciled to the model total (C5). The
BUM-implied near-term growth anchors BY+1 and tapers to the long-term model path
over N years, before the constrained pass, so the two methods merge without a
spike (C6). Author: Avia Solutions.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from ..config import get


@dataclass
class RouteLine:
    route: str            # e.g. "MAN-JFK"
    airline: str
    variant: str          # aircraft variant, e.g. "A321neo"
    seats: int
    weekly_freq: float
    load_factor: float
    year: int
    reason_code: str = ""  # SCHED-GAP / LF-REVISION / LAUNCH / WITHDRAWAL where analyst-set

    def annual_pax(self) -> float:
        """Departing passengers per year (C1)."""
        return self.weekly_freq * get("bum.weeks_per_year") * self.seats * self.load_factor


def schedule_total(lines, year=None) -> float:
    return sum(l.annual_pax() for l in lines if year is None or l.year == year)


# ---- C2: base-year gap, shown and attributed, never rescaled ----

@dataclass
class GapAttribution:
    base_year_pax_input: float
    schedule_total: float
    attributions: dict = field(default_factory=dict)   # reason_code -> pax

    @property
    def gap(self) -> float:
        return self.base_year_pax_input - self.schedule_total

    @property
    def unattributed(self) -> float:
        return self.gap - sum(self.attributions.values())


def base_year_gap(lines, base_year, pax_input) -> GapAttribution:
    """Show the gap; attributions are supplied by the analyst with reason codes. The
    schedule is never rescaled to force a match."""
    return GapAttribution(pax_input, schedule_total(lines, base_year))


# ---- C3: airline-specific fleets and upgauging ----

def carrier_fleet(fleet_ref: dict, airline: str) -> dict:
    """Only the operating carrier's variants are offered (C3)."""
    return fleet_ref.get(airline, {})


def upgauge(line: RouteLine, new_variant: str, fleet_ref: dict) -> RouteLine:
    """Change the aircraft to another variant in the SAME carrier's fleet and
    recompute pax at that carrier's gauge."""
    fleet = carrier_fleet(fleet_ref, line.airline)
    if new_variant not in fleet:
        raise ValueError(f"{new_variant} is not in {line.airline}'s fleet.")
    return RouteLine(line.route, line.airline, new_variant, fleet[new_variant],
                     line.weekly_freq, line.load_factor, line.year, "UPGAUGE")


# ---- C5: QSI candidate dedup and reconciliation ----

def qsi_dedup(candidates, schedule_routes):
    """Cross out QSI candidates already present in the schedule (manual adds), to
    avoid double counting."""
    present = set(schedule_routes)
    return [c for c in candidates if c not in present]


def reconcile_adds(added_pax: float, model_total: float, tol=None) -> bool:
    """True if the analyst's adds keep the schedule within tolerance of the model
    total; a wider gap raises a warning flag (C5)."""
    tol = get("bum.reconcile_wide_gap_pct") if tol is None else tol
    return abs(added_pax) <= tol * max(1.0, model_total)


# ---- C6: blend BUM growth into the long-term model path ----

def blend(model_path: dict, bum_by1: float, base_year: int, n_years=None) -> dict:
    """Anchor the level at BY+1 to the BUM value, then taper the ratio to the model
    path over n_years (default from the book), before the constrained pass."""
    n = get("bum.blend_years_default") if n_years is None else n_years
    by1 = base_year + 1
    ratio = bum_by1 / model_path[by1] if model_path[by1] else 1.0
    out = {}
    for y in sorted(model_path):
        if y < by1:
            out[y] = model_path[y]
        elif y <= by1 + n:
            w = max(0.0, 1.0 - (y - by1) / n)           # 1 at BY+1, 0 at BY+1+n
            out[y] = model_path[y] * (1.0 + (ratio - 1.0) * w)
        else:
            out[y] = model_path[y]
    return out


# ---- C7: telemetry (ingest-vs-reality gaps; public side of G-V) ----

def telemetry_summary(lines) -> dict:
    """Aggregate analyst reason-code records (SCHED-GAP, LF-REVISION, ...) as dated
    evidence of ingest-vs-reality gaps. Ingest quality, not client data, so it sits
    on the public side of guard G-V."""
    out = {}
    for l in lines:
        if l.reason_code:
            out[l.reason_code] = out.get(l.reason_code, 0) + 1
    return out

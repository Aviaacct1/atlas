"""scope/selection - the airport-set rule (Phase 1 global roll-out; John's rule).

Include an airport in the modelled set if it clears the pax floor (2m) OR falls
within the smallest set of largest airports that together make up the national
coverage target (80%) of that country's passengers. Every below-scope airport in
a country collapses into one residual pseudo-airport so national totals stay whole.
A standing goal floor (500k) is reported as a coverage gap, not applied in v1.

All thresholds are read from the assumptions book (config, not code). The rule is
data-source agnostic: it operates on any table of (iata, country, annual pax), so
it runs identically on CAA, Sabre or OAG once each country's traffic is loaded.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from ..config import get


@dataclass
class AirportScope:
    iata: str
    country: str
    pax: float
    included: bool
    reason: str            # "floor" | "coverage" | "residual"
    goal_gap: bool         # excluded but above the goal floor (standing ambition to add)


@dataclass
class CountryScope:
    country: str
    national_pax: float
    modelled: list = field(default_factory=list)     # AirportScope, included
    residual_iata: str = ""
    residual_pax: float = 0.0
    residual_count: int = 0
    coverage: float = 0.0                             # modelled pax / national pax
    goal_gap_count: int = 0                           # below-scope airports above the goal floor


def _params(inclusion_floor, coverage_target, goal_floor, suffix):
    return (
        get("scope.inclusion_floor_pax") if inclusion_floor is None else inclusion_floor,
        get("scope.national_coverage_target") if coverage_target is None else coverage_target,
        get("scope.goal_floor_pax") if goal_floor is None else goal_floor,
        get("scope.residual_pseudo_suffix") if suffix is None else suffix,
    )


def select_country(country: str, airports: list[tuple[str, float]],
                   inclusion_floor=None, coverage_target=None,
                   goal_floor=None, suffix=None) -> CountryScope:
    """Apply the rule to one country's airports [(iata, pax), ...].

    Coverage set: sort descending, include from the top until cumulative pax first
    reaches the coverage target (so the crossing airport is in). Union that with
    every airport at or above the pax floor. The rest form the residual pseudo."""
    floor, target, goal, suf = _params(inclusion_floor, coverage_target, goal_floor, suffix)
    ordered = sorted(airports, key=lambda t: t[1], reverse=True)
    national = float(sum(p for _, p in ordered))

    covered = set()
    if national > 0:
        cum = 0.0
        for iata, pax in ordered:
            covered.add(iata)
            cum += pax
            if cum / national >= target:
                break                              # crossing airport included, then stop

    modelled, residual_pax, residual_count, goal_gap_count = [], 0.0, 0, 0
    for iata, pax in ordered:
        by_floor = pax >= floor
        by_cov = iata in covered
        if by_floor or by_cov:
            reason = "floor" if by_floor else "coverage"
            modelled.append(AirportScope(iata, country, pax, True, reason, False))
        else:
            residual_pax += pax
            residual_count += 1
            gap = pax >= goal
            if gap:
                goal_gap_count += 1
            # individual excluded airports are not returned; they live in the residual

    cov = (sum(a.pax for a in modelled) / national) if national > 0 else 0.0
    return CountryScope(
        country=country, national_pax=national, modelled=modelled,
        residual_iata=(country + suf) if residual_count else "",
        residual_pax=residual_pax, residual_count=residual_count,
        coverage=cov, goal_gap_count=goal_gap_count,
    )


def select_airports(rows: list[tuple[str, str, float]], **kw) -> dict[str, CountryScope]:
    """Apply the rule across many countries. rows = [(iata, country, pax), ...].
    Returns {country: CountryScope}."""
    by_country: dict[str, list[tuple[str, float]]] = {}
    for iata, country, pax in rows:
        by_country.setdefault(country, []).append((iata, float(pax)))
    return {c: select_country(c, aps, **kw) for c, aps in by_country.items()}

"""cockpit/pack - the override-pack schema (Cockpit build update A1-A4).

Every input is an annual PATH (a vector over BY..horizon), never a scalar. The UI
shorthand expands to a vector at pack level:
  - a number            -> HOLD flat at that value
  - "a>b"               -> RAMP linearly from a at BY to b at the horizon
  - None / "engine"     -> FOLLOW the engine's endogenous evolution (fallback)
  - {year: value}       -> an explicit vector
Inputs carry (input x segment) grain where segmentation exists; a blank segment
falls back to the engine value (A2). A client path replaces the engine's
endogenous drift for that input (A3). Assumptions-book values take project-local,
reason-coded overrides that flow through the fare index but never write back to the
book (A4, guard G-V). Author: Avia Solutions.
"""
from __future__ import annotations
from dataclasses import dataclass, field

FOLLOW_ENGINE = "engine"        # sentinel: use the engine's endogenous value


def parse_spec(spec):
    """Normalise a UI shorthand into ('HOLD', v) | ('RAMP', a, b) | ('FOLLOW',) | ('VECTOR', dict)."""
    if spec is None or spec == FOLLOW_ENGINE:
        return ("FOLLOW",)
    if isinstance(spec, dict):
        return ("VECTOR", {int(k): float(v) for k, v in spec.items()})
    if isinstance(spec, str) and ">" in spec:
        a, b = spec.split(">")
        return ("RAMP", float(a), float(b))
    return ("HOLD", float(spec))


def expand(spec, years, base_year, engine_fn=None) -> dict:
    """Expand a path spec to {year: value} over `years`. RAMP interpolates linearly
    from a at BY to b at the horizon (last year). FOLLOW defers to engine_fn(year)."""
    kind = parse_spec(spec)
    horizon = years[-1]
    if kind[0] == "HOLD":
        return {y: kind[1] for y in years}
    if kind[0] == "RAMP":
        a, b = kind[1], kind[2]
        span = (horizon - base_year) or 1
        return {y: a + (b - a) * (y - base_year) / span for y in years}
    if kind[0] == "VECTOR":
        vec = kind[1]
        return {y: vec.get(y, engine_fn(y) if engine_fn else 0.0) for y in years}
    # FOLLOW
    if engine_fn is None:
        raise ValueError("FOLLOW spec needs an engine value function (endogenous drift).")
    return {y: engine_fn(y) for y in years}


def has_client_path(spec) -> bool:
    """A3: an explicit client path (not FOLLOW) replaces the engine's endogenous drift."""
    return parse_spec(spec)[0] != "FOLLOW"


def resolve_segmented(input_spec, segments, years, base_year, engine_fn) -> dict:
    """A2: resolve an (input x segment) input to {segment: {year: value}}. input_spec
    may be a single spec (applies to every segment) or {segment: spec}; a missing or
    blank segment falls back to the engine value for that segment via engine_fn(seg, y)."""
    out = {}
    per_seg = isinstance(input_spec, dict) and any(s in input_spec for s in segments)
    for seg in segments:
        spec = input_spec.get(seg) if per_seg else input_spec
        if spec is None:                       # blank segment -> engine fallback
            out[seg] = {y: engine_fn(seg, y) for y in years}
        else:
            out[seg] = expand(spec, years, base_year, engine_fn=lambda y, s=seg: engine_fn(s, y))
    return out


@dataclass
class BookOverride:
    """A4: a project-local, reason-coded override of an assumptions-book value. It is
    applied to the run and never written back to the book (guard G-V)."""
    param: str
    spec: object                    # path spec (number / "a>b" / vector / FOLLOW)
    reason_code: str
    rationale: str = ""
    provenance: str = "project"     # never 'public'; cannot promote to a vintage


PERMITTED_BOOK_OVERRIDES = {"tau", "jet_fuel_outlook", "carbon_price", "saf_blend",
                            "aircraft_efficiency", "lcc_fares_share"}


@dataclass
class Pack:
    """An override pack: input paths, segmented inputs, and reason-coded book
    overrides. Provenance is 'project' for a bespoke-client pack, 'public' for a
    global-sandbox pack; the vintage-purity guard G-V keeps project packs out of the
    product vintage."""
    name: str
    provenance: str = "project"
    inputs: dict = field(default_factory=dict)          # input_name -> spec or {segment: spec}
    book_overrides: dict = field(default_factory=dict)  # param -> BookOverride

    def add_book_override(self, ov: BookOverride):
        if ov.param not in PERMITTED_BOOK_OVERRIDES:
            raise ValueError(f"{ov.param} is not a permitted project-local book override.")
        self.book_overrides[ov.param] = ov

    def effective_book_value(self, param, book_value, years, base_year, engine_fn=None):
        """A4: the run value for a book parameter = its project override if present,
        else the book value. The book itself is never mutated here."""
        if param in self.book_overrides:
            return expand(self.book_overrides[param].spec, years, base_year, engine_fn)
        return {y: book_value for y in years}

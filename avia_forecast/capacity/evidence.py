"""capacity/evidence - the two-table capacity evidence record and the resolution
layer (Capacity Method and Evidence Record v0.4, sections 2, 3, 4, 5, 6, 7, 11).
Author: Avia Solutions.

The France test set of 3 August 2026 showed that the hard problem is not finding
capacity figures but resolving several different KINDS of figure into one annual
number that will stand up, and showing the working when a client drills into it.

Two tables, and the separation between them is the point:

  capacity_observation   what we found, stored exactly as published, in its own
                         units, never converted in place, never overwritten
                         (superseded instead), with source, locator, season,
                         validity, basis, grade and two names against it.

  capacity_resolution    what we decided: which tests ran, which did not and why,
                         the binding constraint and year, K, the conversion
                         parameters used, and the generated statement.

Rules enforced here rather than left to convention, because each is a failure the
France set produced or nearly produced:

  * Actual traffic can never be a capacity observation. Nantes 2025 traffic was
    entered as a capacity with reasoning that was not unreasonable, and it would
    have passed a quick review.
  * "Declared no limitation" is not the same as "no figure found". The first is
    a test that does not apply; the second is a test we could not run. They must
    not render the same way.
  * An airfield rate carries its basis: an engineered throughput (FAA profiles,
    masterplan design rates) is not the same quantity as a declared capacity that
    already embeds an agreed delay tolerance (coordinator declarations).

The engine downstream is unaffected: resolve() produces a practical capacity in
pax/yr that capacity.spill.airport_solve consumes exactly as before.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import csv
import math

from ..config import get


# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------

CONSTRAINT_TYPES = ("runway", "atc", "terminal", "stand",
                    "regulatory_annual_cap", "curfew", "composite_design_annual")

RATE_BASES = ("engineered_throughput", "declared_with_delay_tolerance", "")

#: A confirmed absence, not a gap. Used where a coordinator publishes no capacity
#: because none is needed: IATA Level 1 means capacity comfortably exceeds demand.
#: Six of the seventeen French airports are in this position and always will be.
#: Recording it as an unread parameter would send someone hunting for a document
#: that does not exist, and would hide a genuine signal of headroom.
NO_DECLARATION = "coordinator_no_declaration"

#: Preference order per constraint type, best first (v0.4 section 3). An
#: observation of a more preferred basis supersedes a less preferred one for the
#: purpose of the test; the less preferred one is still recorded and shown.
PREFERENCE = {
    "runway": ["coordinator_declaration", "regulator_decree", "eurocontrol_airport_corner",
               "faa_called_rate", "faa_profile", "masterplan", "avia_estimate"],
    "atc": ["coordinator_declaration", "regulator_decree", "eurocontrol_airport_corner",
            "avia_estimate"],
    "terminal": ["coordinator_declaration", "operator_statement", "masterplan",
                 "concession_document", "avia_estimate"],
    "stand": ["coordinator_declaration", "operator_statement", "masterplan", "avia_estimate"],
    "regulatory_annual_cap": ["regulator_decree"],
    "curfew": ["regulator_decree", "coordinator_declaration", "operator_statement"],
    "composite_design_annual": ["operator_statement", "masterplan", "concession_document",
                                "avia_estimate"],
}

#: Bases that may never create a hard annual cap (v0.4 section 3).
CAP_BASES_ALLOWED = ("regulator_decree",)


class EvidenceError(ValueError):
    """Raised only for a rule violation in the record itself, never for missing data.
    Missing data is a flagged output; a rule violation is a bug in the entry."""


# --------------------------------------------------------------------------
# capacity_observation
# --------------------------------------------------------------------------

@dataclass
class Observation:
    iata: str
    constraint_type: str
    value: float | None = None            # as published; None where nothing is quantified
    unit: str = ""                        # mvts_per_hr | mvts_per_yr | pax_per_hr | pax_per_yr_m | stands | hours_per_day
    rate_basis: str = ""                  # engineered_throughput | declared_with_delay_tolerance
    declared_no_limit: bool = False       # the coordinator states there is no limitation
    config: str = ""                      # runway configuration or terminal name
    season: str = ""                      # S26 | W26 | permanent | works period
    validity_from: str = ""
    validity_to: str = ""
    basis: str = ""                       # see PREFERENCE
    source_title: str = ""
    source_url: str = ""
    source_locator: str = ""              # page, section or image file
    source_date: str = ""
    retrieved_date: str = ""
    language: str = "en"
    machine_readable: bool = True         # False where the figure is published only as an image
    grade: str = "C"                      # A | B | C, the kind of evidence
    confidence: str = "C"                 # A | B | C, trust in this instance
    entered_by: str = ""
    entered_date: str = ""
    checked_by: str = ""
    checked_date: str = ""
    superseded_by: str = ""
    obs_id: str = ""
    notes: str = ""

    def __post_init__(self):
        if self.constraint_type not in CONSTRAINT_TYPES:
            raise EvidenceError(
                f"{self.iata}: unknown constraint_type {self.constraint_type!r}. "
                f"Actual traffic is not a constraint type and must never be entered as one.")
        if self.rate_basis not in RATE_BASES:
            raise EvidenceError(f"{self.iata}: unknown rate_basis {self.rate_basis!r}")
        if self.constraint_type == "regulatory_annual_cap" and self.value is not None \
                and self.basis not in CAP_BASES_ALLOWED:
            raise EvidenceError(
                f"{self.iata}: a hard annual cap may only come from a regulator decree, "
                f"not from {self.basis!r}")
        if self.declared_no_limit and self.value is not None:
            raise EvidenceError(
                f"{self.iata}: an observation cannot both declare no limitation and carry a value")

    @property
    def quantified(self) -> bool:
        return self.value is not None and math.isfinite(self.value)

    @property
    def checked(self) -> bool:
        return bool(self.entered_by) and bool(self.checked_by) \
            and self.entered_by != self.checked_by


def _b(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "y")


def _f(v):
    if v is None:
        return None
    s = str(v).strip()
    return float(s) if s else None


def load_observations(csv_path) -> list[Observation]:
    """Read the observation CSV. Blank value cells mean 'not quantified', which is
    a legitimate and informative state, not an error."""
    out = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as fh:
        for rec in csv.DictReader(fh):
            if not (rec.get("iata") or "").strip():
                continue
            out.append(Observation(
                iata=rec["iata"].strip(),
                constraint_type=(rec.get("constraint_type") or "").strip(),
                value=_f(rec.get("value")),
                unit=(rec.get("unit") or "").strip(),
                rate_basis=(rec.get("rate_basis") or "").strip(),
                declared_no_limit=_b(rec.get("declared_no_limit")),
                config=(rec.get("config") or "").strip(),
                season=(rec.get("season") or "").strip(),
                validity_from=(rec.get("validity_from") or "").strip(),
                validity_to=(rec.get("validity_to") or "").strip(),
                basis=(rec.get("basis") or "").strip(),
                source_title=(rec.get("source_title") or "").strip(),
                source_url=(rec.get("source_url") or "").strip(),
                source_locator=(rec.get("source_locator") or "").strip(),
                source_date=(rec.get("source_date") or "").strip(),
                retrieved_date=(rec.get("retrieved_date") or "").strip(),
                language=(rec.get("language") or "en").strip(),
                machine_readable=_b(rec.get("machine_readable")),
                grade=(rec.get("grade") or "C").strip().upper(),
                confidence=(rec.get("confidence") or "C").strip().upper(),
                entered_by=(rec.get("entered_by") or "").strip(),
                entered_date=(rec.get("entered_date") or "").strip(),
                checked_by=(rec.get("checked_by") or "").strip(),
                checked_date=(rec.get("checked_date") or "").strip(),
                superseded_by=(rec.get("superseded_by") or "").strip(),
                obs_id=(rec.get("obs_id") or "").strip(),
                notes=(rec.get("notes") or "").strip(),
            ))
    return out


def by_airport(observations) -> dict[str, list[Observation]]:
    out: dict[str, list[Observation]] = {}
    for o in observations:
        out.setdefault(o.iata, []).append(o)
    return out


def preferred(observations, constraint_type: str) -> Observation | None:
    """The observation the tests should use for one constraint type, on the stated
    preference order. Superseded observations are never chosen but stay in the
    record. Returns None where nothing quantified exists."""
    order = PREFERENCE.get(constraint_type, [])
    live = [o for o in observations
            if o.constraint_type == constraint_type and not o.superseded_by and o.quantified]
    if not live:
        return None
    return min(live, key=lambda o: order.index(o.basis) if o.basis in order else len(order))


def declares_no_limit(observations, constraint_type: str) -> Observation | None:
    for o in observations:
        if o.constraint_type == constraint_type and o.declared_no_limit and not o.superseded_by:
            return o
    return None


# --------------------------------------------------------------------------
# capacity_resolution
# --------------------------------------------------------------------------

@dataclass
class TestResult:
    name: str                     # airfield | terminal_rate | terminal_annual | stands | statutory_cap
    k_by_year: dict               # year -> annual capacity implied, m pax/yr
    binding_year: int | None      # first year demand exceeds the implied capacity
    obs_id: str = ""
    basis: str = ""
    rate_basis: str = ""


@dataclass
class Resolution:
    iata: str
    state: str                    # constrained_evidenced | constraint_known_not_quantified | unconstrained
    binding_test: str | None = None
    binding_year: int | None = None
    k_annual_pax_m: float | None = None
    practical_capacity: float | None = None      # engine-facing, pax/yr
    tests_run: list = field(default_factory=list)
    tests_not_run: dict = field(default_factory=dict)   # name -> reason
    convention: str = ""
    conversion: dict = field(default_factory=dict)
    range_flag: bool = False
    range_note: str = ""
    # Binding year read at the edges of the share projection's own accuracy. The blind
    # test against 2025 puts the median error on the projected peak hour share at 15%,
    # and capacity moves inversely with the share, so a 15% share error is a 15% capacity
    # error, which at 3% growth is about 4.7 years on the binding year. A single year
    # quoted to a client is not supported by the evidence.
    binding_year_early: int | None = None
    binding_year_late: int | None = None
    share_uncertainty: float = 0.0
    statement: str = ""
    blocking_flags: list = field(default_factory=list)


def _first_exceedance(demand: dict, k_by_year: dict):
    for y in sorted(demand):
        k = k_by_year.get(y)
        if k is not None and math.isfinite(k) and demand[y] > k:
            return y
    return None


def resolve(iata: str, observations, demand: dict, share: dict,
            seats_per_mvt: float | None = None, load_factor: float | None = None,
            committed_steps=None, convention: str | None = None,
            share_uncertainty: float | None = None) -> Resolution:
    """Run whichever tests the evidence supports and record the ones it does not.

    demand  year -> annual passengers, m (the forecast)
    share   year -> peak hour share of annual traffic (capacity.peakhour)

    The test happens in the peak hour, the answer is reported as an annual figure
    and a binding year (v0.4 section 2). K rises over time for the rate-based
    tests because the peak hour share falls as an airport grows, which is the
    schedule spreading into the shoulders.
    """
    obs = [o for o in observations if o.iata == iata]
    convention = convention or str(get("peak_hour.convention", "busy_30th"))
    spm = seats_per_mvt if seats_per_mvt is not None else float(get("capacity_register.seats_per_mvt_default"))
    lf = load_factor if load_factor is not None else float(get("capacity_register.load_factor_default"))
    allowance = float(get("capacity.peak_spreading_allowance"))
    years = sorted(demand)

    unc = (float(get("peak_hour.share_projection_median_error", 0.0))
           if share_uncertainty is None else float(share_uncertainty))

    res = Resolution(iata=iata, state="unconstrained", convention=convention,
                     share_uncertainty=unc,
                     conversion={"seats_per_mvt": spm, "load_factor": lf,
                                 "peak_spreading_allowance": allowance,
                                 "share_uncertainty": unc,
                                 "peak_hour_share": {y: share.get(y) for y in years}})

    def annual_from_rate(rate_pax_per_hr, y):
        """Annual passengers that exactly fill a peak hour rate in year y."""
        s = share.get(y)
        if not s or not math.isfinite(s) or s <= 0:
            return None
        return rate_pax_per_hr / s / 1e6 * allowance

    # --- Test A, airfield: the lower of the runway and ATC declared rates -------
    airfield_candidates = [o for o in (preferred(obs, "runway"), preferred(obs, "atc")) if o]
    airfield = min(airfield_candidates, key=lambda o: o.value) if airfield_candidates else None
    if airfield and airfield.unit == "mvts_per_hr":
        k = {y: annual_from_rate(airfield.value * spm * lf, y) for y in years}
        t = TestResult("airfield", k, _first_exceedance(demand, k),
                       airfield.obs_id, airfield.basis, airfield.rate_basis)
        res.tests_run.append(t)
    else:
        pending = [o for o in obs if o.constraint_type in ("runway", "atc")
                   and not o.quantified and not o.declared_no_limit
                   and o.basis != NO_DECLARATION]
        odd_unit = [o for o in obs if o.constraint_type in ("runway", "atc")
                    and o.quantified and o.unit != "mvts_per_hr"]
        none_published = [o for o in obs if o.constraint_type in ("runway", "atc")
                          and o.basis == NO_DECLARATION]
        if none_published and not pending and not odd_unit:
            res.tests_not_run["airfield"] = (
                "coordinator publishes no capacity, confirmed: "
                "the airport is not slot constrained")
        elif pending:
            unread = [o for o in pending if not o.machine_readable]
            res.tests_not_run["airfield"] = (
                "parameters held but not transcribed" if unread else "parameters held but not quantified")
        elif odd_unit:
            # A figure IS published; we simply cannot convert the unit it is
            # published in. That is a different answer from "nothing published"
            # and the register exists to keep the two apart.
            res.tests_not_run["airfield"] = (
                "published in a unit the engine cannot convert: "
                + ", ".join(sorted({o.unit for o in odd_unit})))
        else:
            res.tests_not_run["airfield"] = "no published rate found"

    # --- Tests B and C, terminal ----------------------------------------------
    no_limit = declares_no_limit(obs, "terminal")
    term_rate = preferred(obs, "terminal")
    if no_limit and not term_rate:
        res.tests_not_run["terminal"] = "not applicable, coordinator declares no limitation"
    elif term_rate and term_rate.unit == "pax_per_hr":
        k = {y: annual_from_rate(term_rate.value, y) for y in years}
        res.tests_run.append(TestResult("terminal_rate", k, _first_exceedance(demand, k),
                                        term_rate.obs_id, term_rate.basis))
    else:
        annual_obs = term_rate if (term_rate and term_rate.unit == "pax_per_yr_m") \
            else preferred(obs, "composite_design_annual")
        if annual_obs:
            k = {}
            for y in years:
                v = annual_obs.value
                for (yr, delta) in (committed_steps or []):
                    if y >= yr:
                        v += delta
                k[y] = v
            res.tests_run.append(TestResult("terminal_annual", k, _first_exceedance(demand, k),
                                            annual_obs.obs_id, annual_obs.basis))
        elif term_rate and term_rate.quantified:
            # Figari publishes a terminal limit as a count of check-in banks.
            # Real, published, and not convertible without its allocation table.
            res.tests_not_run["terminal"] = (
                f"published in a unit the engine cannot convert: {term_rate.unit}")
        else:
            res.tests_not_run["terminal"] = "no published figure found"

    # --- Test D, stands --------------------------------------------------------
    stands = preferred(obs, "stand")
    if stands and stands.unit == "stands":
        turn = float(get("capacity_evidence.stand_turnaround_hours"))
        k = {}
        for y in years:
            s = share.get(y)
            if not s or s <= 0:
                k[y] = None
                continue
            # peak simultaneous aircraft, indicative: half the peak hour movements
            # (arrivals) held for the turnaround
            pax_per_hr_at_stand_limit = stands.value / turn * 2.0 * spm * lf
            k[y] = pax_per_hr_at_stand_limit / s / 1e6 * allowance
        res.tests_run.append(TestResult("stands", k, _first_exceedance(demand, k),
                                        stands.obs_id, stands.basis))
    else:
        res.tests_not_run["stands"] = "no published stand constraint found"

    # --- Test E, statutory cap -------------------------------------------------
    cap = preferred(obs, "regulatory_annual_cap")
    if cap and cap.unit == "mvts_per_yr":
        k = {y: cap.value * spm * lf / 1e6 for y in years}
        res.tests_run.append(TestResult("statutory_cap", k, _first_exceedance(demand, k),
                                        cap.obs_id, cap.basis))
    elif cap and cap.unit == "pax_per_yr_m":
        k = {y: cap.value for y in years}
        res.tests_run.append(TestResult("statutory_cap", k, _first_exceedance(demand, k),
                                        cap.obs_id, cap.basis))
    else:
        res.tests_not_run["statutory_cap"] = "no cap in law or decree found"

    # --- Resolve ---------------------------------------------------------------
    bound = [t for t in res.tests_run if t.binding_year is not None]
    if bound:
        first = min(t.binding_year for t in bound)
        winner = min((t for t in bound if t.binding_year == first),
                     key=lambda t: t.k_by_year.get(first) or float("inf"))
        res.state = "constrained_evidenced"
        res.binding_test = winner.name
        res.binding_year = first
        res.k_annual_pax_m = winner.k_by_year.get(first)
        res.practical_capacity = res.k_annual_pax_m * 1e6 if res.k_annual_pax_m else None
        _set_range_flag(res, bound, first)
    elif res.tests_run:
        # tests ran but nothing binds over the horizon: carry the tightest K
        last = years[-1]
        ks = [t.k_by_year.get(last) for t in res.tests_run if t.k_by_year.get(last) is not None]
        res.state = "unconstrained"
        res.k_annual_pax_m = min(ks) if ks else None
        res.practical_capacity = res.k_annual_pax_m * 1e6 if res.k_annual_pax_m else None
    else:
        held = [o for o in obs if not o.quantified and not o.declared_no_limit]
        res.state = "constraint_known_not_quantified" if held else "unconstrained"
        res.k_annual_pax_m = None
        res.practical_capacity = None

    if res.binding_year is not None and unc > 0:
        # A HIGHER share means the peak fills sooner, so capacity binds EARLIER.
        for mult, attr in ((1.0 + unc, "binding_year_early"), (1.0 - unc, "binding_year_late")):
            edge = {y: (share.get(y) or 0.0) * mult for y in years}
            edge_res = resolve(iata, obs, demand, edge, spm, lf, committed_steps,
                               convention, share_uncertainty=0.0)
            setattr(res, attr, edge_res.binding_year)

    res.statement = statement(res, obs)
    return res


def _set_range_flag(res: Resolution, bound, first_year: int):
    """Where two tests bind close together, or two capacities are close, the single
    binding year is not a point estimate and the output says so (v0.4 section 11.3)."""
    yr_trig = int(get("capacity_evidence.range_trigger_years"))
    k_trig = float(get("capacity_evidence.range_trigger_k_rel"))
    others = [t for t in bound if t.name != res.binding_test]
    for t in others:
        dy = abs((t.binding_year or 0) - first_year)
        k_other = t.k_by_year.get(first_year)
        dk = (abs(k_other - res.k_annual_pax_m) / res.k_annual_pax_m
              if k_other and res.k_annual_pax_m else 0.0)
        if dy <= yr_trig or dk <= k_trig:
            res.range_flag = True
            res.range_note = (
                f"{res.binding_test} and {t.name} bind within {dy} year(s) of each other; "
                f"the binding year should be read as a range, not a point")
            return


# --------------------------------------------------------------------------
# The statement a user reads on the drill-down (v0.4 section 6)
# --------------------------------------------------------------------------

_STATE_TEXT = {
    "constrained_evidenced": "constrained on the evidence held",
    "constraint_known_not_quantified": "constraint known, not quantified",
    "unconstrained": "no binding constraint on the evidence held",
}


def statement(res: Resolution, observations) -> str:
    """Generated from the record, never typed, so it cannot go stale."""
    lines = [f"{res.iata} capacity: {_STATE_TEXT.get(res.state, res.state)}."]

    if res.state == "constrained_evidenced":
        lines.append(
            f"The binding constraint is the {res.binding_test.replace('_', ' ')} from "
            f"{res.binding_year}, at {res.k_annual_pax_m:.1f}m passengers a year, tested on "
            f"the {res.convention} convention.")
        if res.binding_year_early and res.binding_year_late and \
                res.binding_year_early != res.binding_year_late:
            lines.append(
                f"Read that as a range of {res.binding_year_early} to {res.binding_year_late}. "
                f"The peak hour share is projected rather than observed, and its median error "
                f"against a held-out year is {res.share_uncertainty:.0%}, which moves the "
                f"binding year by about that much either side.")
        if res.range_flag:
            lines.append(res.range_note + ".")
    elif res.state == "constraint_known_not_quantified":
        lines.append("A constraint is on record but no usable figure is held, so the airport "
                     "is modelled unconstrained with the constraint flagged.")

    for o in observations:
        if o.declared_no_limit:
            lines.append(
                f"The {o.constraint_type} is not a constraint here: {o.source_title or o.basis} "
                f"states no limitation{(' for ' + o.season) if o.season else ''}.")

    unread = [o for o in observations if not o.machine_readable and not o.quantified]
    if unread:
        kinds = sorted({o.constraint_type for o in unread})
        lines.append(f"Held but not yet transcribed ({', '.join(kinds)}): published as images "
                     f"rather than text, so a person is required.")

    if res.tests_not_run:
        lines.append("Tests not run: "
                     + "; ".join(f"{k}, {v}" for k, v in sorted(res.tests_not_run.items())) + ".")

    srcs = sorted({f"{o.source_title} ({o.source_date})" for o in observations if o.source_title})
    if srcs:
        lines.append("Sources: " + "; ".join(srcs) + ".")
    return " ".join(lines)


# --------------------------------------------------------------------------
# Validation (v0.4 section 7)
# --------------------------------------------------------------------------

@dataclass
class ValidationFlag:
    iata: str
    check: str
    flagged: bool
    blocking: bool
    detail: str = ""


def check_actual_vs_k(iata: str, actual_pax_m: float | None, k_annual_pax_m: float | None,
                      has_statutory_cap: bool = False) -> ValidationFlag:
    """Check 2. An airport running above its recorded capacity, with no declared cap
    to explain it, means the record is wrong and no convention argument rescues it.
    Blocking, not advisory: this is the check that would have caught both Nice and
    Beauvais in the France test set with nobody reading anything."""
    tol = float(get("capacity_evidence.actual_over_k_block_rel"))
    if actual_pax_m is None or k_annual_pax_m is None or k_annual_pax_m <= 0:
        return ValidationFlag(iata, "actual_vs_k", False, False, "not testable")
    ratio = actual_pax_m / k_annual_pax_m
    flagged = ratio > tol and not has_statutory_cap
    return ValidationFlag(
        iata, "actual_vs_k", flagged, flagged,
        f"actual {actual_pax_m:.1f}m against recorded capacity {k_annual_pax_m:.1f}m "
        f"({ratio:.0%})" if flagged else f"actual at {ratio:.0%} of recorded capacity")


def check_observed_peak_vs_declared(iata: str, observed_peak_mvts_per_hr: float | None,
                                    declared_mvts_per_hr: float | None,
                                    level3: bool = False) -> ValidationFlag:
    """Check 1. The busiest scheduled hour from OAG against the declared rate we hold.
    Observed above declared means our record is wrong. At a Level 3 airport the filed
    schedule is itself shaped by the declaration, so this reads as a lower bound there
    and is the better proxy at uncoordinated airports; the caveat travels with the flag."""
    if observed_peak_mvts_per_hr is None or declared_mvts_per_hr is None or declared_mvts_per_hr <= 0:
        return ValidationFlag(iata, "observed_peak_vs_declared", False, False, "not testable")
    flagged = observed_peak_mvts_per_hr > declared_mvts_per_hr
    detail = (f"observed peak {observed_peak_mvts_per_hr:.0f}/hr against declared "
              f"{declared_mvts_per_hr:.0f}/hr")
    if level3:
        detail += "; Level 3, so the filed peak is shaped by the declaration and this is a lower bound"
    return ValidationFlag(iata, "observed_peak_vs_declared", flagged, flagged, detail)


# --------------------------------------------------------------------------
# Bridge to the existing engine interface
# --------------------------------------------------------------------------

def capacity_by_year(res: Resolution) -> dict:
    """K per year, pax/yr, as the tightest of whichever tests ran.

    Capacity is NOT a constant across a forecast. The rate based tests convert an
    hourly declaration into an annual figure through the peak hour share, and the share
    falls as an airport grows, so the same runway carries more passengers a year later
    on. Holding a single K flat across the horizon throws that away, which is the whole
    finding the elasticity work produced.
    """
    if not res.tests_run:
        return {}
    years = sorted({y for t in res.tests_run for y in t.k_by_year})
    out = {}
    for y in years:
        vals = [t.k_by_year.get(y) for t in res.tests_run
                if t.k_by_year.get(y) is not None and math.isfinite(t.k_by_year[y])]
        if vals:
            out[y] = min(vals) * 1e6
    return out


def capacity_for(res: Resolution) -> float:
    """K passed to capacity.spill.airport_solve: pax/yr, or 0.0 for unconstrained,
    which airport_solve reads as 'no register entry'. Same contract as the v0.1
    register loader, so nothing downstream changes."""
    return res.practical_capacity if res.practical_capacity is not None else 0.0

"""capacity/register - the two-field capacity register loader and K derivation
(Capacity Register - Design and Sourcing v0.1; Method Spec 6.1). Author: Avia Solutions.

The register carries two KINDS of capacity, not one number:
  grade A  declared/called movements per hour, by peak runway configuration;
  grade B  a stated design annual passenger capacity;
  grade C  nothing reliable, modelled unconstrained.

K (annual terminal pax) derives from whichever kind exists, per the book
conventions. All numerics are read from the assumptions book; nothing is hard
coded here. The engine consumes practical_capacity (pax/yr) exactly as before,
so the two-field design is invisible downstream of this loader.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import csv
import json
import math

from ..config import get


@dataclass
class RegisterRow:
    iata: str
    country: str
    k_grade: str                       # "A" | "B" | "C"
    k_annual_pax_m: float | None       # derived annual K before peak-spreading, m pax/yr
    practical_capacity: float | None   # engine-facing K, pax/yr (None => unconstrained)
    committed_steps: list = field(default_factory=list)  # [[opening_year, +m pax], ...]
    source: str = ""
    confidence: str = ""
    ab_flag: bool = False              # both A and B present and they disagree > tol
    notes: str = ""


def _f(v):
    """Parse a CSV cell to float, treating blanks as missing."""
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    return float(s)


def _parse_steps(raw: str):
    """Committed steps come in the seed CSV as 'YYYY:+Nm' pairs, semicolon-joined
    (e.g. '2031:+25'). Returns [[year, delta_m], ...]. Tolerant of blanks."""
    steps = []
    if not raw:
        return steps
    for part in str(raw).replace(",", ";").split(";"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        yr, delta = part.split(":", 1)
        delta = delta.replace("+", "").replace("m", "").strip()
        try:
            steps.append([int(yr.strip()), float(delta)])
        except ValueError:
            continue
    return steps


def derive_k_grade_a(declared_mvts_per_hr, operating_hours, seats_per_mvt, load_factor):
    """Grade A: K = declared_mvts_per_hr x operating_hours x seats_per_mvt x load_factor,
    expressed in m pax/yr. Missing operating hours / seats / load factor fall back to
    the book defaults (a noted curfew is expected to set operating_hours in the row)."""
    oh = operating_hours if operating_hours is not None else get("capacity_register.operating_hours_default")
    spm = seats_per_mvt if seats_per_mvt is not None else get("capacity_register.seats_per_mvt_default")
    lf = load_factor if load_factor is not None else get("capacity_register.load_factor_default")
    if declared_mvts_per_hr is None:
        return None
    annual_pax = declared_mvts_per_hr * oh * spm * lf
    return annual_pax / 1e6


def _practical(k_annual_pax_m):
    """Engine-facing K in pax/yr: derived annual K scaled by the peak-spreading
    allowance (practical annual = allowance x first-binding level, Method Spec 6.1)."""
    if k_annual_pax_m is None:
        return None
    allowance = get("capacity.peak_spreading_allowance")
    return k_annual_pax_m * allowance * 1e6


def derive_row(rec: dict) -> RegisterRow:
    """Derive one register row from a raw CSV record (headers per the seed template)."""
    grade = (rec.get("K_grade") or rec.get("k_grade") or "").strip().upper()
    declared = _f(rec.get("declared_mvts_per_hr"))
    oh = _f(rec.get("operating_hours"))
    spm = _f(rec.get("seats_per_mvt"))
    lf = _f(rec.get("load_factor"))
    design_b = _f(rec.get("design_annual_pax_m"))

    k_a = derive_k_grade_a(declared, oh, spm, lf)
    ab_flag = False

    if grade == "A":
        k = k_a
    elif grade == "B":
        k = design_b
        # if a grade-B airport also carries a rate, cross-check the two kinds
        if k_a is not None and k is not None and k > 0:
            if abs(k_a - k) / k > get("capacity_register.ab_reconcile_tol"):
                ab_flag = True
    elif grade == "C":
        k = None
    else:                                  # unknown grade: prefer B then A then unconstrained
        k = design_b if design_b is not None else k_a

    return RegisterRow(
        iata=(rec.get("iata") or "").strip(),
        country=(rec.get("country") or "").strip(),
        k_grade=grade or "C",
        k_annual_pax_m=k,
        practical_capacity=_practical(k),
        committed_steps=_parse_steps(rec.get("committed_steps", "")),
        source=(rec.get("source") or "").strip(),
        confidence=(rec.get("confidence") or "").strip(),
        ab_flag=ab_flag,
        notes=(rec.get("notes") or "").strip(),
    )


def load_register(csv_path) -> dict[str, RegisterRow]:
    """Read the seed CSV and return {iata: RegisterRow} with K derived per grade.
    Grade C rows carry practical_capacity None and are treated as unconstrained by
    airport_solve (K <= 0)."""
    out: dict[str, RegisterRow] = {}
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as fh:
        for rec in csv.DictReader(fh):
            row = derive_row(rec)
            if row.iata:
                out[row.iata] = row
    return out


def capacity_for(row: RegisterRow) -> float:
    """K passed to capacity.spill.airport_solve: pax/yr, or 0.0 for unconstrained
    (grade C / no derived K), which airport_solve reads as 'no register entry'."""
    return row.practical_capacity if row.practical_capacity is not None else 0.0

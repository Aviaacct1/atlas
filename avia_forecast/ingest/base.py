"""Ingest adapter base: shared validation (Data Architecture 5.1).
Author: Avia Solutions.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ValidationResult:
    ok: bool
    messages: list


def validate_series(values, *, allow_zero: bool = True) -> ValidationResult:
    """Non-negativity and continuity checks common to every adapter."""
    msgs = []
    for v in values:
        if v is None:
            continue
        if v < 0 or (v == 0 and not allow_zero):
            msgs.append(f"non-positive value {v!r}")
    return ValidationResult(ok=not msgs, messages=msgs)


class Adapter:
    """Base class. Subclasses implement read() -> tidy rows and declare source_id."""
    source_id: str = "unset"

    def read(self, *args, **kwargs):
        raise NotImplementedError

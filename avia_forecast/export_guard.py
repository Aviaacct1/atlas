"""Export refusal: a warned run never becomes a client artefact.

Meridian's refusal rule, adopted for Atlas on John's instruction of 16 August 2026:
a run with warnings renders on a portal with the warning stated, and is refused for
any client artefact. Authentication controls who reaches a writer; this controls
whether the writer may write at all, and the two are deliberately separate layers.

The register of active watchpoints is config/export_watchpoints.yaml. Each entry
names its scope, the reason, who opened it and when. Clearing one is a deliberate,
auditable config edit (set cleared with a date, name and note), never a code path:
there is no override flag, because an override flag is how a refusal becomes a
warning again. Author: Avia Solutions.
"""
from __future__ import annotations
import os

import yaml

_REGISTER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "export_watchpoints.yaml")


def refusals(scope: str) -> list[dict]:
    """Uncleared watchpoints matching `scope` or 'all'. An unreadable or absent
    register refuses everything: a guard that fails open is decorative."""
    try:
        doc = yaml.safe_load(open(_REGISTER, encoding="utf-8")) or {}
        entries = doc.get("watchpoints") or []
    except FileNotFoundError:
        return [{"scope": "all", "reason": f"export watchpoint register missing at {_REGISTER}; "
                                           f"exports refuse until it exists"}]
    except Exception as e:  # malformed register
        return [{"scope": "all", "reason": f"export watchpoint register unreadable ({e}); "
                                           f"exports refuse until it parses"}]
    out = []
    for e in entries:
        if e.get("cleared"):
            continue
        if e.get("scope") in (scope, "all"):
            out.append(e)
    return out


def refusal_message(scope: str) -> str | None:
    """One printable message, or None when the export may proceed."""
    r = refusals(scope)
    if not r:
        return None
    lines = [f"- [{e.get('scope')}] {e.get('reason')} (opened {e.get('opened', 'undated')})" for e in r]
    return ("EXPORT REFUSED: this run has open watchpoints and a warned run is never "
            "delivered as a client artefact.\n" + "\n".join(lines) +
            "\nClear the entry in config/export_watchpoints.yaml (cleared: date, by, note) "
            "once the underlying issue is resolved.")

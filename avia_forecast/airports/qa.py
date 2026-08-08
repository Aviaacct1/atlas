"""airports/qa - one-command QA pack per configured instance (O-11).

Runs, in one call, the checks that must be green before any deliverable leaves the building:
benchmark tolerance, the reconciliation identities, a pack round-trip (determinism of the override
pack), and author-stamp verification on every deliverable file. Author: Avia Solutions.
"""
from __future__ import annotations
import json
import re
import zipfile

from . import instance

EXPECTED_AUTHOR = "Avia Solutions"


def _core_authors(path: str):
    """(creator, lastModifiedBy) from an OOXML file's docProps/core.xml (xlsx and docx)."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("docProps/core.xml").decode("utf-8", "replace")

    def g(tag):
        m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml)
        return m.group(1) if m else None
    return g("dc:creator"), g("cp:lastModifiedBy")


def check_author_stamp(path: str, expected: str = EXPECTED_AUTHOR) -> dict:
    try:
        cre, mod = _core_authors(path)
    except Exception as e:
        return {"name": f"author_stamp:{path}", "ok": False, "detail": f"unreadable: {e}"}
    ok = (cre == expected) and (mod in (expected, None))
    return {"name": f"author_stamp:{path}", "ok": ok,
            "detail": {"creator": cre, "lastModifiedBy": mod, "expected": expected}}


def _benchmark_tolerance(cfg: dict, tol: float) -> dict:
    rows = instance.benchmark_check(cfg, tol)
    bad = [r for r in rows if not r[-1]]
    return {"name": "benchmark_tolerance", "ok": bool(rows) and not bad,
            "detail": {"years": len(rows),
                       "worst": max((abs(r[3]) for r in rows), default=None),
                       "failed": [r[0] for r in bad]}}


def _identities(cfg: dict, overrides=None) -> dict:
    fc = instance.forecast(cfg, overrides)
    bad = []
    for y, r in fc.items():
        if abs(r["non_lcc"] + r["lcc"] - r["total"]) > 1.0:
            bad.append(("non_lcc+lcc", y))
        if abs(r["international"] + r["domestic"] + r["transit"] + r["ga"] - r["total"]) > 1.5:
            bad.append(("segments", y))
    return {"name": "identities", "ok": not bad, "detail": {"violations": bad[:5]}}


def _pack_round_trip(cfg: dict, pack: dict) -> dict:
    """A pack must serialise to JSON and re-apply to the identical forecast (the pack is the
    deterministic source of truth). Year-keyed ops become string keys through JSON and must still
    resolve."""
    a = instance.forecast(cfg, pack)
    b = instance.forecast(cfg, json.loads(json.dumps(pack)))
    same = all(abs(a[y]["total"] - b[y]["total"]) < 1e-9 for y in a)
    return {"name": "pack_round_trip", "ok": same, "detail": {"deterministic": same}}


def qa_pack(cfg: dict, deliverables=None, sample_pack=None, tol: float = 0.02) -> dict:
    """Run the full QA pack for one instance. deliverables = paths to the generated files to
    author-stamp check. Returns {checks: [...], ok: bool}."""
    checks = [_benchmark_tolerance(cfg, tol), _identities(cfg),
              _pack_round_trip(cfg, sample_pack or {"domUplift": 0.005})]
    for path in (deliverables or []):
        checks.append(check_author_stamp(path))
    return {"checks": checks, "ok": all(c["ok"] for c in checks)}

"""A warned run never becomes a client artefact.

Guards the export refusal mechanism of 16 August 2026 (Meridian's refusal rule,
adopted on John's instruction): while config/export_watchpoints.yaml holds an
uncleared entry for a scope, every client artefact in that scope refuses, at the
service endpoint and at the writer itself, and the guard fails closed when its
register is missing or unreadable. Author: Avia Solutions.
"""
import os
import sys

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from avia_forecast import export_guard  # noqa: E402


def test_seeded_zagreb_watchpoint_refuses():
    r = export_guard.refusals("zagreb")
    assert r, "the seeded Zagreb watchpoint (review item 1.5) must refuse until cleared in the yaml"
    msg = export_guard.refusal_message("zagreb")
    assert "EXPORT REFUSED" in msg and "export_watchpoints.yaml" in msg


def test_cleared_entries_do_not_refuse(tmp_path, monkeypatch):
    reg = tmp_path / "export_watchpoints.yaml"
    reg.write_text(yaml.safe_dump({"watchpoints": [
        {"scope": "zagreb", "reason": "was broken", "opened": "2026-08-16",
         "cleared": {"date": "2026-08-20", "by": "Jess", "note": "fixed and verified"}}]}),
        encoding="utf-8")
    monkeypatch.setattr(export_guard, "_REGISTER", str(reg))
    assert export_guard.refusals("zagreb") == []
    assert export_guard.refusal_message("zagreb") is None


def test_scope_all_refuses_everything(tmp_path, monkeypatch):
    reg = tmp_path / "export_watchpoints.yaml"
    reg.write_text(yaml.safe_dump({"watchpoints": [
        {"scope": "all", "reason": "estate-wide halt", "opened": "2026-08-16"}]}), encoding="utf-8")
    monkeypatch.setattr(export_guard, "_REGISTER", str(reg))
    for scope in ("zagreb", "bum", "anything"):
        assert export_guard.refusals(scope)


def test_missing_register_fails_closed(monkeypatch):
    monkeypatch.setattr(export_guard, "_REGISTER", os.path.join(REPO, "config", "no_such_file.yaml"))
    r = export_guard.refusals("zagreb")
    assert r and "missing" in r[0]["reason"]


def test_writers_and_service_call_the_guard():
    for fp, needle in (("webapp/zagreb_write_excel.py", "refusal_message"),
                       ("webapp/zagreb_write_report.py", "refusal_message"),
                       ("webapp/qsi_service.py", "refusal_message")):
        text = open(os.path.join(REPO, fp), encoding="utf-8").read()
        assert needle in text, f"{fp} does not consult the export guard"
    svc = open(os.path.join(REPO, "webapp", "qsi_service.py"), encoding="utf-8").read()
    assert svc.count('refusal_message("zagreb")') >= 2, "both Zagreb endpoints must refuse"
    assert "409" in svc

"""O-12 acceptance: Bristol (BRS) is a second configured airport built config-only; the instance QA
pack is green on it and it reproduces its calibrated benchmark within tolerance. Author: Avia Solutions."""
from avia_forecast.airports import instance, qa


def test_bristol_reproduces_benchmark_within_2pct():
    cfg = instance.load("bristol")
    rows = instance.benchmark_check(cfg, tol=0.02)
    assert rows and all(ok for *_, ok in rows), [r for r in rows if not r[-1]]


def test_bristol_qa_pack_green(tmp_path):
    import openpyxl
    cfg = instance.load("bristol")
    good = tmp_path / "d.xlsx"
    wb = openpyxl.Workbook(); wb.properties.creator = "Avia Solutions"; wb.properties.lastModifiedBy = "Avia Solutions"
    wb.active["A1"] = "x"; wb.save(str(good))
    r = qa.qa_pack(cfg, deliverables=[str(good)])
    assert r["ok"], [c for c in r["checks"] if not c["ok"]]

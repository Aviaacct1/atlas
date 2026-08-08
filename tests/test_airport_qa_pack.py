"""O-11 acceptance: one-command instance QA pack (benchmark tolerance, identities, pack round-trip,
author-stamp verification). Green on Zagreb; red on a deliberately mis-stamped file. Author: Avia
Solutions."""
import openpyxl
from avia_forecast.airports import instance, qa


def _mkxlsx(path, author):
    wb = openpyxl.Workbook()
    wb.properties.creator = author
    wb.properties.lastModifiedBy = author
    wb.active["A1"] = "x"
    wb.save(path)


def test_qa_pack_green_on_zagreb(tmp_path):
    good = tmp_path / "deliverable.xlsx"; _mkxlsx(str(good), "Avia Solutions")
    r = qa.qa_pack(instance.load("zagreb"), deliverables=[str(good)])
    assert r["ok"], [c for c in r["checks"] if not c["ok"]]


def test_qa_pack_red_on_misstamped_file(tmp_path):
    bad = tmp_path / "bad.xlsx"; _mkxlsx(str(bad), "openpyxl")
    r = qa.qa_pack(instance.load("zagreb"), deliverables=[str(bad)])
    assert not r["ok"]
    stamp = next(c for c in r["checks"] if c["name"].startswith("author_stamp"))
    assert not stamp["ok"]


def test_pack_round_trip_with_year_keyed_ops():
    cfg = instance.load("zagreb")
    base = instance.forecast(cfg)
    pack = {"ytdTrim": {"trims": {2026: base[2026]["total"] * 0.97}, "taper_years": 3, "reason": "YTD-JUN"}}
    assert qa._pack_round_trip(cfg, pack)["ok"]

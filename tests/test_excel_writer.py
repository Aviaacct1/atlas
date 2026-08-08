"""O-10 writer half: a generic, config-driven Excel writer built from instance.output_rows (no
007-specific logic), author-stamped, regenerating byte-identically and reconciling to the engine.
Author: Avia Solutions."""
import hashlib
import openpyxl
from avia_forecast.airports import instance, qa
from avia_forecast.outputs import excel_writer


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def test_generic_writer_deterministic_and_stamped(tmp_path):
    cfg = instance.load("zagreb")
    p1 = tmp_path / "z1.xlsx"; p2 = tmp_path / "z2.xlsx"
    excel_writer.write_instance_excel(cfg, str(p1))
    excel_writer.write_instance_excel(cfg, str(p2))
    assert _sha(str(p1)) == _sha(str(p2))                       # byte-comparable regeneration
    wb = openpyxl.load_workbook(str(p1))
    assert wb.properties.creator == "Avia Solutions" and "Assumptions" in wb.sheetnames
    assert qa.check_author_stamp(str(p1))["ok"]


def test_generic_writer_reconciles_to_engine(tmp_path):
    cfg = instance.load("zagreb")
    o = instance.output_rows(cfg)
    p = tmp_path / "z.xlsx"; excel_writer.write_instance_excel(cfg, str(p))
    ws = openpyxl.load_workbook(str(p))["Forecast"]
    col = 3 + o["spots"].index(2045)
    trow = next(r for r in range(1, 60) if ws.cell(row=r, column=2).value == "Total passengers")
    val = ws.cell(row=trow, column=col).value
    assert abs(val - round(o["series"]["total"][2045], 1)) < 1.0


def test_generic_writer_runs_for_arbitrary_config(tmp_path):
    cfg = {"meta": {"airport": "TST", "base_year": 2025, "horizon": 2030},
           "markets": {"m": {"elasticity": 1.0, "base_weight": 1.0}},
           "gdp_index": {"m": {str(y): 1.0 + 0.02 * (y - 2025) for y in range(2025, 2031)}},
           "base": {"total": 1000.0, "international": 1000.0, "domestic": 0, "transit": 0,
                    "non_lcc": 1000.0, "lcc": 0, "commercial_atm": 10.0}}
    p = tmp_path / "t.xlsx"
    excel_writer.write_instance_excel(cfg, str(p))
    assert qa.check_author_stamp(str(p))["ok"]

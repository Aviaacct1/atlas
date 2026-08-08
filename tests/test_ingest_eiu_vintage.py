"""Ingest of an EIU forecast vintage: the DGDP 'Real GDP (% change pa)' series is extracted from the
grid and cumulated to a base-anchored index. Tested on a synthetic vintage. Author: Avia Solutions."""
import openpyxl
import importlib.util
import os

_spec = importlib.util.spec_from_file_location(
    "iev", os.path.join(os.path.dirname(__file__), "..", "scripts", "ingest_eiu_vintage.py"))
iev = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(iev)


def _synthetic(path):
    wb = openpyxl.Workbook(); ws = wb.active
    years = list(range(2010, 2021))
    ws.append(["Country", "Code", "Series Title", "SC", "Cur", "Units"] + years + ["Source"])
    # GB: real GDP growth 2% pa; DE: 1.5% pa
    ws.append(["United Kingdom", "GB", "GDP per head (US$)", "YPCA", "US$", ""] + [0]*len(years))
    ws.append(["United Kingdom", "GB", "Real GDP (% change pa)", "DGDP", "", ""] + [2.0]*len(years))
    ws.append(["Germany", "DE", "Real GDP (% change pa)", "DGDP", "", ""] + [1.5]*len(years))
    wb.save(path)


def test_extract_and_index(tmp_path):
    p = str(tmp_path / "v.xlsx"); _synthetic(p)
    rows = iev._rows(p)
    g = iev.extract_growth(rows)
    assert set(g) == {"GB", "DE"} and g["GB"][2015] == 2.0
    idx = iev.to_index(g, 2013)
    assert idx["GB"][2013] == 1.0
    assert abs(idx["GB"][2016] - 1.02 ** 3) < 1e-6        # 3 years of 2% compounding
    assert abs(idx["DE"][2016] - 1.015 ** 3) < 1e-6

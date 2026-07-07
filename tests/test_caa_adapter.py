"""UK CAA adapter tests (Method Spec 2.2, build decision D7).
Uses a fixture CSV in the CAA Table 12.1 shape. Author: Avia Solutions."""
import pandas as pd
import pytest

from avia_forecast.ingest.caa import CaaAdapter, UnmappedCountryError


def _write_intl(tmp_path):
    p = tmp_path / "table_12_1.csv"
    pd.DataFrame({
        "reporting_period": [202312, 202312, 202312, 202212],
        "reporting_airport": ["HEATHROW"] * 4,
        "origin_destination_country": ["United States", "France", "United States", "France"],
        "total_pax": [1_000_000, 500_000, 250_000, 400_000],
        "scheduled_charter": ["SCH"] * 4,
    }).to_csv(p, index=False)
    return p


def test_caa_maps_regions_and_aggregates(tmp_path):
    out = CaaAdapter().read(_write_intl(tmp_path), airport_iata="LHR")
    # 2023 North America = 1.0m + 0.25m aggregated on the same (region, year)
    na23 = out[(out.dest_region == "North America") & (out.year == 2023)]
    assert len(na23) == 1 and na23.iloc[0]["value"] == 1_250_000
    assert set(out["metric"]) == {"od_pax"}
    assert set(out["direction"]) == {"out"}
    assert (out["value"] >= 0).all()
    assert set(out["dest_region"]) == {"North America", "EU+UK"}
    assert set(out["year"]) == {2022, 2023}


def test_caa_domestic_path(tmp_path):
    p = tmp_path / "t122.csv"
    pd.DataFrame({
        "reporting_period": [2023, 2023],
        "reporting_airport": ["HEATHROW", "HEATHROW"],
        "origin_destination_country": ["United Kingdom", "United Kingdom"],
        "total_pax": [300_000, 200_000],
    }).to_csv(p, index=False)
    out = CaaAdapter().read(p, airport_iata="LHR", domestic=True)
    assert out.iloc[0]["dest_region"] == "Domestic"
    assert out["value"].sum() == 500_000


def test_caa_unmapped_country_raises(tmp_path):
    p = tmp_path / "bad.csv"
    pd.DataFrame({
        "reporting_period": [2023], "reporting_airport": ["HEATHROW"],
        "origin_destination_country": ["Neverland"], "total_pax": [1000],
    }).to_csv(p, index=False)
    with pytest.raises(UnmappedCountryError):
        CaaAdapter().read(p, airport_iata="LHR")


def test_caa_rejects_negative_pax(tmp_path):
    p = tmp_path / "neg.csv"
    pd.DataFrame({
        "reporting_period": [2023], "reporting_airport": ["HEATHROW"],
        "origin_destination_country": ["France"], "total_pax": [-5],
    }).to_csv(p, index=False)
    with pytest.raises(ValueError):
        CaaAdapter().read(p, airport_iata="LHR")

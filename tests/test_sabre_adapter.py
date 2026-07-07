"""Sabre GDD adapter + base-year bridge tests (Data Architecture 4.2). Uses a
Sabre-shaped CSV fixture. Author: Avia Solutions."""
import pandas as pd
import pytest

from avia_forecast.ingest.sabre import SabreAdapter, UnmappedCountryError
from avia_forecast import fixtures, pipeline


def _sabre_csv(tmp_path):
    p = tmp_path / "sabre_uk_2025.csv"
    pd.DataFrame({
        "origin_airport": ["LHR", "LHR", "LHR", "MAN", "MAN", "LHR"],
        "destination_country": ["United States", "France", "India", "Spain", "United States", "United States"],
        "od_passengers": [8_000_000, 14_000_000, 6_000_000, 9_000_000, 2_000_000, 1_000_000],
        "year": [2025, 2025, 2025, 2025, 2025, 2024],   # a 2024 row to be filtered out
    }).to_csv(p, index=False)
    return p


def test_sabre_maps_regions_and_filters_base_year(tmp_path):
    out = SabreAdapter().read(_sabre_csv(tmp_path), base_year=2025)
    na = out[(out.iata == "LHR") & (out.dest_region == "North America")]
    assert na.iloc[0]["value"] == 8_000_000        # the 2024 row is excluded
    assert set(out["direction"]) == {"out"} and set(out["metric"]) == {"od_pax"}
    assert set(out[out.iata == "LHR"]["dest_region"]) == {"North America", "EU+UK", "Asia Pacific"}


def test_sabre_seeds_pilot_base_od_and_runs(tmp_path):
    tidy = SabreAdapter().read(_sabre_csv(tmp_path), base_year=2025)
    base = fixtures.build_base_od_from_tidy(tidy, ["LHR", "MAN"])
    assert base["LHR"]["North America"] == pytest.approx(8.0)     # 8m pax
    assert base["MAN"]["EU+UK"] == pytest.approx(9.0)
    pilot = fixtures.make_pilot(base_od_override=base)
    lhr = next(a for a in pilot.airports if a.iata == "LHR")
    assert lhr.base_od["North America"] == pytest.approx(8.0)     # override applied
    res = pipeline.run(pilot=pilot)                               # runs end to end on Sabre-seeded base
    assert res.exceptions == [] and not res.tidy.empty


def test_sabre_unmapped_country_raises(tmp_path):
    p = tmp_path / "bad.csv"
    pd.DataFrame({"origin_airport": ["LHR"], "destination_country": ["Wakanda"],
                  "od_passengers": [1000], "year": [2025]}).to_csv(p, index=False)
    with pytest.raises(UnmappedCountryError):
        SabreAdapter().read(p, base_year=2025)

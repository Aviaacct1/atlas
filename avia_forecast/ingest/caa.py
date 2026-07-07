"""UK CAA ingest adapter (pilot market) -> traffic_history (Method Spec 2.2).

Reads CAA Table 12.1 (international route analysis) and 12.2 (domestic) CSV
extracts, maps origin/destination country to one of the eight model regions and
aggregates to the tidy contract (airport, dest_region, direction, metric=od_pax,
year). Column names come from the source register, not from code, so the exact
CAA layout locks in config.

Direction: the standard CAA route tables carry no arrival/departure split, so a
single default direction is written and the split waits on the Departing
Passenger Survey or a CAA special extract (see build decision D7).
Author: Avia Solutions.
"""
from __future__ import annotations
import pandas as pd

from .base import Adapter, validate_series
from ..config import sources as load_sources, assumptions


class UnmappedCountryError(ValueError):
    pass


def _country_region_map():
    from ..config import _load
    cr = _load("country_region.yaml")
    return cr["map"], cr.get("default_unmapped", None)


def _year_from_period(period) -> int:
    s = str(int(period)) if not isinstance(period, str) else period.strip()
    return int(s[:4])          # YYYYMM or YYYY both start with the year


class CaaAdapter(Adapter):
    source_id = "caa_uk"

    def __init__(self):
        src = load_sources()
        self.cols = src["caa_columns"]
        self.default_direction = src.get("default_direction", "out")
        self.region_map, self.default_unmapped = _country_region_map()

    def _map_region(self, country: str) -> str:
        if country in self.region_map:
            return self.region_map[country]
        if self.default_unmapped is not None:
            return self.default_unmapped
        raise UnmappedCountryError(
            f"CAA country {country!r} is not in Annex A; add it to country_region.yaml.")

    def read(self, csv_path: str, *, airport_iata: str, domestic: bool = False,
             revision_date: str = "") -> pd.DataFrame:
        """Return tidy traffic_history rows for one reporting airport."""
        raw = pd.read_csv(csv_path)
        c = self.cols
        df = raw.rename(columns={
            c["period"]: "period", c["airport"]: "airport",
            c["country"]: "country", c["passengers"]: "pax"})

        df["year"] = df["period"].map(_year_from_period)
        df["pax"] = pd.to_numeric(df["pax"], errors="coerce")

        v = validate_series(df["pax"].dropna().tolist())
        if not v.ok:
            raise ValueError(f"CAA validation failed: {v.messages[:5]}")

        df["dest_region"] = "Domestic" if domestic else df["country"].map(self._map_region)

        grouped = (df.groupby(["dest_region", "year"], as_index=False)["pax"].sum())
        grouped["iata"] = airport_iata
        grouped["direction"] = self.default_direction
        grouped["metric"] = "od_pax"
        grouped["source_id"] = self.source_id
        grouped["synthetic_flag"] = 0
        grouped["revision_date"] = revision_date
        grouped = grouped.rename(columns={"pax": "value"})
        return grouped[["iata", "dest_region", "direction", "metric", "year",
                        "value", "source_id", "synthetic_flag", "revision_date"]]

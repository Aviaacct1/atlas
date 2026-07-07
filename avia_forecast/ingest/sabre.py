"""Sabre GDD ingest adapter -> base-year O&D (Method Spec 2.2; Data Architecture 4.2).

Reads a Sabre Global Demand Data 2025 O&D extract (CSV export from the QSI tool's
sabre.duckdb, or a duckdb file) into the tidy contract: one row per (airport,
dest_region, direction, metric=od_pax, year). Column names come from the source
register, so the exact extract layout locks in config, not code.

Licensing (Work Order 2026, clause 4.b): Sabre GDD is class C and is used here for
internal parameter estimation only (the base-year O&D splits that seed the
forecast). Sabre must be cited where a material input; no raw data or
reconstitutable extract is redistributed; displayed history in the product comes
from class A sources (CAA), reconciled to these splits. Author: Avia Solutions.
"""
from __future__ import annotations
import pandas as pd

from .base import Adapter, validate_series
from ..config import sources as load_sources, _load


class UnmappedCountryError(ValueError):
    pass


def _country_region_map():
    cr = _load("country_region.yaml")
    return cr["map"], cr.get("default_unmapped", None)


def _read_any(path: str) -> pd.DataFrame:
    if str(path).endswith(".duckdb"):
        import duckdb                       # optional; only needed for a duckdb source
        con = duckdb.connect(str(path), read_only=True)
        # expects a table or view named sabre_od; adjust in the export if different
        return con.execute("SELECT * FROM sabre_od").fetch_df()
    return pd.read_csv(path)


class SabreAdapter(Adapter):
    source_id = "sabre_gdd"
    licence_class = "C"

    def __init__(self):
        src = load_sources()
        self.cols = src["sabre_columns"]
        self.default_direction = src.get("sabre_default_direction", "out")
        self.region_map, self.default_unmapped = _country_region_map()

    def _region(self, country: str) -> str:
        if country in self.region_map:
            return self.region_map[country]
        if self.default_unmapped is not None:
            return self.default_unmapped
        raise UnmappedCountryError(
            f"Sabre country {country!r} is not in Annex A; add it to country_region.yaml.")

    def read(self, path: str, *, base_year: int = 2025, revision_date: str = "") -> pd.DataFrame:
        raw = _read_any(path)
        c = self.cols
        df = raw.rename(columns={c["airport"]: "iata", c["country"]: "country",
                                 c["passengers"]: "pax", c["period"]: "year"})
        df["year"] = df["year"].astype(int)
        df = df[df["year"] == base_year]
        df["pax"] = pd.to_numeric(df["pax"], errors="coerce")
        v = validate_series(df["pax"].dropna().tolist())
        if not v.ok:
            raise ValueError(f"Sabre validation failed: {v.messages[:5]}")
        df["dest_region"] = df["country"].map(self._region)
        g = df.groupby(["iata", "dest_region", "year"], as_index=False)["pax"].sum()
        g["direction"] = self.default_direction
        g["metric"] = "od_pax"
        g["source_id"] = self.source_id
        g["synthetic_flag"] = 0
        g["revision_date"] = revision_date
        return g.rename(columns={"pax": "value"})[
            ["iata", "dest_region", "direction", "metric", "year",
             "value", "source_id", "synthetic_flag", "revision_date"]]

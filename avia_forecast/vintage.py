"""vintage.py - the vintage clock (Cockpit build update A5).

The base year BY is a vintage parameter. Everything relative to it rolls when BY
advances: spot years, CAGR windows, actual/forecast labels, offset-anchored
scenario events, the DDFS year. Calendar-anchored history does NOT roll: the COVID
dummy years, the recovery-vs-2019 baseline and the backtest windows are fixed to
the calendar. Author: Avia Solutions.
"""
from __future__ import annotations
from dataclasses import dataclass

# Fixed calendar anchors (never roll with BY)
COVID_YEARS = (2020, 2021, 2022)
SUPPLY_ANOMALY_YEARS = (2023, 2024)
RECOVERY_BASELINE = 2019
BACKTEST_FIT = (2000, 2019)
BACKTEST_FORECAST = (2022, 2026)


@dataclass(frozen=True)
class VintageClock:
    base_year: int
    horizon_span: int = 25            # BY .. BY+25

    @property
    def horizon(self) -> int:
        return self.base_year + self.horizon_span

    def spot_years(self, step: int = 5):
        """Six spot years BY, BY+5 .. BY+25 (Impact table F1)."""
        return list(range(self.base_year, self.horizon + 1, step))

    def cagr_windows(self, step: int = 5):
        """Consecutive CAGR windows across the spot years."""
        sy = self.spot_years(step)
        return list(zip(sy[:-1], sy[1:]))

    def label(self, year: int) -> str:
        """Actual/forecast suffix: BY and earlier are Actual, later are Forecast."""
        return f"{year}{'A' if year <= self.base_year else 'F'}"

    def offset_scenario_year(self, offset: int) -> int:
        """A BY-relative scenario event (generic shock): rolls with BY."""
        return self.base_year + offset

    @staticmethod
    def calendar_scenario_year(year: int) -> int:
        """A calendar-anchored scenario event (committed opening date): fixed."""
        return year

    @staticmethod
    def rolls(kind: str) -> bool:
        """Whether a clock element rolls with BY (True) or is calendar-fixed (False)."""
        return {
            "spot_years": True, "cagr_windows": True, "labels": True,
            "offset_scenario": True, "ddfs_year": True,
            "covid": False, "recovery_baseline": False, "backtest": False,
            "calendar_scenario": False,
        }[kind]

"""Vintage clock acceptance test (Cockpit build update A5): rerunning the identical
project at BY and BY+1 rolls all BY-relative elements and leaves calendar anchors
fixed. Author: Avia Solutions."""
from avia_forecast.vintage import VintageClock, COVID_YEARS, RECOVERY_BASELINE


def test_by_relative_elements_roll_and_calendar_anchors_do_not():
    a = VintageClock(2025)
    b = VintageClock(2026)

    # spot years roll by one
    assert a.spot_years() == [2025, 2030, 2035, 2040, 2045, 2050]
    assert b.spot_years() == [2026, 2031, 2036, 2041, 2046, 2051]

    # actual/forecast labels roll: BY is Actual, BY+1 is Forecast
    assert a.label(2025) == "2025A" and a.label(2026) == "2026F"
    assert b.label(2026) == "2026A" and b.label(2027) == "2027F"

    # a generic (offset) scenario event rolls; a committed-date (calendar) one does not
    assert a.offset_scenario_year(5) == 2030 and b.offset_scenario_year(5) == 2031
    assert a.calendar_scenario_year(2032) == b.calendar_scenario_year(2032) == 2032

    # calendar-anchored history does NOT roll
    assert COVID_YEARS == (2020, 2021, 2022)
    assert RECOVERY_BASELINE == 2019
    assert VintageClock.rolls("offset_scenario") and not VintageClock.rolls("covid")


def test_cagr_windows_span_the_spot_years():
    c = VintageClock(2025)
    assert c.cagr_windows() == [(2025, 2030), (2030, 2035), (2035, 2040), (2040, 2045), (2045, 2050)]
    assert c.horizon == 2050

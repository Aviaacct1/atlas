"""The peak hour window convention: clock hour against rolling 60 minutes.

House convention is rolling (Zagreb engagement letter, 18 May 2026), and it is also
how coordinators declare capacity: Nantes and Basel both publish "passengers per
rolling 60 minutes with a step of 10 minutes". Testing demand measured on clock hours
against a rate declared on a rolling hour compares two different things.

The property that has to hold, and that the first implementation broke: a rolling
maximum can never come out BELOW the clock-hour figure. Ranking every overlapping
10-minute window returned the same busy period thirty times and produced exactly that
impossible result. Taking the best window per clock hour keeps the same 8,760
observations a year, each at or above its clock-hour counterpart.
"""
from __future__ import annotations

import pytest

from avia_forecast.ingest import oag_peak


def test_both_conventions_are_known_and_anything_else_is_refused():
    assert oag_peak.PEAK_WINDOWS == ("clock_hour", "rolling_60_step_5",
                                     "rolling_60_step_10")
    for w in oag_peak.PEAK_WINDOWS:
        assert "hours AS" in oag_peak._hour_cte(w)
    with pytest.raises(ValueError) as e:
        oag_peak._hour_cte("rolling")            # plausible, not a real name
    assert "unknown peak window" in str(e.value)
    # a step finer than the base slot cannot be honoured and must not be faked
    with pytest.raises(ValueError) as e:
        oag_peak._hour_cte("rolling_60_step_3")
    assert "base slot" in str(e.value)


def test_the_clock_hour_form_buckets_six_ten_minute_slots():
    sql = oag_peak._hour_cte("clock_hour")
    assert f"hh / {oag_peak.SLOTS_PER_HOUR}" in sql, "a clock hour is SLOTS_PER_HOUR slots"
    assert oag_peak.SLOT_MINUTES == 5, "house practice is a 5-minute step (JC, 4 Aug 2026)"
    assert "OVER" not in sql, "the clock form must not use a window function"


def test_the_rolling_form_spans_an_hour_and_may_cross_midnight():
    sql = oag_peak._hour_cte("rolling_60_step_5")
    span = oag_peak.SLOTS_PER_HOUR - 1
    assert f"RANGE BETWEEN CURRENT ROW AND {span} FOLLOWING" in sql, \
        "a 60-minute window is SLOTS_PER_HOUR slots inclusive"
    assert "datediff" in sql and f"* {oag_peak.SLOTS_PER_DAY}" in sql, \
        "slots must be indexed continuously across days or a window cannot cross midnight"
    # One value per clock hour, not one per overlapping window. This is the assertion
    # that would have caught the first implementation.
    assert f"s / {oag_peak.SLOTS_PER_HOUR}" in sql and "MAX(pax)" in sql


def test_a_coarser_step_only_considers_every_nth_start_slot():
    """The 10-minute step exists so a declared rate can be tested on its own step."""
    sql5 = oag_peak._hour_cte("rolling_60_step_5")
    sql10 = oag_peak._hour_cte("rolling_60_step_10")
    assert "s % 1 = 0" in sql5
    assert "s % 2 = 0" in sql10, "10 minutes is every 2nd 5-minute slot"


def test_rolling_is_never_below_clock_hour_on_a_worked_series():
    """The invariant, checked arithmetically rather than through the database.

    A day of 10-minute slots with a burst straddling the top of an hour: the clock
    hour splits the burst, the rolling window catches it whole.
    """
    n = oag_peak.SLOTS_PER_DAY
    per_hour = oag_peak.SLOTS_PER_HOUR
    slots = {s: 1.0 for s in range(n)}
    # a bank straddling 10:00: the last slots of hour 9 and the first of hour 10
    straddle = list(range(10 * per_hour - 3, 10 * per_hour + 2))
    for s in straddle:
        slots[s] = 20.0

    clock = {}
    for s, v in slots.items():
        clock[s // per_hour] = clock.get(s // per_hour, 0.0) + v
    rolling = {}
    for s in slots:
        total = sum(slots.get(s + k, 0.0) for k in range(per_hour))
        rolling[s // per_hour] = max(rolling.get(s // per_hour, 0.0), total)

    for hr in clock:
        assert rolling[hr] >= clock[hr] - 1e-9, f"hour {hr}: rolling below clock"
    # and it is strictly higher where the bank straddles the boundary
    assert rolling[9] > clock[9], "the straddling bank must show up in the rolling hour"
    assert max(rolling.values()) >= max(clock.values())


def test_the_window_is_recorded_in_the_convention_name():
    """Mixing conventions is failure mode 4 in the module's own docstring, so a panel
    that reports only 'busy_30th' cannot be compared with another panel."""
    import inspect
    src = inspect.getsource(oag_peak.build_panel)
    assert 'convention = f"{convention}/{window}"' in src


def test_the_book_selects_a_window_that_exists():
    from avia_forecast.config import get
    assert str(get("peak_hour.window", "clock_hour")) in oag_peak.PEAK_WINDOWS

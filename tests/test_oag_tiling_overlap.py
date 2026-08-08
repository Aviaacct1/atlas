"""A split month's period keys must partition it: no day doubled, no day lost.

Asia 2025 carries 2025-01p01, 2025-01p16 and 2025-01p23 for January. period_span
reads one key at a time and has to assume two parts, so it returns 16 to 31 January
for p16, which swallows p23 whole. Summing all three counted 23 to 31 January twice.

Cost, measured 4 August 2026 against a panel Jess Rowden built independently:
Asian annual seats 2.5% high, nine duplicated days out of 365 and easily mistaken for
noise; the 30th busiest hour 7.4% high at the median and 24% at the worst, because
duplicated days go to the top of the ranking. Tokyo Haneda was 33% high on the peak
while agreeing to 0.1% on the annual.

The first fix dropped p23 as a redundant re-pull. That was wrong the same way the bug
was wrong: it looked right and it silently discarded 2.5% of Asian traffic. The parts
are three that partition, not two with a duplicate. Hence part_spans, and hence the
loss test below as well as the overlap test: a fix for one that causes the other is
not a fix.
"""
from __future__ import annotations
import calendar
import datetime

import pytest

from avia_forecast.ingest import oag_store as S


def _multiplicity(spans):
    """How many times each date is covered by a set of (lo, hi) spans."""
    seen: dict = {}
    for lo, hi in spans:
        d = datetime.date.fromisoformat(lo)
        end = datetime.date.fromisoformat(hi)
        while d <= end:
            seen[d] = seen.get(d, 0) + 1
            d += datetime.timedelta(days=1)
    return seen


def test_three_january_parts_partition_january():
    sp = S.part_spans(["2025-01p01", "2025-01p16", "2025-01p23"])
    assert sp["2025-01p01"] == ("2025-01-01", "2025-01-15")
    assert sp["2025-01p16"] == ("2025-01-16", "2025-01-22")   # ends where p23 starts
    assert sp["2025-01p23"] == ("2025-01-23", "2025-01-31")
    counts = _multiplicity(sp.values())
    assert len(counts) == 31
    assert set(counts.values()) == {1}


def test_no_part_is_discarded():
    """The failure mode of the first fix: an overlap removed by losing data."""
    keys = ["2025-01p01", "2025-01p16", "2025-01p23"]
    assert set(S.part_spans(keys)) == set(keys)


def test_two_part_months_are_unchanged():
    sp = S.part_spans(["2025-02p01", "2025-02p16"])
    assert sp["2025-02p01"] == ("2025-02-01", "2025-02-15")
    assert sp["2025-02p16"] == ("2025-02-16", "2025-02-28")
    assert set(_multiplicity(sp.values()).values()) == {1}


@pytest.mark.parametrize("month,length", [("2025-01", 31), ("2025-02", 28),
                                          ("2024-02", 29), ("2025-04", 30)])
def test_a_month_is_covered_exactly_once_however_it_is_split(month, length):
    for cuts in ([1], [1, 16], [1, 11, 21], [1, 8, 15, 22, 29]):
        keys = [f"{month}p{c:02d}" for c in cuts if c <= length]
        counts = _multiplicity(S.part_spans(keys).values())
        assert len(counts) == length, f"{month} {cuts}: covered {len(counts)} days"
        assert set(counts.values()) == {1}, f"{month} {cuts}: doubled days"


def test_whole_month_and_half_year_keys_still_work():
    sp = S.part_spans(["2025-03", "2025-H1", "2025"])
    assert sp["2025-03"] == ("2025-03-01", "2025-03-31")
    assert sp["2025-H1"][0] == "2025-01-01"
    assert sp["2025"] == ("2025-01-01", "2025-12-31")


def test_the_live_store_partitions_every_region_year():
    """The check that would have caught this. Skips where the store is absent."""
    duckdb = pytest.importorskip("duckdb")
    from avia_forecast.ingest import oag_peak
    try:
        path = oag_peak.store_path()
    except FileNotFoundError:
        pytest.skip("no store configured")
    if not path.exists():
        pytest.skip(f"store not present at {path}")
    con = duckdb.connect(str(path), read_only=True)
    try:
        con.execute("SET enable_progress_bar=false")
        pref = S.preferred_tilings(con)
    finally:
        con.close()
    doubled, holed = {}, {}
    for (region, yr), keys in pref.items():
        counts = _multiplicity(S.part_spans(keys).values())
        if any(c > 1 for c in counts.values()):
            doubled[(region, yr)] = sum(1 for c in counts.values() if c > 1)
        expected = 366 if calendar.isleap(int(yr)) else 365
        if len(counts) < expected:
            holed[(region, yr)] = expected - len(counts)
    assert not doubled, f"region-years counting a day twice: {doubled}"
    assert not holed, f"region-years missing days: {holed}"

"""The fare index is built from the assumptions, and the shipped file matches them.

Until 9 August 2026 data/fare_index_constructed.json was a static file that nothing
regenerated, estimate/fare_construction.py was imported by nothing, and the two
assumptions behind the index, fare_index.pass_through_theta and real_yield_trend_tau,
were read only in code paths nothing called. Changing either changed no number the
product reported, and nothing said so.

These tests close that loop from both ends: the construction responds to the assumptions,
and the file the forecast actually reads is the one those assumptions produce. The second
is the one that earns its keep, because it fails the day someone edits the assumptions
book and does not re-run scripts/build_fare_index.py.

Author: Avia Solutions.
"""
import json
import os

import pytest

from avia_forecast.config import get
from avia_forecast.estimate.fare_construction import build_fare_index

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUEL = os.path.join(REPO, "data", "jet_fuel_eia.json")
INDEX = os.path.join(REPO, "data", "fare_index_constructed.json")


def _fuel():
    raw = json.load(open(FUEL))
    return {int(k): float(v) for k, v in raw.items() if str(k).isdigit() and v}


def _rebase(idx, years):
    out = {}
    for seg, s in idx.items():
        b = s[years[0]]
        out[seg] = {str(y): round(s[y] / b * 100.0, 3) for y in years}
    return out


@pytest.mark.skipif(not os.path.isfile(FUEL), reason="jet fuel series not staged")
def test_pass_through_changes_the_index():
    """A higher cost pass-through must move the fare index. If it does not, the
    assumption is inert and the book is describing something the engine does not do."""
    fuel = _fuel()
    years = sorted(fuel)
    lo = build_fare_index(fuel, years, theta=0.5)
    hi = build_fare_index(fuel, years, theta=1.5)
    seg = "Long Haul"
    assert lo[seg] != hi[seg], "pass_through_theta has no effect on the constructed index"
    # in a period whose fuel rises, more pass-through means a higher fare index
    rising = [y for y in years[1:] if fuel.get(y, 0) > fuel.get(y - 1, 0)]
    assert rising, "no year in the fuel series rises; the direction cannot be tested"
    y = rising[len(rising) // 2]
    assert hi[seg][y] != lo[seg][y]


@pytest.mark.skipif(not os.path.isfile(FUEL), reason="jet fuel series not staged")
def test_real_yield_trend_changes_the_index():
    fuel = _fuel()
    years = sorted(fuel)
    a = build_fare_index(fuel, years, tau=-0.010)
    b = build_fare_index(fuel, years, tau=0.0)
    seg = "Domestic"
    assert a[seg][years[-1]] < b[seg][years[-1]], (
        "a negative real-yield trend must leave the index below a flat one by the end")


@pytest.mark.skipif(not (os.path.isfile(FUEL) and os.path.isfile(INDEX)),
                    reason="fuel series or shipped index not present")
def test_shipped_index_matches_the_assumptions_book():
    """The file the forecast reads must be the one the current assumptions produce.

    If this fails, either the assumptions book changed without the index being rebuilt,
    or the index was hand-edited. Either way the product is reporting numbers its own
    stated assumptions do not generate. Fix by running:

        python scripts/build_fare_index.py --write

    and then re-running the webapp builders.
    """
    shipped = json.load(open(INDEX))
    years = sorted(int(y) for y in next(iter(shipped.values())))
    rebuilt = _rebase(build_fare_index(_fuel(), years,
                                       theta=get("fare_index.pass_through_theta"),
                                       tau=get("fare_index.real_yield_trend_tau")), years)
    assert set(rebuilt) == set(shipped), "segments differ between the shipped and rebuilt index"
    for seg in shipped:
        for y in (str(years[0]), str(years[len(years) // 2]), str(years[-1])):
            assert y in rebuilt[seg], f"{seg} {y} missing from the rebuilt index"
            assert rebuilt[seg][y] == pytest.approx(float(shipped[seg][y]), abs=0.05), (
                f"{seg} {y}: shipped {shipped[seg][y]}, the assumptions produce "
                f"{rebuilt[seg][y]}. Run scripts/build_fare_index.py --write.")

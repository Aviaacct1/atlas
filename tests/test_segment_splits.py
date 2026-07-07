"""Segment output splits acceptance test (Cockpit build update B2). Author: Avia Solutions."""
import pytest
from avia_forecast.demand import splits
from avia_forecast.aggregate.reconcile import ReconciliationError

YEARS = list(range(2025, 2036))


def _total(g=0.03, start=100.0):
    t, lvl = {}, start
    for y in YEARS:
        t[y] = lvl; lvl *= (1 + g)
    return t


def test_B2_domestic_takes_lower_share_of_excess_and_adds_up():
    total = _total()
    dom, intl = splits.split_domestic_international(total, base_domestic=30.0, base_international=70.0, years=YEARS)

    # build-stopping adding-up identity: domestic + international = total (exact)
    splits.check_adding_up(dom, intl, total, "dom+int")            # must not raise
    for y in YEARS:
        assert dom[y] + intl[y] == pytest.approx(total[y])

    # domestic's excess growth is 0.55x international's, every year
    ed = splits.excess_growth(dom, YEARS); ei = splits.excess_growth(intl, YEARS)
    for y in YEARS[1:]:
        assert ed[y] == pytest.approx(0.55 * ei[y], rel=1e-9)

    # so the domestic share of the total declines as the market grows
    assert dom[YEARS[-1]] / total[YEARS[-1]] < dom[YEARS[0]] / total[YEARS[0]]


def test_B2_adding_up_violation_is_build_stopping():
    total = _total()
    dom, intl = splits.split_domestic_international(total, 30.0, 70.0, YEARS)
    intl[YEARS[-1]] *= 1.01                                        # break the identity
    with pytest.raises(ReconciliationError):
        splits.check_adding_up(dom, intl, total, "dom+int")


def test_B2_transfer_od_split_adds_up_to_total():
    # transfer follows the hub overlay; transfer + O&D = total terminal (identity)
    od = {y: 80.0 + (y - 2025) for y in YEARS}
    transfer = {y: 20.0 + 0.5 * (y - 2025) for y in YEARS}
    term = {y: od[y] + transfer[y] for y in YEARS}
    splits.check_adding_up(transfer, od, term, "transfer+O&D")     # must not raise
    transfer[2030] += 1.0
    with pytest.raises(ReconciliationError):
        splits.check_adding_up(transfer, od, term, "transfer+O&D")

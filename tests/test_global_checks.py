"""Global adding-up / level-reconciliation checks (Fable review #4). Author: Avia Solutions."""
import pytest
from avia_forecast import global_checks as gc


def _fixture():
    airports = {"GB": [10.0, 5.0], "FR": [8.0], "US": [20.0, 15.0]}
    cov_c = {"GB": 1.10, "FR": 1.10, "US": 1.05}
    cov_r = {"Europe": 2.0, "North America": 1.3}
    c2r = {"GB": "Europe", "FR": "Europe", "US": "North America"}
    return airports, cov_c, cov_r, c2r


def test_reconciles_by_construction():
    airports, cov_c, cov_r, c2r = _fixture()
    rec = gc.reconcile_levels(airports, cov_c, cov_r, c2r)
    assert rec["country_tot"]["GB"] == pytest.approx(15.0 * 1.10)
    assert rec["country_tot"]["US"] == pytest.approx(35.0 * 1.05)
    eu = (15.0 * 1.10 + 8.0 * 1.10) * 2.0
    na = (35.0 * 1.05) * 1.3
    assert rec["region_tot"]["Europe"] == pytest.approx(eu)
    assert rec["world"] == pytest.approx(eu + na)
    assert gc.assert_adds_up(rec) is True
    assert rec["issues"] == []


def test_flags_bad_coverage():
    airports, cov_c, cov_r, c2r = _fixture()
    cov_c = dict(cov_c); cov_c["US"] = 0.0          # non-positive coverage
    rec = gc.reconcile_levels(airports, cov_c, cov_r, c2r)
    assert any(i[0] == "coverage_country_nonpositive" for i in rec["issues"])
    with pytest.raises(AssertionError):
        gc.assert_adds_up(rec)


def test_flags_missing_region():
    airports, cov_c, cov_r, c2r = _fixture()
    c2r = dict(c2r); del c2r["FR"]
    rec = gc.reconcile_levels(airports, cov_c, cov_r, c2r)
    assert any(i[0] == "country_without_region" for i in rec["issues"])


def test_reconcile_connecting_and_tb():
    from avia_forecast import global_checks as gc
    # modest connecting: kept, no flag
    conn, flag = gc.reconcile_connecting(10.0, 3.0)
    assert conn == 3.0 and flag is None
    # negative residual: floored to zero and flagged
    conn, flag = gc.reconcile_connecting(10.0, -2.0)
    assert conn == 0.0 and flag == "negative_residual"
    # implausibly high connecting share: kept but flagged
    conn, flag = gc.reconcile_connecting(1.0, 5.0)
    assert conn == 5.0 and flag == "implausible_conx_share"
    # T-B holds after reconciliation (terminal = od + conn), fails when it doesn't
    assert gc.tb_check(3.0, 1.0, 2.0)
    assert not gc.tb_check(5.0, 1.0, 2.0)

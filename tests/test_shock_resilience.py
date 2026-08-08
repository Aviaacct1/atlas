"""shocks/resilience tests - fall and recovery measurement on controlled series.
Author: Avia Solutions."""
import pytest

from avia_forecast.shocks import (
    Shock,
    to_index,
    resilience_metrics,
    compare_premium_economy,
    forward_shock_template,
)


def test_single_shock_fall_and_recovery():
    series = {"1999": 100, "2000": 110, "2001": 90, "2002": 80, "2003": 95, "2004": 115}
    rows = resilience_metrics(series, [Shock("9/11", "2001")])
    assert len(rows) == 1
    r = rows[0]
    assert r["peak_period"] == "2000" and r["peak_value"] == 110
    assert r["trough_period"] == "2002" and r["trough_value"] == 80
    assert r["drop_frac"] == pytest.approx(30 / 110)
    assert r["periods_peak_to_trough"] == 2
    assert r["recovered"] is True
    assert r["recovery_period"] == "2004"
    assert r["periods_trough_to_recovery"] == 2
    assert r["periods_peak_to_recovery"] == 4


def test_not_recovered_within_window():
    series = {"2000": 100, "2001": 70, "2002": 80}
    r = resilience_metrics(series, [Shock("9/11", "2001")])[0]
    assert r["recovered"] is False
    assert r["recovery_period"] is None
    assert r["periods_peak_to_recovery"] is None


def test_absent_shocks_are_skipped():
    series = {"2000": 100, "2001": 90, "2002": 110}
    rows = resilience_metrics(series, [Shock("9/11", "2001"), Shock("COVID-19", "2020")])
    assert [r["shock"] for r in rows] == ["9/11"]


def test_two_shocks_partition_the_window():
    series = {"2000": 100, "2001": 80, "2002": 120, "2008": 90, "2009": 70, "2010": 130}
    rows = resilience_metrics(series, [Shock("9/11", "2001"), Shock("GFC", "2008")])
    gfc = next(r for r in rows if r["shock"] == "GFC")
    # peak must look back only to the previous onset, so 2002 (120), not earlier
    assert gfc["peak_period"] == "2002" and gfc["peak_value"] == 120
    assert gfc["trough_period"] == "2009" and gfc["trough_value"] == 70
    assert gfc["drop_frac"] == pytest.approx(50 / 120)
    assert gfc["recovery_period"] == "2010"


def test_recovery_window_to_next_vs_to_end():
    # 9/11 returns to its peak only after the SARS window has closed
    series = {"2000": 100, "2001": 80, "2002": 95, "2003": 90, "2004": 120}
    shocks = [Shock("9/11", "2001"), Shock("SARS", "2003")]
    n = next(r for r in resilience_metrics(series, shocks, recovery_window="to_next") if r["shock"] == "9/11")
    e = next(r for r in resilience_metrics(series, shocks, recovery_window="to_end") if r["shock"] == "9/11")
    assert n["recovered"] is False
    assert e["recovered"] is True and e["recovery_period"] == "2004"


def test_recovery_window_rejects_bad_value():
    with pytest.raises(ValueError):
        resilience_metrics({"2000": 100, "2001": 90}, [Shock("9/11", "2001")], recovery_window="sideways")


def test_to_index_rebases_to_100():
    idx = to_index({"2000": 50, "2001": 60, "2002": 40}, "2000")
    assert idx["2000"] == 100.0
    assert idx["2001"] == pytest.approx(120.0)
    assert idx["2002"] == pytest.approx(80.0)


def test_to_index_rejects_missing_or_zero_base():
    with pytest.raises(KeyError):
        to_index({"2000": 50}, "1999")
    with pytest.raises(ValueError):
        to_index({"2000": 0, "2001": 5}, "2000")


def test_compare_premium_falls_deeper():
    # premium drops 40%, economy 20%, same shock
    premium = {"2000": 100, "2001": 60, "2002": 105}
    economy = {"2000": 100, "2001": 80, "2002": 105}
    rows = compare_premium_economy(premium, economy, [Shock("9/11", "2001")])
    r = rows[0]
    assert r["premium_drop_frac"] == pytest.approx(0.40)
    assert r["economy_drop_frac"] == pytest.approx(0.20)
    assert r["drop_frac_diff"] == pytest.approx(0.20)   # premium fell 20 points further


def test_forward_template_shape():
    series = {"1999": 100, "2000": 110, "2001": 90, "2002": 80, "2003": 95, "2004": 115}
    rows = resilience_metrics(series, [Shock("9/11", "2001")])
    tpl = forward_shock_template(rows)
    assert tpl["n"] == 1
    assert tpl["path"][0] == 100.0
    assert min(tpl["path"]) < 100.0          # it falls
    assert tpl["path"][-1] == pytest.approx(100.0)   # and returns to the peak
    assert tpl["mean_drop_frac"] == pytest.approx(30 / 110)


def test_forward_template_empty_when_nothing_recovered():
    series = {"2000": 100, "2001": 70, "2002": 80}
    rows = resilience_metrics(series, [Shock("9/11", "2001")])
    tpl = forward_shock_template(rows)
    assert tpl["n"] == 0 and tpl["path"] == []

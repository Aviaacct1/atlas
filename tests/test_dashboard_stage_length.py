"""The dashboard's RPK basis is the engine's, never a typed constant.

Guards the 23 August 2026 change: until then dashboard.html held a typed per-region
stage length constant, so the page's RPK CAGR equalled its passenger CAGR while every
comparator's published RPK grew stage length inside it, and the reconciliation table's
matched-basis claim did not hold for RPK rows. Now the build ships a stage_length block
from config/stage_length.yaml and the page applies growth via slAt(). Author: Avia
Solutions.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from avia_forecast import stage_length as sl  # noqa: E402

PAGE = open(os.path.join(REPO, "webapp", "dashboard.html"), encoding="utf-8").read()


def test_no_typed_stage_length_constant_in_the_page():
    assert 'const SL={"Europe"' not in PAGE
    assert '"Middle East":2.9' not in PAGE


def test_page_applies_growth_from_the_bundle():
    assert "DASH.stage_length" in PAGE
    assert "slAt(" in PAGE
    # every former constant lookup is gone
    assert "SL[regKey]||SL._G" not in PAGE and "SL[rk]||SL._G" not in PAGE and "SL[r]||SL._G" not in PAGE
    # missing bundle block fails loudly, not silently
    assert "no stage_length block" in PAGE


def test_engine_fold_matches_the_yaml():
    # a directly mapped region carries its own rate
    assert sl.growth_engine("Middle East") == sl.growth("Middle East")
    assert sl.growth_engine("South America") == sl.growth("Latin America")
    # the Asia Pacific fold stays inside the range of its members
    members = [b for b, e in sl.BOEING_TO_ENGINE.items() if e == "Asia Pacific"]
    rates = [sl.growth(b) for b in members]
    g = sl.growth_engine("Asia Pacific")
    assert min(rates) <= g <= max(rates)
    # weights move the fold towards the heavier member
    heavy = {m: (1000.0 if sl.growth(m) == max(rates) else 1.0) for m in members}
    assert sl.growth_engine("Asia Pacific", heavy) > g
    # an unknown region takes the common world rate, never zero
    assert sl.growth_engine("Atlantis") == sl.growth("World") > 0

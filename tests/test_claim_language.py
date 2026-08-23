"""The BT2 claim string is Text A of the 23 August 2026 ruling, and nothing else.

John's ruling: calibrated leads with its basis named (88.8% within +-20%, 82.4% within
+-10%, n=2,915, US routes graded against DOT DB1B), blind evidence second and only as
portfolios (94% of twenty, 80% of ten), single-route blind figures never on a client
surface, and the bare phrase "calibrated accuracy" retired because it let calibrated
read as unseen. Figures verified 23 August 2026 against master_backtest_scored.csv
(fc_over_out, bt2_score.within bands: 88.8 / 82.4 exactly). Author: Avia Solutions.
"""
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(REPO, "scripts", "build_bum_candidates.py"), encoding="utf-8").read()


def test_text_a_ships_verbatim():
    assert "Calibrated on the 2,915-route training set" in SRC
    assert "graded against DOT DB1B" in SRC
    assert "88.8% within +-20%, 82.4% within" in SRC
    assert "distribution chart alongside" in SRC
    assert "portfolios of" in SRC and "94% within +-20%; portfolios of ten: 80%" in SRC
    assert "not a route-level accuracy claim" in SRC


def test_retired_wordings_are_gone():
    # the pre-ruling headline that let calibrated read as unseen
    assert "calibrated accuracy" not in SRC
    # single-route blind figures never appear in this file, not even in comments
    assert "53.7" not in SRC and "55.9" not in SRC

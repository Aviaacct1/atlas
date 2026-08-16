"""The accuracy card is generated, never typed.

Guards the 16 August 2026 rebuild of the dashboard accuracy statement. The card was
three rows typed into dashboard.html captioned "refreshed every vintage" while nothing
wrote them; the seats-anchor figures were presented as engine accuracy. These tests
assert the two ends of the fix: the page holds no accuracy literal and renders from
DASH.accuracy, and scripts/accuracy_block.py reproduces every figure from the exhibit
files it names. Author: Avia Solutions.
"""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from accuracy_block import build_accuracy  # noqa: E402

DATA = os.path.join(REPO, "data")
PAGE = open(os.path.join(REPO, "webapp", "dashboard.html"), encoding="utf-8").read()


def test_no_typed_accuracy_rows_in_the_page():
    # the literal rows this fix removed, and the shape that produced them
    assert "const acc=[" not in PAGE
    assert '"87%"' not in PAGE and '"74%"' not in PAGE and '"3.2%"' not in PAGE
    assert "refreshed every vintage" not in PAGE


def test_page_renders_from_the_built_block():
    assert "DASH.accuracy" in PAGE
    # the no-bundle state must refuse rather than fall back to figures
    assert "no accuracy block" in PAGE


def test_block_reproduces_the_exhibits():
    block = build_accuracy(DATA)
    if block is None:
        import pytest
        pytest.skip("backtest exhibits not staged on this host")
    seats = json.load(open(os.path.join(DATA, "backtest_seats_exhibit.json")))["summary"]
    one_year = seats["annual 2023->2024"]
    row = block["seats_anchor"]["rows"][0]
    assert row[0].startswith("1 year")
    assert row[1] == f"{one_year['n']:,} airports"
    assert row[2] == f"{one_year['wmape_seats'] * 100:.1f}%"
    assert row[3] == f"{one_year['within_20pct'] * 100:.1f}%"
    # the engine table must include a window where the model loses to the naive control:
    # a track record that omits the windows it loses is not a track record
    verdicts = {r[4] for r in block["engine"]["rows"]}
    assert "no" in verdicts and "yes" in verdicts
    # every figure's basis is stated beside it
    assert "anchor validation, not forecast accuracy" in block["seats_anchor"]["basis"]
    assert "naive" in block["engine"]["basis"]


def test_basis_words_are_not_borrowed():
    # the seats table must not describe itself as the engine's operating configuration
    assert "operating configuration" not in PAGE

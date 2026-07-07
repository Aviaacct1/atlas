"""Assumptions-book loader.

Design rule (Data Architecture 5.2): configuration, not code. No numeric
assumption lives in Python; everything is read from config/*.yaml, which is
reconciled one-to-one with the Excel Control sheet.
Author: Avia Solutions.
"""
from __future__ import annotations
from pathlib import Path
from functools import lru_cache
import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    with open(CONFIG_DIR / name, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def assumptions() -> dict:
    """Full assumptions book as a nested dict."""
    return _load("assumptions_book.yaml")


def regions() -> dict:
    return _load("regions.yaml")


def sources() -> dict:
    return _load("sources.yaml")


def get(path: str, default=None):
    """Dotted lookup into the assumptions book, e.g. get('reliability.T4_fit_min_r2')."""
    node = assumptions()
    for key in path.split("."):
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node

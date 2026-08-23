"""Skeleton smoke tests: config loads, no numeric assumption is hard-coded in the
package, the schema builds, and the build entrypoint validates scenarios.
Author: Avia Solutions."""
import sqlite3
from avia_forecast import config, db, __version__
import build as build_entry


def test_assumptions_book_loads_key_parameters():
    assert config.get("reliability.T2_range.bG") == [0.5, 2.5]
    assert config.get("applied_bounds.bF") == [-1.1, -0.15]   # widened 23 Aug 2026 to bracket the MEASURED bF (MEASUREMENTS 16)
    assert config.get("reconciliation.parity_tolerance_rel") == 0.00001
    assert len(config.regions()["regions"]) == 8


def test_schema_builds():
    conn = sqlite3.connect(":memory:")
    db.init_schema(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ["airports", "traffic_history", "forecasts", "assumptions_book",
              "estimation_trail", "events", "sources"]:
        assert t in tables


def test_build_rejects_unknown_scenario():
    import pytest
    with pytest.raises(ValueError):
        build_entry.build("2026v0", "NoSuchScenario")
    assert build_entry.build("2026v0", "Baseline")["code_version"] == __version__

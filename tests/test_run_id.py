"""O-21 acceptance: the run-id content hash is deterministic and sensitive, is carried in the
deliverable/extract, and the ledger binds to it. Author: Avia Solutions."""
from avia_forecast.airports import instance
from avia_forecast.outputs import run_id as R


def test_run_id_deterministic_and_sensitive():
    a = R.run_id("v99", {"domUplift": 0.005}, {"aci": "2024", "oag": "2025w"})
    b = R.run_id("v99", {"domUplift": 0.005}, {"aci": "2024", "oag": "2025w"})
    assert a == b and a.startswith("r")
    assert R.run_id("v100", {"domUplift": 0.005}, {"aci": "2024", "oag": "2025w"}) != a   # code change
    assert R.run_id("v99", {"domUplift": 0.006}, {"aci": "2024", "oag": "2025w"}) != a    # pack change
    assert R.run_id("v99", {"domUplift": 0.005}, {"aci": "2025", "oag": "2025w"}) != a    # data change


def test_output_rows_carries_run_id():
    o = instance.output_rows(instance.load("zagreb"), overrides={"domUplift": 0.004})
    assert o["meta"].get("run_id", "").startswith("r")
    # same inputs -> same run id (reproducible on demand)
    o2 = instance.output_rows(instance.load("zagreb"), overrides={"domUplift": 0.004})
    assert o["meta"]["run_id"] == o2["meta"]["run_id"]
    o3 = instance.output_rows(instance.load("zagreb"), overrides={"domUplift": 0.009})
    assert o["meta"]["run_id"] != o3["meta"]["run_id"]


def test_ledger_binds_to_run_id():
    led = {"entries": [{"target": "domUplift", "value": 0.004, "reason": "CLIENT-PLAN"}]}
    bound = R.bind_ledger(led, "rabc123")
    assert bound["run_id"] == "rabc123"

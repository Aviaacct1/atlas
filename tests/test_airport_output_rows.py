"""O-10 (engine half): instance.output_rows emits the full native deliverable row set a generic writer
consumes - every headline series, spot years, CAGRs, assumptions register and seasonality - computed
engine-side with no 007-specific logic, reconciling by construction. Author: Avia Solutions."""
from avia_forecast.airports import instance


def test_output_rows_full_set_and_reconciles():
    o = instance.output_rows(instance.load("zagreb"))
    for k in ("total", "international", "domestic", "transit", "charter", "ga",
              "non_lcc", "lcc", "commercial_atm", "landed_tonnage"):
        assert k in o["series"], k
    for y in o["years"]:
        assert abs(o["series"]["non_lcc"][y] + o["series"]["lcc"][y] - o["series"]["total"][y]) < 1.0
        assert abs(o["series"]["international"][y] + o["series"]["domestic"][y] + o["series"]["transit"][y]
                   + o["series"]["ga"][y] - o["series"]["total"][y]) < 2.0
    assert o["spots"] and o["cagr"] and o["assumptions"]
    assert o["meta"]["composition_source"] == "true_od"


def test_output_rows_total_matches_benchmark():
    cfg = instance.load("zagreb"); o = instance.output_rows(cfg)
    for y, mv, bv, d, ok in instance.benchmark_check(cfg):
        assert abs(o["series"]["total"][y] - mv) < 1.0

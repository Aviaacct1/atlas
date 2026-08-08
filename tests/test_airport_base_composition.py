"""O-6 acceptance: true-O&D vs OAG-seats base composition switch. ZAG long-haul weight moves 8.5%
(OAG direct seats) to 19.5% (true O&D) across the switch, the resolved source is stamped, and a GDD
coverage below threshold falls the source back to OAG seats. Author: Avia Solutions."""
from avia_forecast.airports import instance


def test_zagreb_longhaul_true_od_vs_oag_seats():
    cfg = instance.load("zagreb")
    lh_true, src_true = instance.long_haul_weight(cfg, "true_od")
    lh_oag, src_oag = instance.long_haul_weight(cfg, "oag_seats")
    assert abs(lh_true - 0.195) < 0.005, lh_true
    assert abs(lh_oag - 0.085) < 0.005, lh_oag
    assert src_true != src_oag


def test_gdd_coverage_falls_back_and_stamps():
    cfg = instance.load("zagreb")
    cfg = {**cfg, "base_composition": {"source": "true_od", "gdd_coverage": 0.1, "gdd_coverage_threshold": 0.6}}
    src, note = instance._composition_source(cfg)
    assert src == "oag_seats" and "fell back" in note.lower()


def test_zagreb_default_reproduces_007():
    assert all(r[-1] for r in instance.benchmark_check(instance.load("zagreb")))

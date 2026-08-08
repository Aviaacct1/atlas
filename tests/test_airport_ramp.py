"""O-5 acceptance: the net-new ramp F(y) is an engine primitive. Zagreb's 0.284->0.998 ramp is a
config entry over an explicit gross LCC path and reproduces the LCC net path; a second event type
(an entrant) carries its own ramp. Author: Avia Solutions."""
from avia_forecast.airports import instance


def test_zagreb_lcc_ramp_reproduces_net():
    cfg = instance.load("zagreb")
    blk = next(b for b in cfg["carrier_blocks"] if b["name"] == "lcc")
    assert blk["basis"] == "ramped_gross" and blk.get("ramp"), "LCC block must be a ramped_gross primitive"
    net = {int(k): float(v) for k, v in cfg["lcc_net_path"].items()}
    for y in range(cfg["meta"]["base_year"] + 1, cfg["meta"]["horizon"] + 1):
        assert abs(instance._block_pax(cfg, blk, y, None) - net[y]) < 1e-3, (y,)


def test_ramp_endpoints_and_linear_extrapolation():
    spec = {"start": 0.284, "end": 0.998, "start_year": 2026, "end_year": 2045, "shape": "linear"}
    assert abs(instance._ramp(spec, 2026) - 0.284) < 1e-9
    assert abs(instance._ramp(spec, 2045) - 0.998) < 1e-9
    assert instance._ramp(spec, 2048) > 0.998            # linear extrapolates past the end year


def test_second_event_takes_its_own_ramp():
    cfg = {"meta": {"base_year": 2025, "horizon": 2035},
           "carrier_blocks": [
               {"name": "entrant", "basis": "ramped_gross", "base_level": 0, "entrant_year": 2028,
                "gross_path": {2028: 500000, 2035: 1200000},
                "ramp": {"start": 0.5, "end": 1.0, "start_year": 2028, "end_year": 2035, "shape": "smoothstep"}}]}
    b = cfg["carrier_blocks"][0]
    assert instance._block_pax(cfg, b, 2027, None) == 0.0                       # entrant off before its year
    assert abs(instance._block_pax(cfg, b, 2028, None) - 0.5 * 500000) < 1e-6   # own ramp start 0.5
    assert abs(instance._block_pax(cfg, b, 2035, None) - 1200000) < 1e-6        # own ramp end 1.0 -> net=gross

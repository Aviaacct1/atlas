"""O-4 acceptance: carrier-block capacity paths as a first-class long-run driver. Zagreb's LCC block
reproduces from the generic primitive (not bespoke lcc_net_path handling); a two-block airport
exercises entrant events, share caps, gross-seats basis and fleet-grid upgauge through the same code
path. Author: Avia Solutions."""
from avia_forecast.airports import instance


def test_zagreb_lcc_reproduces_from_primitive():
    cfg = instance.load("zagreb")
    assert cfg.get("carrier_blocks"), "Zagreb must carry a carrier_blocks primitive"
    by, hz = cfg["meta"]["base_year"], cfg["meta"]["horizon"]
    nonlcc = cfg["base"]["non_lcc"]
    for y in range(by + 1, hz + 1):
        organic = nonlcc * instance._organic(cfg, y)
        prim = instance._carrier_net(cfg, y, organic)
        legacy = instance._lcc_net(cfg, y)            # the old bespoke lcc_net_path
        assert abs(prim - legacy) < 1e-6, (y, prim, legacy)


def _two_block_cfg():
    return {
        "meta": {"base_year": 2025, "horizon": 2030},
        "carrier_blocks": [
            {"name": "incumbent", "basis": "net_pax", "path": {2026: 100000, 2030: 200000}},
            {"name": "entrant", "basis": "gross_seats", "load_factor": 0.8,
             "entrant_year": 2028, "upgauge_pa": 0.02, "path": {2028: 100000, 2030: 150000}},
        ],
    }


def test_entrant_gate_gross_seats_and_upgauge():
    cfg = _two_block_cfg()
    b_inc, b_ent = cfg["carrier_blocks"]
    assert instance._block_pax(cfg, b_ent, 2027, None) == 0.0        # entrant off before its year
    expect = 100000 * 0.8 * (1.02 ** (2028 - 2025))                  # seats x LF x fleet-grid upgauge
    assert abs(instance._block_pax(cfg, b_ent, 2028, None) - expect) < 1e-6
    assert abs(instance._block_pax(cfg, b_inc, 2028, None) - 150000) < 1e-6   # net_pax midpoint


def test_share_cap_binds():
    cfg = {"meta": {"base_year": 2025, "horizon": 2030},
           "carrier_blocks": [{"name": "dominant", "basis": "net_pax", "share_cap": 0.30,
                               "path": {2026: 900000, 2030: 900000}}]}
    organic = 100000.0
    net = instance._carrier_net(cfg, 2027, organic)
    total = organic + net
    assert net < 900000                              # capped down from raw
    assert abs(net - 0.30 * total) < 1e-3            # share held exactly at the cap

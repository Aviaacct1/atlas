"""Engine-driven derive-layer identity tests (Cockpit E/B2 wiring). Author: Avia Solutions."""
import pytest
from avia_forecast import pipeline, fixtures
from avia_forecast.outputs import derive


def test_derive_identities_hold_from_the_run():
    res = pipeline.run()
    pilot = fixtures.make_pilot()
    d = derive.derive_demand_outputs(res, pilot)
    years = res.summary["years"]
    for y in years:
        # dom + int = O&D; transfer + O&D = terminal; total ATMs = commercial + cargo + GA
        assert d["dom_pax"][y] + d["int_pax"][y] == pytest.approx(d["od_pax"][y])
        assert d["transfer_pax"][y] + d["od_pax"][y] == pytest.approx(d["total_pax"][y])
        assert d["total_atm"][y] == pytest.approx(d["commercial_atm"][y] + d["cargo_atm"][y] + d["ga_atm"][y])
        assert d["ddfs"][y] > 0 and d["transfer_pax"][y] >= -1e-9
    assert set(derive.METRICS) <= set(d)

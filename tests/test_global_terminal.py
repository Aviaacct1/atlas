"""Phase 3b global terminal (with transfers). Author: Avia Solutions."""
import os, pytest
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from avia_forecast.paths import DATA, OEF_DIR, ACI_DIR, ACI_DECRYPT, SABRE_DB, OAG_DB, QSI_REF, PREAGG, QSI_APP, OEF_GDP_XLSX
from avia_forecast import global_terminal as gt

DATA = DATA


@pytest.mark.skipif(not os.path.exists(os.path.join(DATA, "aci_hub_calibration_2024.json")),
                    reason="ACI calibration not built")
def test_terminal_base_anchors_to_aci_and_grows():
    r = gt.run_terminal()
    y0, y1 = r.years[0], r.years[-1]
    # base year terminal matches the ACI 2024 sample (~8.9bn), by construction
    assert 8000 < r.world[y0] < 9500
    assert r.base_terminal_m == pytest.approx(r.world[y0], rel=1e-6)
    # grows, at a plausible world terminal rate near the ACI forecast
    assert r.world[y1] > r.world[y0]
    assert 0.025 < r.world_cagr < 0.045


@pytest.mark.skipif(not os.path.exists(os.path.join(DATA, "aci_hub_calibration_2024.json")),
                    reason="ACI calibration not built")
def test_emerging_region_terminal_outgrows_mature():
    r = gt.run_terminal()
    y0, y1 = r.years[0], r.years[-1]
    def cagr(s): return (s[y1] / s[y0]) ** (1 / (y1 - y0)) - 1
    assert cagr(r.by_region["Asia Pacific"]) > cagr(r.by_region["EU+UK"])
    assert cagr(r.by_region["Africa"]) > cagr(r.by_region["North America"])

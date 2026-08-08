"""qsi_calibration - capture-band launch-uplift calibration from the cohort backtest.
calibrated pax = floor x stim_basis x median_uplift(band), where floor = capture x market.
Author: Avia Solutions."""
import json, os

_TABLE = None

def _table():
    global _TABLE
    if _TABLE is None:
        fp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "qsi_capture_uplift.json")
        _TABLE = json.load(open(fp))
    return _TABLE

def band(cap):
    for b in _table()["bands"]:
        if b["cap_lo"] <= cap < b["cap_hi"]:
            return b
    return _table()["bands"][-1]

def calibrated(floor_pax, cap):
    """(calibrated pax, uplift used, band label) from a capture x market floor."""
    b = band(max(0.0, min(1.0, cap)))
    t = _table()
    return floor_pax * t["stim_basis"] * b["median_uplift"], b["median_uplift"], \
        f"{b['cap_lo']*100:.0f}-{b['cap_hi']*100:.0f}%"

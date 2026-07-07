"""BUM module acceptance tests (Cockpit build update C). Author: Avia Solutions."""
import pytest
from avia_forecast.cockpit import bum

FLEET = {"BA": {"A350-1000": 331, "A380": 469, "787-9": 216},
         "Ryanair": {"737-800": 189}}


def _line(route="MAN-JFK", airline="BA", variant="787-9", seats=216, freq=7, lf=0.85, year=2025, rc=""):
    return bum.RouteLine(route, airline, variant, seats, freq, lf, year, rc)


def test_C1_route_line_annual_pax():
    l = _line(freq=7, seats=216, lf=0.85)
    assert l.annual_pax() == pytest.approx(7 * 52 * 216 * 0.85)


def test_C2_base_year_gap_shown_attributed_never_rescaled():
    lines = [_line(seats=216, freq=7, lf=0.85, year=2025),
             _line(route="MAN-DXB", airline="Emirates", variant="A380", seats=469, freq=7, lf=0.80, year=2025)]
    total = bum.schedule_total(lines, 2025)
    ga = bum.base_year_gap(lines, 2025, pax_input=total + 3_000_000)
    assert ga.gap == pytest.approx(3_000_000)                 # gap shown
    ga.attributions["SCHED-GAP"] = 2_000_000                  # analyst attributes part of it
    assert ga.unattributed == pytest.approx(1_000_000)        # residual visible, not hidden
    assert bum.schedule_total(lines, 2025) == pytest.approx(total)   # schedule never rescaled


def test_C3_upgauge_within_carrier_fleet_only():
    l = _line(airline="BA", variant="787-9", seats=216)
    up = bum.upgauge(l, "A380", FLEET)                        # BA A380: 469 seats
    assert up.seats == 469 and up.annual_pax() > l.annual_pax()
    assert set(bum.carrier_fleet(FLEET, "BA")) == {"A350-1000", "A380", "787-9"}
    with pytest.raises(ValueError):                           # not in BA's fleet
        bum.upgauge(l, "737-800", FLEET)


def test_C5_qsi_dedup_and_reconcile():
    cands = ["MAN-JFK", "MAN-BOS", "MAN-ORD"]
    assert bum.qsi_dedup(cands, ["MAN-JFK"]) == ["MAN-BOS", "MAN-ORD"]     # dedup manual adds
    assert bum.reconcile_adds(added_pax=0.5, model_total=100.0)            # within 5%
    assert not bum.reconcile_adds(added_pax=10.0, model_total=100.0)       # wide-gap warning


def test_C6_blend_anchors_at_by1_and_tapers_to_model():
    model = {y: 100.0 * (1.02 ** (y - 2025)) for y in range(2025, 2041)}
    bum_by1 = model[2026] * 1.10                              # BUM sees 10% more near term
    b = bum.blend(model, bum_by1, base_year=2025, n_years=3)
    assert b[2026] == pytest.approx(bum_by1)                  # anchor exact at BY+1
    assert b[2029] == pytest.approx(model[2029])             # fully tapered by BY+1+N
    assert model[2027] < b[2027] < bum_by1 * 1.05            # elevated but tapering between
    assert b[2035] == pytest.approx(model[2035])             # rejoined the model path

    # a shock applied to the model path flows through the blend beyond the taper
    shocked = dict(model); shocked[2035] *= 0.85
    assert bum.blend(shocked, bum_by1, 2025, 3)[2035] == pytest.approx(shocked[2035])


def test_C7_telemetry_aggregates_reason_codes():
    lines = [_line(rc="SCHED-GAP"), _line(rc="LF-REVISION"), _line(rc="SCHED-GAP"), _line(rc="")]
    assert bum.telemetry_summary(lines) == {"SCHED-GAP": 2, "LF-REVISION": 1}

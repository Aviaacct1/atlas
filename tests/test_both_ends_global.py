"""Global-shaped both-ends test (Fable review): two modelled ends, so rho_o and
rho_d are both < 1 and the multiplicative composition + sequential attribution run
for real before the global build depends on them. Author: Avia Solutions."""
import pytest
from avia_forecast.capacity import spill as sp
from avia_forecast.aggregate import reconcile as rec


def test_both_ends_two_modelled_ends_attribution_and_reconciliation():
    # A flow between two constrained countries: origin retains 90%, destination 85%.
    flow_u = 1_000_000.0
    rho_o, rho_d = 0.90, 0.85
    be = sp.both_ends(flow_u, rho_o, rho_d)

    # multiplicative: a journey must clear both ends, so it loses more than the tighter end alone
    assert be.flow_c == pytest.approx(flow_u * rho_o * rho_d)
    assert be.flow_c < flow_u * min(rho_o, rho_d)

    # sequential attribution: origin books its own loss, destination books the cross-term
    assert be.origin_booking == pytest.approx(flow_u * (1 - rho_o))
    assert be.dest_booking == pytest.approx(flow_u * rho_o * (1 - rho_d))
    rec.check_TD(flow_u, be)                                    # the three sum to flow_u (T-D)

    # flow-level suppression reconciles with the airport-level capacity requirement within tolerance
    flow_suppression = be.origin_booking + be.dest_booking
    airport_capreq = flow_u * (1 - rho_o) + flow_u * rho_o * (1 - rho_d)
    assert rec.check_both_ends_vs_capreq(flow_suppression, airport_capreq)


def test_both_ends_symmetric_when_only_one_end_binds():
    # the UK-pilot case: destination unmodelled (rho_d = 1) reduces to origin-only
    be = sp.both_ends(2_000_000.0, 0.8, 1.0)
    assert be.dest_booking == pytest.approx(0.0)
    assert be.flow_c == pytest.approx(2_000_000.0 * 0.8)
    rec.check_TD(2_000_000.0, be)

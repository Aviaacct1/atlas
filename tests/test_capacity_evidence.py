"""Capacity evidence record and resolution layer (Capacity Method v0.4).
Author: Avia Solutions."""
from pathlib import Path

import pytest

from avia_forecast.capacity import evidence as ev
from avia_forecast.capacity import spill as sp
from avia_forecast.config import get

FRANCE = Path(__file__).resolve().parent.parent / "data" / "capacity_observations_france.csv"


# --------------------------------------------------------------------------
# The rules the France test set nearly broke
# --------------------------------------------------------------------------

def test_actual_traffic_cannot_be_entered_as_a_constraint():
    """The Nantes failure: an actual passenger figure entered as a capacity."""
    with pytest.raises(ev.EvidenceError):
        ev.Observation(iata="NTE", constraint_type="actual_traffic", value=7.1,
                       unit="pax_per_yr_m")


def test_no_limitation_and_no_figure_are_different_states():
    no_limit = ev.Observation("NCE", "terminal", declared_no_limit=True,
                              basis="coordinator_declaration")
    not_found = ev.Observation("BOD", "terminal", basis="operator_statement")
    assert no_limit.declared_no_limit and not no_limit.quantified
    assert not not_found.declared_no_limit and not not_found.quantified


def test_an_observation_cannot_both_declare_no_limit_and_carry_a_value():
    with pytest.raises(ev.EvidenceError):
        ev.Observation("NCE", "terminal", value=14.0, unit="pax_per_yr_m",
                       declared_no_limit=True)


def test_only_a_decree_may_create_a_hard_annual_cap():
    with pytest.raises(ev.EvidenceError):
        ev.Observation("ORY", "regulatory_annual_cap", value=250000, unit="mvts_per_yr",
                       basis="operator_statement")
    ok = ev.Observation("ORY", "regulatory_annual_cap", value=250000, unit="mvts_per_yr",
                        basis="regulator_decree")
    assert ok.quantified


def test_preference_order_picks_the_coordinator_over_the_operator():
    obs = [
        ev.Observation("XXX", "runway", 40, "mvts_per_hr", basis="masterplan", obs_id="m"),
        ev.Observation("XXX", "runway", 46, "mvts_per_hr", basis="coordinator_declaration", obs_id="c"),
        ev.Observation("XXX", "runway", 52, "mvts_per_hr", basis="eurocontrol_airport_corner", obs_id="e"),
    ]
    assert ev.preferred(obs, "runway").obs_id == "c"


def test_superseded_observations_stay_in_the_record_but_are_not_used():
    obs = [
        ev.Observation("XXX", "runway", 40, "mvts_per_hr", basis="coordinator_declaration",
                       obs_id="old", superseded_by="new"),
        ev.Observation("XXX", "runway", 46, "mvts_per_hr", basis="eurocontrol_airport_corner",
                       obs_id="new"),
    ]
    assert ev.preferred(obs, "runway").obs_id == "new"
    assert len(obs) == 2


def test_checked_requires_two_different_names():
    o = ev.Observation("XXX", "runway", 40, "mvts_per_hr", basis="coordinator_declaration",
                       entered_by="S Parry", checked_by="S Parry")
    assert not o.checked
    o2 = ev.Observation("XXX", "runway", 40, "mvts_per_hr", basis="coordinator_declaration",
                        entered_by="S Parry", checked_by="J Kingham")
    assert o2.checked


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------

def demand(start=10.0, growth=0.03, years=range(2025, 2046)):
    return {y: start * (1 + growth) ** (y - min(years)) for y in years}


def flat_share(value=0.0005, years=range(2025, 2046)):
    return {y: value for y in years}


def falling_share(base=0.0005, years=range(2025, 2046), rate=0.01):
    return {y: base * (1 - rate) ** (y - min(years)) for y in years}


def test_airfield_test_binds_and_names_the_subsystem():
    obs = [ev.Observation("XXX", "runway", 30, "mvts_per_hr",
                          rate_basis="declared_with_delay_tolerance",
                          basis="coordinator_declaration", obs_id="r1")]
    res = ev.resolve("XXX", obs, demand(), flat_share(), seats_per_mvt=150, load_factor=0.82)
    assert res.state == "constrained_evidenced"
    assert res.binding_test == "airfield"
    assert res.binding_year is not None
    assert res.k_annual_pax_m > 0


def test_a_falling_share_pushes_the_binding_year_out():
    """The whole point of section 11.1: holding the share flat brings the constraint
    forward and overstates the requirement."""
    obs = [ev.Observation("XXX", "runway", 45, "mvts_per_hr",
                          basis="coordinator_declaration", obs_id="r1")]
    flat = ev.resolve("XXX", obs, demand(), flat_share())
    fall = ev.resolve("XXX", obs, demand(), falling_share())
    assert fall.binding_year > flat.binding_year
    assert fall.k_annual_pax_m > flat.k_annual_pax_m


def test_no_limitation_records_not_applicable_not_not_found():
    obs = [
        ev.Observation("NCE", "terminal", declared_no_limit=True,
                       basis="coordinator_declaration", source_title="COHOR Nice", season="S26"),
        ev.Observation("NCE", "runway", 40, "mvts_per_hr", basis="coordinator_declaration"),
    ]
    res = ev.resolve("NCE", obs, demand(), flat_share())
    assert res.tests_not_run["terminal"].startswith("not applicable")
    assert "no limitation" in res.statement


def test_untranscribed_images_are_reported_as_such():
    obs = [ev.Observation("NTE", "runway", None, "mvts_per_hr",
                          basis="coordinator_declaration", machine_readable=False)]
    res = ev.resolve("NTE", obs, demand(), flat_share())
    assert res.state == "constraint_known_not_quantified"
    assert res.tests_not_run["airfield"] == "parameters held but not transcribed"
    assert "images" in res.statement
    # unresolved means unconstrained downstream, and says so
    assert ev.capacity_for(res) == 0.0
    assert sp.airport_solve(5e6, ev.capacity_for(res)).retention == 1.0


def test_committed_steps_lift_the_annual_terminal_test():
    obs = [ev.Observation("BVA", "composite_design_annual", 5.6, "pax_per_yr_m",
                          basis="operator_statement")]
    without = ev.resolve("BVA", obs, demand(start=5.0), flat_share())
    with_step = ev.resolve("BVA", obs, demand(start=5.0), flat_share(),
                           committed_steps=[(2029, 2.4)])
    assert with_step.binding_year > without.binding_year


def test_statutory_cap_is_tested_and_can_bind():
    obs = [
        ev.Observation("ORY", "runway", 80, "mvts_per_hr", basis="coordinator_declaration"),
        ev.Observation("ORY", "regulatory_annual_cap", 250000, "mvts_per_yr",
                       basis="regulator_decree", obs_id="cap"),
    ]
    res = ev.resolve("ORY", obs, demand(start=30.0), flat_share())
    assert any(t.name == "statutory_cap" for t in res.tests_run)


def test_the_tighter_of_runway_and_atc_is_used():
    obs = [
        ev.Observation("NCE", "runway", 50, "mvts_per_hr", basis="coordinator_declaration", obs_id="r"),
        ev.Observation("NCE", "atc", 34, "mvts_per_hr", basis="coordinator_declaration", obs_id="a"),
    ]
    res = ev.resolve("NCE", obs, demand(), flat_share())
    airfield = [t for t in res.tests_run if t.name == "airfield"][0]
    assert airfield.obs_id == "a"


def test_range_flag_raised_when_two_tests_bind_close_together():
    obs = [
        ev.Observation("XXX", "runway", 45, "mvts_per_hr", basis="coordinator_declaration"),
        ev.Observation("XXX", "composite_design_annual", 12.0, "pax_per_yr_m",
                       basis="operator_statement"),
    ]
    res = ev.resolve("XXX", obs, demand(), flat_share())
    assert res.range_flag
    assert "range" in res.range_note


def test_tests_not_run_are_always_recorded():
    obs = [ev.Observation("XXX", "runway", 30, "mvts_per_hr", basis="coordinator_declaration")]
    res = ev.resolve("XXX", obs, demand(), flat_share())
    assert "stands" in res.tests_not_run and "statutory_cap" in res.tests_not_run
    assert "Tests not run" in res.statement


def test_statement_carries_no_em_or_en_dashes():
    obs = ev.load_observations(FRANCE)
    for iata in {o.iata for o in obs}:
        res = ev.resolve(iata, obs, demand(), flat_share())
        assert "—" not in res.statement and "–" not in res.statement


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def test_actual_above_recorded_capacity_blocks():
    """Would have caught Nice (15.1m actual against a 14.0m record) with nobody reading."""
    f = ev.check_actual_vs_k("NCE", actual_pax_m=15.1, k_annual_pax_m=14.0)
    assert f.flagged and f.blocking
    ok = ev.check_actual_vs_k("LYS", actual_pax_m=10.5, k_annual_pax_m=13.0)
    assert not ok.flagged


def test_a_declared_cap_explains_running_at_the_ceiling():
    f = ev.check_actual_vs_k("ORY", 34.5, 34.0, has_statutory_cap=True)
    assert not f.flagged


def test_observed_peak_above_declared_flags_and_carries_the_level3_caveat():
    f = ev.check_observed_peak_vs_declared("XXX", 52.0, 46.0, level3=True)
    assert f.flagged and "lower bound" in f.detail
    f2 = ev.check_observed_peak_vs_declared("YYY", 30.0, 46.0)
    assert not f2.flagged


# --------------------------------------------------------------------------
# The France seed
# --------------------------------------------------------------------------

def test_france_seed_loads_and_holds_the_expected_shape():
    obs = ev.load_observations(FRANCE)
    airports = ev.by_airport(obs)
    assert set(airports) == {"CDG", "ORY", "BVA", "NTE", "NCE", "MRS", "BOD", "LYS"}
    # Nantes and Bordeaux carry no quantified capacity at all, by design
    assert not any(o.quantified for o in airports["NTE"])
    assert not any(o.quantified for o in airports["BOD"])
    # Nice terminal is declared unlimited and the operator figure is superseded
    nce = {o.obs_id: o for o in airports["NCE"]}
    assert nce["FR-NCE-01"].declared_no_limit
    assert nce["FR-NCE-04"].superseded_by == "FR-NCE-01"
    # Orly's cap is recorded without a figure, deliberately
    ory_cap = [o for o in airports["ORY"] if o.constraint_type == "regulatory_annual_cap"][0]
    assert not ory_cap.quantified and "not assumed" in ory_cap.notes
    # every COHOR parameter row is flagged as not machine readable
    cohor = [o for o in obs if "COHOR" in o.source_title and o.constraint_type in ("runway", "atc")]
    assert cohor and all(not o.machine_readable for o in cohor)


def test_nice_resolution_reads_as_the_worked_example():
    obs = ev.load_observations(FRANCE)
    res = ev.resolve("NCE", obs, demand(start=15.1), flat_share())
    assert res.state == "constraint_known_not_quantified"
    assert res.tests_not_run["terminal"].startswith("not applicable")
    assert res.tests_not_run["airfield"] == "parameters held but not transcribed"
    assert "no limitation" in res.statement and "images" in res.statement


def test_engine_contract_unchanged():
    """resolve() feeds spill.airport_solve exactly as the v0.1 register loader did."""
    obs = [ev.Observation("XXX", "composite_design_annual", 20.0, "pax_per_yr_m",
                          basis="operator_statement")]
    res = ev.resolve("XXX", obs, demand(), flat_share())
    K = ev.capacity_for(res)
    assert K > 0
    solve = sp.airport_solve(25e6, K)
    assert solve.retention < 1.0 and solve.spill > 0


# --------------------------------------------------------------------------
# The three ways a test can fail to run are three different answers.
# Found in the France harvest of 3 August 2026, where all three occur.
# --------------------------------------------------------------------------

def _flat(v, y0=2026, y1=2046):
    return {y: v for y in range(y0, y1)}


def _resolve_with(obs, iata):
    return ev.resolve(iata, obs, _flat(5.0), _flat(0.00035))


def test_level_1_no_declaration_is_not_an_unread_document():
    """Bordeaux is IATA Level 1, so COHOR publishes nothing and never will.

    Reporting that as 'parameters held but not transcribed' sends someone
    hunting for a document that does not exist, and hides the fact that a
    Level 1 designation is itself evidence of headroom.
    """
    obs = [ev.Observation("BOD", "runway", unit="mvts_per_hr",
                          basis=ev.NO_DECLARATION, obs_id="b")]
    res = _resolve_with(obs, "BOD")
    msg = res.tests_not_run["airfield"]
    assert "no capacity" in msg and "confirmed" in msg
    assert "transcribed" not in msg and "not quantified" not in msg


def test_an_image_still_awaiting_transcription_reads_as_held_not_absent():
    obs = [ev.Observation("NCE", "runway", unit="mvts_per_hr",
                          basis="coordinator_declaration",
                          machine_readable=False, obs_id="n")]
    res = _resolve_with(obs, "NCE")
    assert "not transcribed" in res.tests_not_run["airfield"]


def test_a_figure_in_an_unconvertible_unit_is_not_reported_as_absent():
    """Figari declares its terminal limit as a count of check-in banks.

    A real published figure that the engine cannot convert without the
    airport's allocation table. That is not the same as nothing published,
    and the register exists to keep the two apart.
    """
    obs = [ev.Observation("FSC", "terminal", value=9, unit="check_in_banks",
                          basis="coordinator_declaration", obs_id="f")]
    res = _resolve_with(obs, "FSC")
    msg = res.tests_not_run["terminal"]
    assert "cannot convert" in msg and "check_in_banks" in msg
    assert msg != "no published figure found"


def test_the_three_absent_states_are_all_distinct():
    a = _resolve_with([ev.Observation("A", "runway", unit="mvts_per_hr",
                                      basis=ev.NO_DECLARATION, obs_id="a")], "A")
    b = _resolve_with([ev.Observation("B", "runway", unit="mvts_per_hr",
                                      basis="coordinator_declaration",
                                      machine_readable=False, obs_id="b")], "B")
    c = _resolve_with([], "C")
    msgs = {a.tests_not_run["airfield"], b.tests_not_run["airfield"],
            c.tests_not_run["airfield"]}
    assert len(msgs) == 3


def test_the_france_harvest_file_loads_and_covers_all_seventeen_airports():
    path = Path(__file__).resolve().parents[1] / "data" / \
        "capacity_observations_france_harvest.csv"
    if not path.exists():
        pytest.skip("France harvest file not present")
    obs = ev.load_observations(path)
    ba = ev.by_airport(obs)
    assert len(ba) == 17, f"expected all 17 COHOR airports, got {sorted(ba)}"
    # Every observation carries a source, which is the anti-invention guard.
    missing = [o.obs_id for o in obs if not (o.source_url or o.source_title)]
    assert not missing, f"observations with no source: {missing}"

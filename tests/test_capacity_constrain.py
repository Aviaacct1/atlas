"""End to end wiring: schedules to a constrained forecast (Capacity Method v0.4).
Author: Avia Solutions."""
import pytest

from avia_forecast.capacity import constrain, evidence, peakhour as ph


def fit():
    obs = []
    for i in range(25):
        base = 1.0 + i * 1.5
        for j, y in enumerate(range(2015, 2020)):
            annual = base * (1.03 ** j)
            peak = 0.004 * (annual * 1e6) ** 0.85
            obs.append(ph.PeakObs(f"A{i:02d}", y, annual, peak, intl_share=0.5,
                                  seasonality=1 / 12, convention="busy_30th"))
    return ph.fit_peak_share(obs)


def base_obs(iata="XXX", annual_pax_m=10.0, share=0.0005, constrained=False):
    o = ph.PeakObs(iata, 2025, annual_pax_m, share * annual_pax_m * 1e6,
                   intl_share=0.5, seasonality=1 / 12, constrained=constrained,
                   convention="busy_30th")
    o.annual_mvts, o.peak_hour_mvts = 200_000, 40.0
    return o


def demand(start=10.0, growth=0.03, years=range(2025, 2046)):
    return {y: start * (1 + growth) ** (y - min(years)) for y in years}


def runway(iata="XXX", rate=45):
    return [evidence.Observation(iata, "runway", rate, "mvts_per_hr",
                                 basis="coordinator_declaration")]


# --------------------------------------------------------------------------

def test_the_share_falls_across_the_forecast():
    path, basis, _ = constrain.build_share_path(fit(), base_obs(), demand())
    years = sorted(path)
    assert path[years[-1]] < path[years[0]]
    assert basis == "observed"


def test_a_constrained_airport_is_anchored_on_the_fit_not_on_its_own_peak():
    """Its filed peak reports the declaration, so projecting from it would carry the
    constraint into the thing meant to detect it."""
    _, basis, reason = constrain.build_share_path(fit(), base_obs(constrained=True), demand())
    assert basis == "fitted"
    assert "declared parameter" in reason


def test_end_to_end_gives_a_binding_year_and_a_spill_path():
    r = constrain.constrain_airport("XXX", runway(), demand(), base_obs(), fit())
    assert r.binding_year is not None
    assert r.constrained[max(r.constrained)] <= r.unconstrained[max(r.unconstrained)]
    assert r.spill[max(r.spill)] > 0


def test_the_binding_year_comes_back_as_a_range():
    """The share is projected, not observed, and its median error against 2025 is 15%.
    A single binding year is not supported by the evidence."""
    r = constrain.constrain_airport("XXX", runway(), demand(), base_obs(), fit())
    early, late = r.binding_range
    assert early is not None and late is not None
    assert early <= r.binding_year <= late
    assert late > early
    assert "range of" in r.resolution.statement


def test_an_airport_with_no_observation_is_skipped_not_assumed():
    """Saying nothing is the honest output. Assuming an airport has room is not."""
    panel = [base_obs("AAA")]
    results, skipped = constrain.constrain_all(runway("AAA"), {"BBB": demand()},
                                               panel, fit(), base_year=2025)
    assert results == {}
    assert "no usable peak hour observation" in skipped["BBB"]


def test_capacity_requirement_sums_the_traffic_that_cannot_be_accommodated():
    results, _ = constrain.constrain_all(
        runway("AAA") + runway("BBB"),
        {"AAA": demand(), "BBB": demand()},
        [base_obs("AAA"), base_obs("BBB")], fit(), base_year=2025)
    last = max(demand())
    total = constrain.capacity_requirement(results, last)
    assert total == pytest.approx(sum(r.spill[last] for r in results.values()))
    assert total > 0


def test_headroom_ranking_finds_the_airports_with_room():
    """The other half of the picture: when a hub fills up the spilt traffic has to go
    to a neighbour, and the engine can only route it if it knows who has room."""
    obs = runway("FULL", 20) + runway("ROOM", 200)
    results, _ = constrain.constrain_all(
        obs, {"FULL": demand(), "ROOM": demand()},
        [base_obs("FULL"), base_obs("ROOM")], fit(), base_year=2025)
    ranking = constrain.headroom_ranking(results, 2025)
    assert ranking[0][0] == "ROOM"
    assert ranking[0][1] > 0


def test_capacity_rises_across_the_forecast_as_the_share_falls():
    """The same runway carries more passengers a year later on, because the peak hour
    share falls as the airport grows. Holding a single K flat across the horizon would
    throw away the entire elasticity result."""
    r = constrain.constrain_airport("XXX", runway(), demand(), base_obs(), fit())
    years = sorted(r.capacity)
    assert r.capacity[years[-1]] > r.capacity[years[0]]
    # and the constrained traffic follows it up rather than sitting on a flat ceiling
    assert r.constrained[years[-1]] > r.constrained[years[0]]


def test_capacity_by_year_takes_the_tightest_test_each_year():
    obs = (runway("YYY", 45)
           + [evidence.Observation("YYY", "composite_design_annual", 11.0, "pax_per_yr_m",
                                   basis="operator_statement")])
    r = constrain.constrain_airport("YYY", obs, demand(), base_obs("YYY"), fit())
    for y, k in r.capacity.items():
        assert k <= 11.0 + 1e-9        # the annual design figure binds where it is lower

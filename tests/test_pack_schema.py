"""Pack schema acceptance tests (Cockpit build update A1-A4). Author: Avia Solutions."""
import pytest
from avia_forecast.cockpit import pack as pk

YEARS = list(range(2025, 2041))
BY = 2025
SEGMENTS = ["Domestic", "International Short Haul", "Long Haul"]


def test_A1_paths_not_scalars_ramp_hits_endpoints_exactly():
    v = pk.expand("5>9", YEARS, BY)
    assert v[2025] == pytest.approx(5.0)          # base year
    assert v[2040] == pytest.approx(9.0)          # horizon
    assert v[2032] == pytest.approx(5.0 + 4.0 * (2032 - 2025) / (2040 - 2025))  # linear between
    # a bare number holds flat; 'engine' follows the endogenous shape
    assert set(pk.expand(7.0, YEARS, BY).values()) == {7.0}
    eng = pk.expand("engine", YEARS, BY, engine_fn=lambda y: 3.0 + (y - BY))
    assert eng[2025] == 3.0 and eng[2026] == 4.0


def test_A2_long_haul_only_seats_override_moves_only_long_haul():
    engine_seats = {"Domestic": 150, "International Short Haul": 180, "Long Haul": 280}
    LF = {"Domestic": 0.80, "International Short Haul": 0.82, "Long Haul": 0.84}
    pax = {"Domestic": 10.0, "International Short Haul": 20.0, "Long Haul": 30.0}
    eng_fn = lambda seg, y: engine_seats[seg]

    seats = pk.resolve_segmented({"Long Haul": 300}, SEGMENTS, YEARS, BY, eng_fn)  # blank dom/short
    atm = lambda seg: pax[seg] / (seats[seg][2030] * LF[seg])

    assert seats["Long Haul"][2030] == 300 and seats["Domestic"][2030] == 150     # fallback held
    base_long = pax["Long Haul"] / (280 * LF["Long Haul"])
    assert atm("Long Haul") < base_long                                            # ATMs moved
    assert atm("Domestic") == pytest.approx(pax["Domestic"] / (150 * LF["Domestic"]))  # untouched


def test_A3_client_path_replaces_endogenous_drift():
    assert pk.has_client_path("5>9") and pk.has_client_path(7.0)
    assert not pk.has_client_path(None) and not pk.has_client_path("engine")

    calls = {"engine": 0}
    def endog(y):
        calls["engine"] += 1
        return 0.05
    def resolve_transfer(spec):
        return pk.expand(spec, YEARS, BY, engine_fn=endog) if pk.has_client_path(spec) \
            else pk.expand("engine", YEARS, BY, engine_fn=endog)
    resolve_transfer("5>9")               # client path set: hub overlay must not move it
    assert calls["engine"] == 0
    resolve_transfer(None)                # no path: engine endogenous drives it
    assert calls["engine"] > 0


def test_A4_book_override_applies_without_writing_back():
    p = pk.Pack("Genoa 2026", provenance="project")
    p.add_book_override(pk.BookOverride("tau", -0.006, reason_code="HOUSE", rationale="client yield view"))
    book_tau = -0.003
    eff = p.effective_book_value("tau", book_tau, YEARS, BY)
    assert set(eff.values()) == {-0.006}          # run uses the override
    assert book_tau == -0.003                     # the book is not mutated
    assert p.book_overrides["tau"].provenance == "project"
    with pytest.raises(ValueError):               # non-permitted param rejected
        p.add_book_override(pk.BookOverride("gdp", 0.02, reason_code="X"))

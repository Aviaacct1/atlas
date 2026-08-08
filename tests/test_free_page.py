"""O-15 acceptance (generator): the per-airport free page renders for a registered airport, a residual
pseudo-airport and an unregistered-capacity airport, with honest stamps in each case, and passes the
licence filter. Author: Avia Solutions."""
from avia_forecast.outputs import free_page, licence

EXTRACT = {
    "years": [2025, 2035, 2045, 2060],
    "meta": {"vintage": "v2026.1", "error_record": None},
    "airports": {
        "LHR": {"name": "London Heathrow", "term_u": [80, 95, 105, 120], "term_c": [80, 90, 95, 100],
                "capacity_source": "register", "pseudo": False},
        "_RESID_HR": {"name": "Croatia residual", "term_u": [2, 3, 4, 5], "term_c": [2, 3, 4, 5],
                      "capacity_source": None, "pseudo": True},
        "XXX": {"name": "Unregistered City", "term_u": [5, 7, 9, 12], "term_c": [5, 7, 9, 12],
                "capacity_source": "illustrative", "pseudo": False},
    }}


def test_registered_airport_shows_cap_date_and_vintage():
    pg = free_page.per_airport_page(EXTRACT, "LHR")
    assert pg["capacity_date"] == 2035 and not pg["pseudo"]
    assert pg["vintage"] == "v2026.1"
    assert "no published error record" in pg["error_record"]
    ok, _ = licence.licence_filter(pg)
    assert ok


def test_residual_pseudo_airport_stamped():
    pg = free_page.per_airport_page(EXTRACT, "_RESID_HR")
    assert pg["pseudo"] and any("residual" in s for s in pg["stamps"])


def test_unregistered_capacity_stamped_illustrative():
    pg = free_page.per_airport_page(EXTRACT, "XXX")
    assert any("illustrative" in s for s in pg["stamps"]) and pg["capacity_date"] is None

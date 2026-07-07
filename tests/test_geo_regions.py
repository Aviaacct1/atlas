"""Global ISO2 -> region map (geo/regions_iso2). Author: Avia Solutions."""
from avia_forecast.geo import regions_iso2 as g


def test_region_assignments_match_pilot_scheme():
    cases = {
        "GB": "EU+UK", "DE": "EU+UK", "IE": "EU+UK",
        "NO": "Other Europe", "CH": "Other Europe", "TR": "Other Europe", "RU": "Other Europe",
        "AE": "Middle East", "SA": "Middle East", "IR": "Middle East",
        "ZA": "Africa", "EG": "Africa", "NG": "Africa",
        "US": "North America", "CA": "North America", "MX": "North America", "JM": "North America",
        "BR": "South America", "AR": "South America", "CO": "South America",
        "CN": "Asia Pacific", "IN": "Asia Pacific", "JP": "Asia Pacific", "AU": "Asia Pacific",
    }
    for code, region in cases.items():
        assert g.region_for_iso2(code) == region, code


def test_region_sets_are_disjoint():
    seen = {}
    for region, codes in g._REGION_SETS.items():
        for c in codes:
            assert c not in seen, f"{c} in both {seen.get(c)} and {region}"
            seen[c] = region


def test_unmapped_returns_none_no_silent_bucketing():
    assert g.region_for_iso2("ZZ") is None
    assert g.region_for_iso2(None) is None


def test_dest_region_domestic_is_relative():
    assert g.dest_region("GB", "GB") == "Domestic"
    assert g.dest_region("GB", "FR") == "EU+UK"
    assert g.dest_region("US", "MX") == "North America"   # cross-border, not domestic
    assert g.dest_region("CN", "CN") == "Domestic"

"""geo/regions_iso2 - ISO2 country code to the 8-region model (Method Spec 1.1,
Annex A), consistent with config/country_region.yaml used on the UK pilot.
Author: Avia Solutions.

The scheme (from the UK pilot map, extended worldwide):
  EU+UK          EU27 + United Kingdom + Gibraltar
  Other Europe   geographic Europe outside the EU (incl Norway, Switzerland,
                 Iceland), plus Turkey, Russia and the Caucasus
  Middle East    Arabian peninsula + Levant + Iran/Iraq
  Africa         the whole continent
  Asia Pacific   South, East, Central and South-East Asia plus Oceania
  North America  USA, Canada, Mexico, Central America and the Caribbean
  South America  the South American continent
"Domestic" is relative (same country as the origin) and is resolved by the caller,
not stored here. region_for_iso2 returns None for an unmapped code so nothing is
silently bucketed (Method Spec: no silent bucketing)."""
from __future__ import annotations

EU_UK = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
    "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES",
    "SE", "GB", "GI",
}
OTHER_EUROPE = {
    "AL", "AD", "AM", "AZ", "BA", "BY", "CH", "FO", "GE", "GG", "IS", "IM", "JE",
    "LI", "MC", "MD", "ME", "MK", "NO", "RS", "RU", "SM", "TR", "UA", "VA", "XK",
    "SJ", "AX",
}
MIDDLE_EAST = {
    "AE", "BH", "IL", "IQ", "IR", "JO", "KW", "LB", "OM", "PS", "QA", "SA", "SY", "YE",
}
AFRICA = {
    "DZ", "AO", "BJ", "BW", "BF", "BI", "CV", "CM", "CF", "TD", "KM", "CG", "CD",
    "CI", "DJ", "EG", "GQ", "ER", "SZ", "ET", "GA", "GM", "GH", "GN", "GW", "KE",
    "LS", "LR", "LY", "MG", "MW", "ML", "MR", "MU", "YT", "MA", "MZ", "NA", "NE",
    "NG", "RE", "RW", "SH", "ST", "SN", "SC", "SL", "SO", "ZA", "SS", "SD", "TZ",
    "TG", "TN", "UG", "ZM", "ZW", "EH",
}
NORTH_AMERICA = {
    "US", "CA", "MX",
    "BZ", "CR", "SV", "GT", "HN", "NI", "PA",                            # Central America
    "AG", "AI", "AW", "BS", "BB", "BM", "VG", "KY", "CU", "CW", "DM",    # Caribbean
    "DO", "GD", "GP", "HT", "JM", "MQ", "MS", "PR", "BL", "KN", "LC",
    "MF", "VC", "SX", "TT", "TC", "VI", "BQ", "GL", "PM",
}
SOUTH_AMERICA = {
    "AR", "BO", "BR", "CL", "CO", "EC", "FK", "GF", "GY", "PE", "PY", "SR", "UY", "VE",
}
ASIA_PACIFIC = {
    "AF", "PK", "IN", "BD", "LK", "NP", "BT", "MV",                      # South Asia
    "CN", "HK", "MO", "TW", "JP", "KP", "KR", "MN",                      # East Asia
    "KZ", "KG", "TJ", "TM", "UZ",                                        # Central Asia
    "BN", "KH", "ID", "LA", "MY", "MM", "PH", "SG", "TH", "TL", "VN",    # SE Asia
    "AU", "NZ", "FJ", "PG", "SB", "VU", "NC", "PF", "WS", "TO", "KI",    # Oceania
    "FM", "MH", "NR", "PW", "TV", "CK", "NU", "AS", "GU", "MP",
    "NF", "CX", "CC", "WF", "PF",
}

_REGION_SETS = {
    "EU+UK": EU_UK,
    "Other Europe": OTHER_EUROPE,
    "Middle East": MIDDLE_EAST,
    "Africa": AFRICA,
    "North America": NORTH_AMERICA,
    "South America": SOUTH_AMERICA,
    "Asia Pacific": ASIA_PACIFIC,
}

_LOOKUP = {code: region for region, codes in _REGION_SETS.items() for code in codes}


def region_for_iso2(code: str | None) -> str | None:
    """World region for an ISO2 country code, or None if unmapped."""
    if not code:
        return None
    return _LOOKUP.get(code.strip().upper())


def dest_region(origin_iso2: str | None, dest_iso2: str | None) -> str | None:
    """Model region of a destination relative to an origin: 'Domestic' when the two
    countries match, otherwise the destination's world region (None if unmapped)."""
    if origin_iso2 and dest_iso2 and origin_iso2.upper() == dest_iso2.upper():
        return "Domestic"
    return region_for_iso2(dest_iso2)

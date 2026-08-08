"""OEF GDP + population ingest (per-country GDP history and forecast). Author: Avia Solutions.

Parses the OEF world file on E: (Annual sheet, GDP constant prices + Population, total),
maps OEF location names to ISO2, and writes per-country series 1980-2050 to E: data. This
supplies BOTH per-country forward GDP (replacing the regional global_drivers assumption) and
history for the airport income-elasticity regressions. OEF is licensed: internal use only,
never redistributed.
"""
from __future__ import annotations
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from avia_forecast.io_safe import dump_atomic
from avia_forecast.paths import DATA, OEF_DIR, ACI_DIR, ACI_DECRYPT, SABRE_DB, OAG_DB, QSI_REF, PREAGG, QSI_APP, OEF_GDP_XLSX
import json, os, re
import openpyxl, pycountry

OEF = OEF_GDP_XLSX
DATA = DATA

OVERRIDE = {
    "Korea": "KR", "Korea, Rep": "KR", "South Korea": "KR", "Russia": "RU", "Iran": "IR",
    "Vietnam": "VN", "Viet Nam": "VN", "Taiwan": "TW", "Hong Kong": "HK", "Macao": "MO",
    "Macau": "MO", "Czech Republic": "CZ", "Czechia": "CZ", "Slovak Republic": "SK",
    "Turkey": "TR", "Turkiye": "TR", "Yemen, Rep": "YE", "Egypt": "EG", "Venezuela": "VE",
    "Bolivia": "BO", "Laos": "LA", "Syria": "SY", "Tanzania": "TZ", "Moldova": "MD",
    "Brunei": "BN", "Cote d'Ivoire": "CI", "Ivory Coast": "CI", "Kyrgyzstan": "KG",
    "Macedonia": "MK", "North Macedonia": "MK", "Swaziland": "SZ", "Eswatini": "SZ",
    "Cape Verde": "CV", "Gambia, The": "GM", "Bahamas, The": "BS", "United States": "US",
    "United Kingdom": "GB", "Congo-Brazzaville": "CG", "Congo-Kinshasa": "CD",
    "Democratic Republic of the Congo": "CD", "West Bank & Gaza": "PS", "Palestine": "PS",
    "Hong Kong SAR": "HK", "Slovakia": "SK", "Brunei Darussalam": "BN",
    "Iran, Islamic Rep.": "IR", "Venezuela, RB": "VE", "Hong Kong, China": "HK",
    "Macao, China": "MO", "Lao PDR": "LA", "Congo, Dem. Rep.": "CD", "Congo, Rep.": "CG",
    "East Timor": "TL", "Gambia, The": "GM", "St. Kitts and Nevis": "KN", "St. Lucia": "LC",
    "St. Vincent / Grenadines": "VC", "Virgin Islands (U.S.)": "VI", "Virgin Islands (UK)": "VG",
}
AGG = re.compile(r"(Economies|World|Africa|Americas|Asia|Europe|Emerging|Advanced|"
                 r"Union|Area|OECD|Middle East|Latin|Caribbean|Pacific|Sub-Saharan|"
                 r"income|Region|G7|G20|BRICS|ASEAN|EU\b)", re.I)


def _iso2(name):
    n = re.sub(r"\s+", " ", name.strip())
    if n in OVERRIDE:
        return OVERRIDE[n]
    if AGG.search(n):
        return None
    try:
        c = pycountry.countries.get(name=n) or pycountry.countries.get(common_name=n)
        if c:
            return c.alpha_2
    except Exception:
        pass
    try:
        res = pycountry.countries.search_fuzzy(n)
        if res:
            return res[0].alpha_2
    except Exception:
        return None
    return None


def run():
    wb = openpyxl.load_workbook(OEF, read_only=True, data_only=True)
    ws = wb["Annual"]
    rows = list(ws.iter_rows(values_only=True))
    hdr = rows[0]
    ycol = {int(str(c)): i for i, c in enumerate(hdr) if str(c).strip().isdigit()}
    years = sorted(ycol)

    def series(row):
        out = {}
        for y in years:
            v = row[ycol[y]]
            try:
                out[y] = float(v)
            except (TypeError, ValueError):
                pass
        return out

    gdp, pop = {}, {}
    unmatched = []
    for r in rows[1:]:
        loc, ind = r[0], r[1]
        if not loc or not ind:
            continue
        ind = str(ind)
        if "GDP, constant" in ind:
            iso = _iso2(str(loc))
            if iso:
                gdp[iso] = series(r)
            elif not AGG.search(str(loc)):
                unmatched.append(str(loc))
        elif "Population, total" in ind:
            iso = _iso2(str(loc))
            if iso:
                pop[iso] = series(r)
    wb.close()

    os.makedirs(DATA, exist_ok=True)
    dump_atomic({"_source": "OEF 31Jul2024, GDP constant 2015 US$ + Population; internal only",
               "gdp": {k: {str(y): v for y, v in s.items()} for k, s in gdp.items()},
               "pop": {k: {str(y): v for y, v in s.items()} for k, s in pop.items()}}, os.path.join(DATA, "oef_gdp_pop_by_iso2.json"))
    print(f"GDP countries: {len(gdp)}   population countries: {len(pop)}   years {years[0]}-{years[-1]}")
    if unmatched:
        print("unmatched country-like locations:", sorted(set(unmatched))[:20])
    return gdp, pop


if __name__ == "__main__":
    run()

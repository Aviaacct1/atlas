"""Build webapp/data/history.json: real historic breakdowns from the Sabre store,
for the Observatory History page. Author: Avia Solutions.

All series are read directly from C:\\Avia\\sabre.duckdb (Sabre MI, non-directional
O&D). The cabin split, premium share, regional traffic and cabin fares are the
historic trends the forecast is built on. Sabre is class C: figures are Avia
analysis output, not a redistributed extract. Consistent basis: ND years only
(2016-2025); 2013 and 2015 are point-of-origin and are reported separately, not
mixed into the ND series.
"""
from __future__ import annotations
import json, os, sys

import duckdb

# the shocks module lives in this repo's engine package (avia_forecast/shocks)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from avia_forecast.shocks import Shock, to_index, resilience_metrics, compare_premium_economy, forward_shock_template
from avia_forecast.paths import SABRE_DB

# World scheduled passengers (millions). 1960-2022 from the knowledge library file
# "ICAO Traffic 1929-2023 (JK).xlsx", ICAO Member States Airlines, Avia Solutions
# analysis. 2023 ICAO ("The World of Air Transport in 2023", 4.3bn). 2024-2025 IATA
# (record demand; 2025 first year above 5 billion). ICAO widened reporting coverage
# around 1970, so 1960-1969 are on a narrower reporting base (flagged in the tool).
WORLD_PAX_M = {
 1960:106,1961:111,1962:121,1963:135,1964:155,1965:177,1966:200,1967:233,1968:260,1969:293,
 1970:383.0,1971:410.9,1972:450.1,1973:488.5,1974:514.5,1975:534.0,1976:576.4,1977:610.3,
 1978:678.6,1979:754.1,1980:748.3,1981:752.3,1982:765.8,1983:797.8,1984:847.9,
 1985:899.2,1986:960.0,1987:1027.9,1988:1082.5,1989:1109.5,1990:1165.2,1991:1135.2,
 1992:1145.6,1993:1142.4,1994:1233.3,1995:1303.6,1996:1391.1,1997:1456.7,1998:1471.5,
 1999:1562.3,2000:1774.4,2001:1740.7,2002:1738.9,2003:1794.6,2004:2002.8,2005:2144.9,
 2006:2263.3,2007:2462.0,2008:2500.0,2009:2488.3,2010:2707.9,2011:2883.0,2012:3016.0,
 2013:3151.0,2014:3330.0,2015:3571.0,2016:3810.0,2017:4079.0,2018:4345.0,2019:4494.0,
 2020:1792.0,2021:2300.0,2022:3250.0,2023:4300.0,2024:4900.0,2025:5200.0,
}
WORLD_COVERAGE_BREAK = 1970   # ICAO reporting coverage widened; pre-1970 narrower base

# World RPK (billions) and passenger load factor (%), 1960-2020, same ICAO source
# file (sheet ICAO_Dec22, RPK and PLF columns). Real, Avia Solutions analysis.
WORLD_RPK_BN = {
 1960:109,1961:117,1962:130,1963:147,1964:171,1965:198,1966:229,1967:273,1968:309,1969:351,
 1970:460,1971:494,1972:560,1973:618,1974:656,1975:697,1976:764,1977:818,1978:936,1979:1060,
 1980:1089,1981:1119,1982:1142,1983:1190,1984:1278,1985:1367,1986:1452,1987:1589,1988:1705,1989:1774,
 1990:1894,1991:1845,1992:1929,1993:1949,1994:2100,1995:2248,1996:2432,1997:2573,1998:2628,1999:2798,
 2000:3201,2001:3109,2002:3124,2003:3180,2004:3629,2005:3919,2006:4171,2007:4513,2008:4608,2009:4561,
 2010:4930,2011:5264,2012:5545,2013:5850,2014:6199,2015:6664,2016:7157,2017:7730,2018:8293,2019:8677,2020:2990,
 # 2021-2025 chained from the ICAO 2020 base using IATA reported RPK growth
 # (+21.8%, +64.9%, +36.8%, +10.4%, +5.3%); above 2019 from 2024.
 2021:3642,2022:6006,2023:8216,2024:9071,2025:9552,
}
WORLD_PLF = {
 1960:59.2,1961:55.2,1962:53.5,1963:53.6,1964:55.9,1965:55.9,1966:57.7,1967:57.0,1968:53.5,1969:52.0,
 1970:54.8,1971:54.1,1972:57.1,1973:57.6,1974:59.3,1975:59.1,1976:60.1,1977:60.8,1978:64.5,1979:66.0,
 1980:63.2,1981:63.7,1982:63.6,1983:64.2,1984:64.8,1985:65.7,1986:65.0,1987:67.1,1988:67.6,1989:68.0,
 1990:67.6,1991:66.4,1992:65.8,1993:64.7,1994:66.3,1995:66.9,1996:68.2,1997:69.0,1998:68.5,1999:69.1,
 2000:71.1,2001:69.2,2002:71.3,2003:71.6,2004:73.4,2005:74.9,2006:75.8,2007:76.8,2008:76.0,2009:76.7,
 2010:78.2,2011:78.0,2012:78.9,2013:79.5,2014:79.7,2015:80.2,2016:80.3,2017:81.5,2018:81.7,2019:82.4,2020:65.3,
 2021:66.9,2022:78.7,2023:82.2,2024:83.5,2025:83.6,   # 2021-2025 IATA reported load factor
}

# AMEX European Corporate Travel Index: global-average fare growth by cabin, YoY,
# Western Europe to all destinations. Knowledge library "AMEX Global Year on year
# (2000 to 2002).xls". A dated corporate-fare index (1999-2003); the premium-vs-
# economy signal at the 2001-2002 downturn is the point of interest.
AMEX_FARE_YOY = {
 "Economy":        {"2000":0.038,"2001":0.075,"2002":-0.083},
 "Business":       {"2000":0.063,"2001":0.064,"2002":0.011},
 "First":          {"2000":0.080,"2001":0.064,"2002":0.013},
}

# Airport financial benchmarks, EUR per passenger, 2009. From the proprietary
# knowledge library "Avia - European Apt Financial Database / European apt
# financial benchmarking (JK) 7Mar11.xls" (per-pax EUR rows). Single airports plus
# two hub groups (BAA, AdP). Dated 2009; a structure to refresh, not to publish.
BENCHMARKS = [
 # name, pax_m, aero, non_aero, opex, ebitda, ebitda_pct, group
 ("Copenhagen", 19.7, 10.68, 9.02, 9.58, 10.34, 0.52, False),
 ("Zurich",     21.9, 15.26, 9.52, 12.63, 12.15, 0.49, False),
 ("Brussels",   17.0, 13.91, 7.60, 9.57, 11.95, 0.56, False),
 ("Manchester", 20.4, 8.44, 8.46, 10.31, 6.59, 0.39, False),
 ("Oslo",       18.1, 9.50, 12.80, 10.76, 11.54, 0.518, False),
 ("Stockholm",  27.1, 14.18, 7.37, 16.29, 5.26, 0.244, False),
 ("Munich",     32.7, 15.65, 14.35, 25.34, 4.67, 0.156, False),
 ("BAA group",  84.3, 15.42, 13.26, 15.31, 13.37, 0.466, True),
 ("AdP group",  83.4, 17.39, 15.46, 21.73, 11.12, 0.338, True),
]

# The Sabre store resolves centrally. This module read its own QSI_SABRE variable with
# its own default until 8 August 2026, which is a second name for one location.
DB = SABRE_DB
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "history.json")

PREMIUM = ("FIRST", "BUSINESS")
ECON = ("DISCOUNT COACH", "PREMIUM COACH")
Y0, Y1 = 2016, 2025          # contiguous ND window
BASE = 2019                  # pre-COVID benchmark

con = duckdb.connect(DB, read_only=True)


def _cabin_year():
    rows = con.execute(f"""
      SELECT year,
        SUM(CASE WHEN cabin_class IN ('FIRST','BUSINESS') THEN passengers ELSE 0 END) premium,
        SUM(CASE WHEN cabin_class IN ('DISCOUNT COACH','PREMIUM COACH') THEN passengers ELSE 0 END) economy
      FROM sabre WHERE directionality='ND' AND year BETWEEN {Y0} AND {Y1}
      GROUP BY year ORDER BY year""").fetchall()
    prem = {str(y): p for y, p, e in rows}
    econ = {str(y): e for y, p, e in rows}
    share = {str(y): p / (p + e) for y, p, e in rows}
    return prem, econ, share


def _regions():
    rows = con.execute(f"""
      SELECT poo_region_name reg, year, SUM(passengers) pax
      FROM sabre WHERE directionality='ND' AND year BETWEEN {Y0} AND {Y1}
        AND poo_region_name IS NOT NULL AND poo_region_name <> 'UNASSIGNED'
      GROUP BY 1,2""").fetchall()
    by = {}
    for reg, year, pax in rows:
        by.setdefault(reg, {})[str(year)] = pax
    tot19 = {r: v.get("2019", 0) for r, v in by.items()}
    top = sorted(tot19, key=tot19.get, reverse=True)[:12]
    return {r: {y: round(by[r].get(y, 0)) for y in map(str, range(Y0, Y1 + 1))} for r in top}


def _fares():
    # pax-weighted average base fare, then rebased to a fare index (base year = 100).
    # We ship the index only, not absolute Sabre fare levels, to stay within licence.
    rows = con.execute(f"""
      SELECT year, cabin_class,
        SUM(passengers*avg_base_fare_usd)/NULLIF(SUM(passengers),0) wfare
      FROM sabre WHERE directionality='ND' AND year BETWEEN {Y0} AND {Y1}
      GROUP BY 1,2""").fetchall()
    absd = {}
    for year, cab, wf in rows:
        absd.setdefault(cab, {})[str(year)] = wf
    out = {}
    for cab, s in absd.items():
        yrs = sorted(s, key=lambda y: int(y))
        base = s[yrs[0]]
        out[cab] = {y: (round(s[y] / base * 100, 1) if (s[y] is not None and base) else None) for y in yrs}
    return out


prem, econ, share = _cabin_year()
prem_idx = to_index(prem, str(BASE))
econ_idx = to_index(econ, str(BASE))
covid = [Shock("COVID-19", "2020")]
sl = lambda d: {y: d[y] for y in d if int(y) >= BASE}
mp = resilience_metrics(sl(prem), covid)
me = resilience_metrics(sl(econ), covid)
cmp = compare_premium_economy(sl(prem), sl(econ), covid)
tpl = forward_shock_template(resilience_metrics(prem, covid))

# Long premium series 2008-2025: IATA Premium Traffic Monitor (international pax,
# 2008 peak=100) spliced onto Sabre (global O&D cabin, 2019=100) at 2013. IATA
# figures are extracted from the IATA reports in the knowledge library (GFC trough
# and reported annual growth); sources noted per point in the sendable workbook.
def _long_premium():
    # IATA annual index, 2008 peak = 100, chained from reported growth/levels
    iata_growth = {  # (premium, economy) year-on-year; 2009 is peak-to-trough
        2009: (-0.23, -0.09), 2010: (0.091, 0.059), 2011: (0.055, 0.051),
        2012: (0.048, 0.059), 2013: (0.020, 0.035)}
    ip, ie = {2008: 100.0}, {2008: 100.0}
    for y in range(2009, 2014):
        gp, ge = iata_growth[y]
        ip[y] = ip[y - 1] * (1 + gp); ie[y] = ie[y - 1] * (1 + ge)
    # Sabre annual index 2019=100, 2013-2025 (all years; 2013/2015 point-of-origin)
    rows = con.execute("""
      SELECT year,
        SUM(CASE WHEN cabin_class IN ('FIRST','BUSINESS') THEN passengers ELSE 0 END) premium,
        SUM(CASE WHEN cabin_class IN ('DISCOUNT COACH','PREMIUM COACH') THEN passengers ELSE 0 END) economy
      FROM sabre WHERE year BETWEEN 2013 AND 2025 GROUP BY year ORDER BY year""").fetchall()
    sp = {y: p for y, p, e in rows}; se = {y: e for y, p, e in rows}
    spx = to_index({str(y): sp[y] for y in sp}, "2019")
    sex = to_index({str(y): se[y] for y in se}, "2019")
    sp_idx = {int(k): v for k, v in spx.items()}; se_idx = {int(k): v for k, v in sex.items()}
    # scale IATA to meet Sabre at 2013
    kp = sp_idx[2013] / ip[2013]; ke = se_idx[2013] / ie[2013]
    prem, econ, src = {}, {}, {}
    for y in range(2008, 2026):
        if y <= 2013:
            prem[str(y)] = round(ip[y] * kp, 1); econ[str(y)] = round(ie[y] * ke, 1)
            src[str(y)] = "IATA"
        if y >= 2013:
            prem[str(y)] = round(sp_idx[y], 1); econ[str(y)] = round(se_idx[y], 1)
            src[str(y)] = "Sabre" if y > 2013 else "join"
    return {"years": list(range(2008, 2026)), "premium": prem, "economy": econ, "segment": src,
            "base_year": 2019, "join_year": 2013,
            "source": "IATA Premium Traffic Monitor (to 2013); Sabre MI, AviaSolutions analysis (from 2013)"}

# point-of-origin years reported separately (different basis, not mixed in)
poo = con.execute("""
  SELECT year,
    SUM(CASE WHEN cabin_class IN ('FIRST','BUSINESS') THEN passengers ELSE 0 END) premium,
    SUM(CASE WHEN cabin_class IN ('DISCOUNT COACH','PREMIUM COACH') THEN passengers ELSE 0 END) economy
  FROM sabre WHERE directionality='POO' AND year IN (2013,2015) GROUP BY year ORDER BY year""").fetchall()
poo_note = {str(y): {"premium": round(p), "economy": round(e)} for y, p, e in poo}

data = {
    "meta": {
        "source": "Sabre MI, AviaSolutions analysis",
        "basis": "Non-directional O&D, global, full years",
        "window": f"{Y0}-{Y1}",
        "base_year": BASE,
        "premium_def": "First + Business",
        "economy_def": "Discount + Premium Coach",
        "poo_years_excluded": [2013, 2015],
    },
    "years": list(range(Y0, Y1 + 1)),
    "cabin": {
        "prem_raw": {k: round(v) for k, v in prem.items()},
        "econ_raw": {k: round(v) for k, v in econ.items()},
        "prem_index": {k: round(v, 1) for k, v in prem_idx.items()},
        "econ_index": {k: round(v, 1) for k, v in econ_idx.items()},
        "prem_share": {k: round(v, 4) for k, v in share.items()},
    },
    "resilience": {"premium": mp, "economy": me, "compare": cmp, "forward_template": tpl},
    "regions": _regions(),
    "fares": _fares(),
    "fares_meta": {"base_year": Y0, "note": "Fare index rebased to base year = 100. Sabre MI, Avia Solutions analysis; absolute fares withheld under the Sabre licence."},
    "long_premium": _long_premium(),
    "world_traffic": {
        "years": sorted(WORLD_PAX_M),
        "pax_m": {str(y): WORLD_PAX_M[y] for y in sorted(WORLD_PAX_M)},
        "coverage_break": WORLD_COVERAGE_BREAK,
        "rpk_bn": {str(y): WORLD_RPK_BN[y] for y in sorted(WORLD_RPK_BN)},
        "plf": {str(y): WORLD_PLF[y] for y in sorted(WORLD_PLF)},
        "rpk_plf_source": "ICAO to 2020 (RPK and load factor); IATA 2021-2025 (RPK growth and load factor); Avia Solutions analysis",
        "source": "ICAO Member States Airlines to 2023 (2023: The World of Air Transport in 2023); IATA 2024-2025; Avia Solutions analysis",
    },
    "amex_fares": {"yoy": AMEX_FARE_YOY, "years": ["2000","2001","2002"],
        "source": "AMEX European Corporate Travel Index, Western Europe to all destinations, Avia Solutions analysis"},
    "benchmarks": {
        "vintage": 2009, "currency": "EUR",
        "airports": [{"name": n, "pax_m": p, "aero": a, "non_aero": na, "opex": o,
                      "ebitda": e, "ebitda_pct": pc, "group": g}
                     for (n, p, a, na, o, e, pc, g) in BENCHMARKS],
        "source": "Avia European Airport Financial Database, 2009; per-passenger, EUR; Avia Solutions analysis",
    },
    "poo_reference": poo_note,
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=True, indent=0)
print("wrote", OUT)
print("premium fall %.1f%% recover %s ; economy fall %.1f%% recover %s" % (
    mp[0]["drop_frac"] * 100, mp[0]["recovery_period"], me[0]["drop_frac"] * 100, me[0]["recovery_period"]))
print("premium share 2016 %.1f%% -> 2019 %.1f%% -> 2025 %.1f%%" % (
    share["2016"] * 100, share["2019"] * 100, share["2025"] * 100))
print("regions:", ", ".join(list(data["regions"])[:6]), "...")

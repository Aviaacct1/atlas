"""build_capacity_webapp_data - webapp/data/capacity.json for the tool's capacity view.
PUBLISHES: screen states (schedule-derived, all airports) + the service-quality context
(public-data test, CHANGELOG 92) + register COVERAGE status only.
WITHHOLDS: register-derived binding ranges/capacities - the capacity-layer extract's
checks must pass and the overrun disposition land before those reach users (C2 verdict).
Author: Avia Solutions.  Run after run_capacity_layer.py; restart the service to serve.
"""
import json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from avia_forecast.io_safe import dump_atomic

ext = json.load(open(os.path.join(REPO, "data", "capacity_layer_extract.json")))
meta = json.load(open(os.path.join(REPO, "data", "global_airport_meta_2025.json")))
sq = json.load(open(os.path.join(REPO, "data", "service_quality_screen_test.json")))
names = {}
try:
    dd = json.load(open(os.path.join(REPO, "webapp", "data", "dashboard.json")))
    ap = dd.get("airports")
    if isinstance(ap, dict):
        for i, r in ap.items():
            names[i] = r.get("name") or r.get("n") or ""
    elif isinstance(ap, list):
        for r in ap:
            if isinstance(r, dict) and r.get("iata"):
                names[r["iata"]] = r.get("name", "")
except Exception:
    pass

STATE_TEXT = {
    "at_ceiling": "Full - the busiest hour has stopped growing. There is no room left to add flights when people most want to fly",
    "tightening": "Filling up - the airport is still growing, but new flights are being pushed into quieter times of day because the busy hours are nearly full",
    "headroom": "Room to grow - the busy hours can still take more flights",
    "too_short": "Not enough history to judge",
    "not_assessed": "Too small to judge from timetables alone",
}

# activity (last scheduled year) from the OAG store snapshot; names for majors the
# forecast set does not carry (hand map, city-level, checked against the IATA code)
try:
    ACT = json.load(open(os.path.join(REPO, "data", "oag_airport_names.json")))
except FileNotFoundError:
    ACT = {}
HAND_NAMES = {
    "CGO": "Zhengzhou", "CSX": "Changsha", "URC": "Urumqi", "KWE": "Guiyang",
    "DLC": "Dalian", "HRB": "Harbin", "TNA": "Jinan", "LHW": "Lanzhou",
    "NNG": "Nanning", "FOC": "Fuzhou", "TYN": "Taiyuan", "CGQ": "Changchun",
    "HFE": "Hefei", "WNZ": "Wenzhou", "KBP": "Kyiv", "NGB": "Ningbo",
    "YNT": "Yantai", "INC": "Yinchuan", "DAC": "Dhaka", "KWL": "Guilin",
    "JJN": "Quanzhou", "XNN": "Xining", "WUX": "Wuxi", "SWA": "Jieyang (Shantou)",
    "SPR": "San Pedro", "TSE": "Astana", "TZA": "Belize City", "LXA": "Lhasa",
    "VVI": "Santa Cruz", "BTH": "Batam", "REP": "Siem Reap", "BET": "Bethel",
    "KRR": "Krasnodar", "BGW": "Baghdad", "POM": "Port Moresby", "KRT": "Khartoum",
    "SIP": "Simferopol", "LPB": "La Paz", "CZX": "Changzhou", "JNU": "Juneau",
    "VTE": "Vientiane", "HUZ": "Huizhou", "XUZ": "Xuzhou", "YIW": "Yiwu",
    "YTY": "Yangzhou", "WEH": "Weihai", "DSN": "Ordos", "MAF": "Midland",
    "NSN": "Nelson", "ROV": "Rostov-on-Don", "KIV": "Chisinau",
}
rows = {}
for src_key in ("airports", "screen_unregistered"):
    for iata, v in ext.get(src_key, {}).items():
        sc = (v.get("screen") or v) if src_key == "airports" else v
        st = (sc or {}).get("state")
        if not st:
            continue
        m = meta.get(iata) or {}
        rows[iata] = {
            "state": st,
            "state_text": STATE_TEXT.get(st, st),
            "note": (sc or {}).get("note", ""),
            "name": names.get(iata) or HAND_NAMES.get(iata, ""),
            "country": m.get("country", ""),
            "region": m.get("region", ""),
            "size_m": (lambda u: float(u) if u else None)(((v.get("unconstrained_m") or {}) if src_key == "airports" else {}).get("2025")),
            "listed": bool((names.get(iata) or HAND_NAMES.get(iata)) and
                           ACT.get(iata, {}).get("last_year", 2026) >= 2023),
            "register": ("operates above its rated level (official figures held)"
                         if src_key == "airports" and v.get("knowledge_state") == "constraint_overrun_observed"
                         else "official figures held (being checked)" if src_key == "airports" and
                         v.get("knowledge_state") in ("constrained_evidenced", "constraint_known_not_quantified")
                         else "none held yet"),
        }

from collections import Counter
counts = Counter(v["state"] for v in rows.values())
out = {
    "meta": {
        "generated_from": "capacity screen (schedule-derived) + public service-quality test",
        "source": "Source: OAG schedules, AviaSolutions analysis",
        "presentation_rule": ("When we say an airport will run out of room, we give a range of "
                              "years, never a single year - forecasts are not that precise"),
        "counts": dict(counts),
        "n_airports": len(rows),
    },
    "service_quality_context": {
        "text": (f"We compared these results with public passenger ratings for {sq['n']} airports. "
                 "Airports that are filling up get worse ratings than similar-sized airports with "
                 "room to grow. Airports that filled up long ago score highest, because they have "
                 "learned to manage it. The lesson: the time to plan new capacity is while an "
                 "airport is filling up, not after it is full."),
        "basis": "public data direction test; see CHANGELOG 92 and data/service_quality_screen_test.json",
    },
    "airports": rows,
}
# --- global story, methodology and service exhibit (added CHANGELOG 94) ---
import json as _json
_sq = _json.load(open(os.path.join(REPO, "data", "service_quality_screen_test.json")))
out["global_summary"] = {
    "headline": (
        "{at} airports are already full at their busiest hours, and {ti} more are "
        "filling up. That is where the world's next capacity problems come from.".format(
            at=out["meta"]["counts"].get("at_ceiling", 0),
            ti=out["meta"]["counts"].get("tightening", 0))
    ),
    "investment_gap_status": (
        "The big number this page will eventually show is the INVESTMENT GAP: how much "
        "airport capacity the world must build for our traffic forecast to come true. "
        "We are not showing it yet, for two honest reasons: we only hold checked "
        "capacity figures for a small set of airports so far (France first), and we are "
        "still deciding how to count airports that squeeze in more passengers than "
        "their buildings were designed for. It appears here when both are done."
    ),
}
out["methodology"] = [
    ("What demand wants", "First we forecast how many people will want to fly at every "
     "airport, assuming nothing gets in the way. Capacity never changes that forecast; "
     "we compare the two, and the difference is what has to be built."),
    ("Reading the timetables", "Airlines publish their schedules. If an airport's "
     "busiest hour has stopped growing while the rest of its day still grows, it is "
     "running out of room - the timetable shows it even when nobody announces it. This "
     "works for every airport in the world, which is why every airport gets a state."),
    ("Checking the paperwork", "For some airports we also collect the official numbers: "
     "how many passengers the terminal was built for, how many flights the runway is "
     "allowed. Every figure keeps a note of where it came from. This covers France so "
     "far; more countries follow. Where we hold these figures we can say when an "
     "airport runs out of room - as a range of years, never one year."),
    ("Full is not a wall", "Airports can squeeze in more people than the building was "
     "designed for; the price is queues and lower ratings, up to safety limits. And "
     "capacity jumps when a new runway or terminal opens - announced projects and "
     "their opening years are added airport by airport as the register grows, so a "
     "reader who knows about a planned expansion will see it reflected."),
]
# growth by state: median annualised traffic growth from the screen panel - the third
# axis of the story (fast growth fills airports; service pays first; then growth caps)
import csv as _csv, statistics as _stats
_g = {}
for _r in _csv.DictReader(open(os.path.join(REPO, "data", "capacity_screen.csv"))):
    if _r["state"] not in ("headroom", "tightening", "at_ceiling"):
        continue
    try:
        _gr = float(_r["annual_growth"]); _y0, _y1 = int(_r["first_year"]), int(_r["last_year"])
    except ValueError:
        continue
    if _y1 > _y0:
        _ann = (1 + _gr) ** (1 / (_y1 - _y0)) - 1
        if -0.5 < _ann < 0.5:
            _g.setdefault(_r["state"], []).append(_ann)
GROWTH = {s: {"median_pct": round(_stats.median(v) * 100, 1), "n": len(v)} for s, v in _g.items()}

_bands = _sq.get("bands", {})
out["service_exhibit"] = {
    "n": _sq.get("n"),
    "overall": _sq.get("overall"),
    "bands": _bands,
    "growth_by_state": GROWTH,
    "chart_story": (
        "The fastest-growing airports are the ones filling up. While they fill, "
        "passenger ratings dip. Once full, ratings recover - but growth collapses, "
        "because there is nowhere to put it. Planning while filling up avoids both."),
    "rule_of_thumb": (lambda t, h: (
        f"Airports that are filling up score lower with passengers than similar-sized "
        f"airports with room to spare (smallest airports: {t['mean']} vs {h['mean']} stars "
        f"out of 5; {t['share_45']:.0%} get 4-5 stars, against {h['share_45']:.0%}). Airports "
        "that have been full for years score highest of all - they have learned to live "
        "with it. So the damage to service happens WHILE an airport fills up. That is "
        "the moment to plan."))(_sq["bands"]["<5m"]["tightening"], _sq["bands"]["<5m"]["headroom"]),
    "reading": (
        f"Average public rating (Skytrax stars out of 5, August 2026) by capacity state "
        f"and airport size, {_sq['n']} airports. A first test on public data, not our final "
        "measurement: the proper version uses official capacity figures as the "
        "register grows."),
}
dump_atomic(out, os.path.join(REPO, "webapp", "data", "capacity.json"), indent=1)

print(f"webapp/data/capacity.json: {len(rows)} airports, counts {dict(counts)}")

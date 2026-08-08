"""Engine data bundle for the analyst Cockpit. Real per-airport base forecast (2019-2060,
ACI history + engine forecast), entity rollups (global/region/country) and per-airport input
defaults (dom share, connecting share, gdp elasticity). The cockpit's base = engine vintage;
analyst edits apply as deltas on top. Author: Avia Solutions."""
from __future__ import annotations
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from avia_forecast.io_safe import dump_atomic
from avia_forecast.paths import DATA, OEF_DIR, ACI_DIR, ACI_DECRYPT, SABRE_DB, OAG_DB, QSI_REF, PREAGG, QSI_APP, OEF_GDP_XLSX
import json, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

E = DATA
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webapp", "data")
H0, BASE = 2019, 2025
REPO_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
def _repo_json(fn):
    fp = os.path.join(REPO_DATA, fn)
    return json.load(open(fp)) if os.path.exists(fp) else {}
UK_BG = _repo_json("uk_estimated_bG.json")                       # per-airport estimated income elasticity (pilot, bG only)
FULL_REGRESS = _repo_json("airport_regress.json")               # full diagnostics (bG,r2,t,n,points) from estimate_airport_diagnostics.py
from avia_forecast.config import get as _cfg
MAX_CX = _cfg("global_drivers.airport_elasticity_max_cx", 0.25)          # apply airport-own elasticity only below this connecting share
USE_AIR = _cfg("global_drivers.use_airport_elasticities", True)
def _clamp_bg(v):
    lo, hi = BG_BOUND
    return round(max(lo, min(hi, v)), 3)
UK_BF = {k: round(v, 3) for k, v in _repo_json("uk_estimated_bF.json").items()}   # segment fare terms
BG_BOUND = [0.6, 2.2]                                            # from assumptions_book global_drivers.bG_applied_bounds


def run():
    dash = json.load(open(os.path.join(OUT, "dashboard.json")))     # per-airport series (2015-2060) + cty + dests
    dyrs = dash["years"]
    yrs = [y for y in dyrs if y >= H0]
    idx = [dyrs.index(y) for y in yrs]
    est = {k: v["bG"] for k, v in json.load(open(os.path.join(E, "estimated_bG_by_country.json"))).items() if v.get("reliable")}
    CTY = dash["cty"]

    def slice_series(a, sc):
        s = a["scen"][sc]
        return [round(s[i], 3) for i in idx]

    airports = []
    for a in dash["airports"]:
        iso = None
        # country iso from cty table
        c = CTY.get(a["country"], {})
        iso = c.get("iso")
        b25 = a["scen"]["Baseline"][dyrs.index(BASE)]
        b60 = a["scen"]["Baseline"][-1]
        g = round((b60 / b25) ** (1 / (dyrs[-1] - BASE)) - 1, 4) if b25 > 0 else 0.03
        _ar = FULL_REGRESS.get(a["iata"])
        _cx = round(a.get("cnx") or 0.0, 3)
        if USE_AIR and _ar and _ar.get("reliable") and _cx <= MAX_CX:
            ge = _clamp_bg(_ar["bG_est"]); ge_src = "airport"          # airport's own estimate (O&D-dominant, reliable)
        elif iso in est:
            ge = est[iso]; ge_src = "country"                          # country estimate (hub, or airport not estimated)
        else:
            ge = None; ge_src = "default"                              # segment/literature default
        airports.append({
            "c": a["iata"], "n": a["name"], "cty": a["country"], "reg": a["region"],
            "base": round(b25, 3), "g": g, "cap": a.get("cap") or 0,
            "dom": (round(c.get("dom", 0.3), 3)), "cx": round(a.get("cnx") or 0.0, 3),
            "ge": round(ge, 2) if ge else None, "ge_src": ge_src,
            "dests": a.get("dests", [])[:10],
            "series": {"Baseline": slice_series(a, "Baseline"),
                       "High": slice_series(a, "High"), "Low": slice_series(a, "Low")},
            **({"regress": {**FULL_REGRESS[a["iata"]], "bG_bound": BG_BOUND, "bF": UK_BF}}
               if a["iata"] in FULL_REGRESS else
               {"regress": {"bG_est": round(UK_BG[a["iata"]], 3), "bG_bound": BG_BOUND, "bF": UK_BF}}
               if a["iata"] in UK_BG else {}),
        })

    # entity rollups (global / region / country) - sum airport series
    def rollup(pred):
        out = {sc: [0.0] * len(yrs) for sc in ("Baseline", "High", "Low")}
        for a in airports:
            if pred(a):
                for sc in out:
                    for i in range(len(yrs)):
                        out[sc][i] += a["series"][sc][i]
        return {sc: [round(v, 2) for v in out[sc]] for sc in out}

    regions = sorted({a["reg"] for a in airports})
    countries = sorted({a["cty"] for a in airports})
    entities = {"Global": rollup(lambda a: True)}
    for r in regions:
        entities["reg:" + r] = rollup(lambda a, r=r: a["reg"] == r)
    top_cty = sorted(countries, key=lambda c: -sum(a["base"] for a in airports if a["cty"] == c))[:40]
    for c in top_cty:
        entities["cty:" + c] = rollup(lambda a, c=c: a["cty"] == c)

    dump_atomic({"years": yrs, "base": BASE, "horizon": yrs[-1],
               "airports": airports, "entities": entities,
               "regions": regions, "countries": top_cty},
              os.path.join(OUT, "cockpit.json"))
    print(f"cockpit.json: {len(airports)} airports, {len(entities)} entities, years {yrs[0]}-{yrs[-1]}")


if __name__ == "__main__":
    run()

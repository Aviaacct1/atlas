"""Skytrax service curve vs peak absorption - threshold test and recorded NULL (CHANGELOG 96).

John's decision (7 Aug 2026): base the service-level rule of thumb on Skytrax while ASQ
sample size and licence cost are checked. The proper x-axis is utilisation against rated
capacity; the register holds rated capacities for two airports, so this run used the
screen's continuous measure, ABSORPTION (peak-hour growth / annual growth).

RESULT, first run: NULL. Mean stars are flat across absorption bands, overall and within
size bands (tight 3.22 vs in-step 3.11 - the "wrong" direction, within noise). A ratio of
two growth rates is too noisy per airport to carry the curve. The signal survives in the
CATEGORICAL screen states (service_quality_screen_test.json: tightening below headroom
within size bands; at_ceiling highest) because the state rule folds in size floors and
static-peak logic the raw ratio lacks. The operative interim rule is therefore STATE-based;
this file exists so the threshold claim is never built on the absorption proxy. Re-run on
utilisation of rated capacity as the register extends - that axis is not a growth-rate
ratio and should not share this failure mode. Author: Avia Solutions."""
import csv, json, os, statistics, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from avia_forecast.io_safe import dump_atomic

stars = {r["iata"]: float(r["stars"]) for r in csv.DictReader(open(os.path.join(REPO, "data", "skytrax_airport_stars_2026.csv")))}
ext = json.load(open(os.path.join(REPO, "data", "capacity_layer_extract.json")))
level = {i: float((v.get("unconstrained_m") or {}).get("2025") or 0) for i, v in ext["airports"].items()}
scr = {r["iata"]: r for r in csv.DictReader(open(os.path.join(REPO, "data", "capacity_screen.csv")))}

rows = []
for iata, st in stars.items():
    r = scr.get(iata)
    size = level.get(iata)
    if not r or not size or r["state"] in ("not_assessed", "too_short"):
        continue
    a = r["absorption"]
    if a in ("", "nan"):
        continue
    rows.append((iata, st, float(a), float(size), r["state"]))
print(f"joined: {len(rows)} airports with stars, readable absorption and size")

BANDS = [("<0 (peak shrinking)", lambda a: a < 0),
         ("0-0.35 (tight)", lambda a: 0 <= a < 0.35),
         ("0.35-0.7 (absorbing)", lambda a: 0.35 <= a < 0.7),
         ("0.7-1.1 (in step)", lambda a: 0.7 <= a < 1.1),
         (">1.1 (peak leading)", lambda a: a >= 1.1)]
SIZES = [("<5m", lambda z: z < 5), ("5-20m", lambda z: 5 <= z < 20), (">20m", lambda z: z >= 20)]

def cell(sel):
    v = [st for _, st, a, z, _ in rows if sel(a, z)]
    return {"n": len(v), "mean_stars": round(statistics.mean(v), 2) if len(v) >= 8 else None}

curve = {}
for bl, bf in BANDS:
    curve[bl] = {"all": cell(lambda a, z, bf=bf: bf(a))}
    for sl, sf in SIZES:
        curve[bl][sl] = cell(lambda a, z, bf=bf, sf=sf: bf(a) and sf(z))

tight = curve["0-0.35 (tight)"]["all"]["mean_stars"]
instep = curve["0.7-1.1 (in step)"]["all"]["mean_stars"]
sq = json.load(open(os.path.join(REPO, "data", "service_quality_screen_test.json")))
out = {"n": len(rows), "x_axis": "absorption (peak-hour growth / annual growth)",
       "bands": curve,
       "result": "NULL - no threshold shape on the absorption proxy, overall or within size bands",
       "tight_vs_instep": [tight, instep],
       "rule_of_thumb": (
           "STATE-BASED (the operative interim rule), from the corrected size run: "
           "tightening rates below headroom in every size band "
           f"(<5m: {sq['bands']['<5m']['tightening']['mean']} vs {sq['bands']['<5m']['headroom']['mean']} mean stars, "
           f"4-5 star share {sq['bands']['<5m']['tightening']['share_45']:.0%} vs {sq['bands']['<5m']['headroom']['share_45']:.0%}); "
           "settled at-ceiling airports rate highest. The service cost shows while "
           "capacity tightens, which is the window to plan."),
       "state_means": sq.get("overall"),
       "status": ("Absorption-based continuous curve: recorded null, do not publish a "
                  "threshold from it. Utilisation-of-rated-capacity curve replaces this "
                  "as the register harvest extends; ASQ sample size and licence cost "
                  "under review meanwhile."),
       "author": "Avia Solutions"}
dump_atomic(out, os.path.join(REPO, "data", "service_curve_skytrax.json"), indent=1)
for bl, _ in BANDS:
    c = curve[bl]["all"]
    print(f"{bl:26s} n={c['n']:3d} mean={c['mean_stars']}")
print("result:", out["result"])

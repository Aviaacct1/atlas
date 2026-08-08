"""service_quality_screen_test - the crude test of John's service-cost thesis (6 Aug):
do public Skytrax star ratings differ by the capacity screen's state? If airports the
screen calls at_ceiling/tightening score below headroom airports of similar size, the
"rated capacity is a service-level line" model has empirical legs - from entirely
public data, no ASQ licence involved. Author: Avia Solutions.

Inputs (all in-repo): data/skytrax_airport_stars_2026.csv (A-Z index, Aug 2026, 430
airports hand-mapped to IATA, terminal-specific entries excluded);
data/capacity_layer_extract.json (screen states); data/global_airport_meta_2025.json
(size = term_out_m). Caveats printed with the result: Skytrax stars are coarse (1-5),
partly assessment-based, and asset age confounds (new terminals score high AND have
headroom) - this is a direction-and-magnitude sketch, not the calibration.
"""
import csv, json, os, statistics, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

stars = {r["iata"]: float(r["stars"]) for r in csv.DictReader(open(os.path.join(REPO, "data", "skytrax_airport_stars_2026.csv")))}
ext = json.load(open(os.path.join(REPO, "data", "capacity_layer_extract.json")))
meta = json.load(open(os.path.join(REPO, "data", "global_airport_meta_2025.json")))

state = {}
for i, v in ext["airports"].items():
    s = (v.get("screen") or {}).get("state")
    if s: state[i] = s
for i, v in ext.get("screen_unregistered", {}).items():
    state[i] = v.get("state")

# Size = REAL annual passengers (m): the extract's base-year level. term_out_m in the
# meta file is a departing-O&D measure (LHR 20.1 vs 85.4 actual) and mislabelled the
# bands in the first run (caught 7 Aug when LHR displayed as a 20m airport).
level = {}
for i, v in ext["airports"].items():
    u = (v.get("unconstrained_m") or {}).get("2025")
    if u:
        level[i] = float(u)

rows = []
for iata, st in stars.items():
    sc = state.get(iata)
    size = level.get(iata)
    if sc and sc in ("at_ceiling", "tightening", "headroom") and size:
        rows.append((iata, st, sc, float(size)))

print(f"joined: {len(rows)} airports with Skytrax stars, screen state and size "
      f"(of {len(stars)} rated, {len(state)} screened)")

def band(sz):
    return "<5m" if sz < 5 else ("5-20m" if sz < 20 else ">20m")

def summarise(rs, label):
    if len(rs) < 5:
        print(f"  {label:<26} n={len(rs):>3}  (too few)"); return None
    vals = [r[1] for r in rs]
    hi = sum(1 for v in vals if v >= 4) / len(vals)
    print(f"  {label:<26} n={len(rs):>3}  mean {statistics.mean(vals):.2f}  median {statistics.median(vals):.0f}  "
          f"4-5 star share {hi:.0%}")
    return {"mean": round(statistics.mean(vals), 2), "n": len(rs), "share_45": round(hi, 3)}

print("\nALL SIZES:")
res = {}
for sc in ("headroom", "tightening", "at_ceiling"):
    res[sc] = summarise([r for r in rows if r[2] == sc], sc)

print("\nBY SIZE BAND (the size control):")
out = {"n": len(rows), "overall": res, "bands": {}}
for b in ("<5m", "5-20m", ">20m"):
    print(f" {b}:")
    out["bands"][b] = {}
    for sc in ("headroom", "tightening", "at_ceiling"):
        m = summarise([r for r in rows if r[2] == sc and band(r[3]) == b], f"{sc}")
        out["bands"][b][sc] = m

print("\nat_ceiling airports in the joined set:",
      sorted(i for i, s, sc, z in rows if sc == "at_ceiling"))
print("\nCaveats: coarse 1-5 scale; asset-age confound (new terminals score high AND")
print("have headroom); screen states are schedule-derived, not register-derived.")
print("Direction test only - the calibration needs ASQ-grade data or Google scores.")

sys.path.insert(0, REPO)
from avia_forecast.io_safe import dump_atomic
dump_atomic(out, os.path.join(REPO, "data", "service_quality_screen_test.json"), indent=1)
print("exhibit -> data/service_quality_screen_test.json")

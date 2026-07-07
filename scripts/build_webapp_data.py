"""Assemble the web-app data bundle from the engine: world + regional + per-airport terminal
forecasts across scenarios, plus the hub M profiles. Writes webapp/data/*.json. Author: Avia Solutions."""
from __future__ import annotations
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from avia_forecast.io_safe import dump_atomic
from avia_forecast.paths import DATA, OEF_DIR, ACI_DIR, ACI_DECRYPT, SABRE_DB, OAG_DB, QSI_REF, PREAGG, QSI_APP, OEF_GDP_XLSX
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from avia_forecast import global_terminal as gt

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webapp", "data")
E = DATA
SCEN = ["Baseline", "High", "Low"]


def run():
    os.makedirs(OUT, exist_ok=True)
    M = json.load(open(os.path.join(E, "oag_final_to_next_M.json")))
    names = {}
    try:
        import csv
        for r in csv.DictReader(open(QSI_REF, encoding="utf-8-sig")):
            names[r["airport_code"].strip()] = r["city_name"].strip()
    except Exception:
        pass

    world, regions, airports = {}, {}, {}
    years = None
    for sc in SCEN:
        r = gt.run_terminal(scenario=sc)
        years = r.years
        world[sc] = {str(y): round(r.world[y], 1) for y in years}
        regions[sc] = {reg: {str(y): round(s[y], 1) for y in years} for reg, s in r.by_region.items()}
        for iata, a in r.by_airport.items():
            d = airports.setdefault(iata, {"iata": iata, "city": names.get(iata, ""),
                                           "country": a["country"], "region": a["region"],
                                           "connecting_share": a["connecting_share"],
                                           "M": M.get(iata, {}), "scen": {}})
            d["scen"][sc] = dict(zip((str(y) for y in years), a["series"]))

    y0, y1 = str(years[0]), str(years[-1])
    for d in airports.values():
        b = d["scen"]["Baseline"]
        d["t0"] = b[y0]; d["t1"] = b[y1]
        d["cagr"] = round(((b[y1] / b[y0]) ** (1 / (int(y1) - int(y0))) - 1) * 100, 2) if b[y0] > 0 else 0

    dump_atomic({"years": [int(y) for y in years], "world": world,
               "regions": regions,
               "world_cagr": {sc: round(((world[sc][y1] / world[sc][y0]) ** (1/(int(y1)-int(y0))) - 1)*100, 2) for sc in SCEN}},
              os.path.join(OUT, "world.json"))
    top = sorted(airports.values(), key=lambda d: -d["t0"])
    dump_atomic(top, os.path.join(OUT, "airports.json"))
    dump_atomic({"generated": "engine", "n_airports": len(airports), "years": [int(y) for y in years],
               "base_year": years[0], "horizon": years[-1], "scenarios": SCEN},
              os.path.join(OUT, "meta.json"))
    print(f"web data: {len(airports)} airports, scenarios {SCEN}, years {years[0]}-{years[-1]}")
    print("world terminal (Baseline):", world["Baseline"][y0], "->", world["Baseline"][y1], "m")


if __name__ == "__main__":
    run()

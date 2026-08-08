#!/usr/bin/env python3
"""
Avia Solutions - QSI forecast runner (end to end from a generated demand extract).
Takes the store-generated 20-column demand extract, feeds it into the calibrated
QSI pipeline (capture from the QSI workbooks), converges to a target load factor,
and prints the forecast. This is the demand-side automated chain in one command.

Prereqs in C:\Avia: demand_extract.csv (from sabre_generate_demand.py), the QSI
workbooks under Reference Cases\BA LHR-SJC, airport_city_country.csv.

Run: py -3.12 _os.path.join(_paths.AVIA, 'run_forecast.py')
Options: --demand <csv>  --target-lf 0.829  --home-growth 0.09
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import sys, os, csv, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def load_connecting(csv_path, growth):
    from providers import ConnectingCityData
    agg = {}
    with open(csv_path, newline='') as f:
        for row in csv.DictReader(f):
            c = row["Mod Dest City"]
            d = agg.setdefault(c, {"pax":0.0,"direct":False,
                                   "name":row.get("Mod Dest City Name",""),
                                   "ctry":row.get("Mod Dest Country","")})
            d["pax"] += float(row["Passengers"] or 0)
            if row["Direct/Indirect"] == "Direct":
                d["direct"] = True
    return [ConnectingCityData(city_code=k, city_name=v["name"], country=v["ctry"],
            base_demand=v["pax"], growth_rate=growth, qsi_score=0.0,
            direct_service=v["direct"]) for k, v in agg.items()]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demand", default=_os.path.join(_paths.AVIA, 'demand_extract.csv'))
    ap.add_argument("--target-lf", type=float, default=0.829)
    ap.add_argument("--home-growth", type=float, default=0.09)
    a = ap.parse_args()

    from route_config import RouteConfig
    from convergence import converge_to_load_factor

    home = load_connecting(a.demand, a.home_growth)
    print(f"loaded {len(home)} connecting cities from {os.path.basename(a.demand)} "
          f"(base demand {sum(c.base_demand for c in home):,.0f})")

    cfg = RouteConfig.ba_lhr_sjc()
    dp = cfg.demand_provider
    dp.get_connecting_cities = lambda direction: home if direction == "home" else []
    cfg.demand_provider = dp

    res, adj = converge_to_load_factor(cfg, a.target_lf)
    cap = cfg.annual_capacity; tot = res["grand_total"]
    print("\n" + "=" * 56)
    print(f"FORECAST  {cfg.airline_code} {cfg.home_airport_code}-{cfg.dest_airport_code}"
          f"  (demand auto-generated from Sabre store)")
    print("=" * 56)
    print(f"  converged adjustment : {adj:.4f}")
    print(f"  P2P            : {res.get('p2p_total',0):>10,.0f}")
    print(f"  home connecting: {res.get('home_total',0):>10,.0f}")
    print(f"  dest connecting: {res.get('dest_total',0):>10,.0f}")
    print(f"  GRAND TOTAL    : {tot:>10,.0f}")
    print(f"  load factor    : {tot/cap:>9.1%}   (capacity {cap:,})")

if __name__ == "__main__":
    main()

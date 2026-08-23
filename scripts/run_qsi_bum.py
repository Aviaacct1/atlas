"""Run the QSI tool's route optimiser for an airport's candidate routes and write results
INCREMENTALLY, so the cockpit shows the first routes while the rest are still computing.
Author: Avia Solutions.

This calls the EXISTING QSI tool (route_forecast.forecast) ~10 times, once per candidate route,
and after EACH one rewrites webapp/data/bum_candidates.json with the results so far (plus a
_status line). The cockpit polls that file, shows the first ~5 immediately, and adds the rest as
they land. Runs on the machine with the QSI tool and its databases (the 16GB Sabre DB), in the
background, with no time limit:

    python scripts/run_qsi_bum.py --airports SOU

Every path resolves through avia_forecast/paths.py, so there is nothing to pass. The
--qsi, --oag and --sabre arguments remain for a one-off run against another location.

Candidate routes = each airport's largest UNSERVED O&D markets (real new-route opportunities).
Each result carries the QSI tool's optimised route demand and QSI share.
"""
from __future__ import annotations
import argparse, csv, json, os, sys, time, tempfile
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from avia_forecast.io_safe import dump_atomic
from avia_forecast import paths

def _atomic_write(path, obj):
    """Write JSON atomically (delegates to io_safe.dump_atomic: same-dir temp, fsync, parse-back,
    os.replace) so a concurrent reader (the cockpit poll) never sees a half file."""
    dump_atomic(obj, path, indent=1)


OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webapp", "data", "bum_candidates.json")
DEMO = ["SOU"]


def _ref(qsi):
    apc, name = {}, {}
    for row in csv.DictReader(open(os.path.join(qsi, "reference_tables", "airport_city_country.csv"), encoding="utf-8-sig")):
        c = row["airport_code"].strip(); apc[c] = row["country_code"].strip(); name[c] = row["city_name"].strip()
    return apc, name


def candidates_for(origin, apc, name, qsi, oag_db, n):
    import duckdb
    con = duckdb.connect(paths.PREAGG, read_only=True)
    od = {d: p for d, p in con.execute("select d, sum(pax) p from od_p2p where year=2024 and o=? group by d order by p desc", [origin]).fetchall()}
    con.close()
    served = set()
    w = duckdb.connect(oag_db, read_only=True)
    for (arr,) in w.execute("select distinct arr_airport from oag where dep_airport=? and year=2025", [origin]).fetchall():
        served.add(arr)
    oc = apc.get(origin)
    comp_by_dest = {}
    w2 = duckdb.connect(paths.PREAGG, read_only=True)
    out = []
    for d, p in od.items():
        if d == origin or d not in apc or d in served or apc.get(d) == oc:
            continue
        # competitors for the QSI/market split: same-country board points serving the destination
        comp = [origin]
        for (oo,) in w2.execute("select o from od_p2p where year=2024 and d=? group by o order by sum(pax) desc limit 12", [d]).fetchall():
            if apc.get(oo) == oc and oo != origin and len(comp) < 6:
                comp.append(oo)
        out.append({"dst": d, "name": name.get(d, d), "market_pax_000": round(p / 1000, 1), "comp": comp})
        if len(out) >= n:
            break
    w2.close()
    return out


def _pax(res):
    # The two-way ROUTE forecast is the point-to-point demand the route wins (captured_demand),
    # NOT total_demand (which adds all the connecting feed through the hub) or natural_market
    # (the whole O&D market). Prefer captured; carried_forecast (capacity-bounded) is the fallback.
    if isinstance(res, dict):
        for k in ("carried_forecast", "total_demand", "captured_demand", "captured", "route_pax", "pax", "forecast", "demand"):
            if res.get(k) is not None:
                return float(res[k])
    try:
        return float(res)
    except Exception:
        return None


def _qsi(res):
    if isinstance(res, dict):
        for k in ("qsi_share", "share", "qsi"):
            if res.get(k) is not None:
                return round(float(res[k]), 3)
    return None


STIM = 1.15   # demand stimulation vs the pre-existing service (visible parameter, carried on each row)


def _route_block_min(RF, o, dst, default=540):
    """Block time from the great-circle sector (~800 km/h cruise + 35 min taxi/climb), so a short
    candidate is not costed as a nine-hour sector. Falls back to the default if coords are missing."""
    try:
        olat, olon, _ = RF._origin_geo(o); dlat, dlon, _ = RF._origin_geo(dst)
        km = RF._gc_km(olat, olon, dlat, dlon)
        return int(max(60, km / 13.0 + 35))
    except Exception:
        return default


def _optimise_route(RF, o, dst, comp, sabre_db, oag_db, week, res0):
    """Turn a candidate into an OPTIMISED operating plan: airline + aircraft + frequency matched to
    the route's demand and range (the tool's select_aircraft), so the route CARRIES its demand rather
    than spilling against a fixed A321. Fully guarded: returns None on any failure so the caller falls
    back to the plain forecast."""
    import math
    try:
        import aircraft_select as ACS
        from aircraft_economics import AIRCRAFT
    except Exception:
        return None
    demand_tw = None
    for k in ("total_demand", "carried_forecast", "captured_demand"):
        if res0.get(k) is not None:
            demand_tw = float(res0[k]); break
    if not demand_tw or demand_tw <= 0:
        return None
    demand_ew = demand_tw / 2.0                                   # two-way market -> one direction
    try:
        olat, olon, _ = RF._origin_geo(o); dlat, dlon, _ = RF._origin_geo(dst)
        dist_nm = RF._gc_km(olat, olon, dlat, dlon) / 1.852
    except Exception:
        return None
    if not dist_nm or dist_nm <= 0:
        return None
    airline = None                                               # suggested operator = origin's largest carrier
    try:
        w = duckdb.connect(oag_db, read_only=True)
        r = w.execute("select carrier from oag where dep_airport=? and year=2025 and carrier is not null "
                      "group by carrier order by sum(cast(seats_total as double)) desc limit 1", [o]).fetchone()
        w.close(); airline = r[0] if r else None
    except Exception:
        pass
    try:
        best_ac, _ = ACS.select_aircraft(dist_nm, demand_ew, 7, airline_iata=airline)
    except Exception:
        try:
            best_ac, _ = ACS.select_aircraft(dist_nm, demand_ew, 7)
        except Exception:
            return None
    seats = (AIRCRAFT.get(best_ac, {}).get("econ_seats", 0) + AIRCRAFT.get(best_ac, {}).get("bus_seats", 0)) or 180
    plan_lf = 0.85
    freq = max(1, min(int(math.ceil(demand_ew / (seats * 52 * plan_lf))), 21))   # size to clear the spill, cap 3x daily
    try:
        res2 = RF.forecast(sabre_db, oag_db, week, o, [dst], comp,
                           aircraft=best_ac, freq=freq,
                           block_min=int(max(60, dist_nm * 1.852 / 13.0 + 35)), stimulation=STIM)
        carried = res2.get("carried_forecast") or res2.get("total_demand") or demand_tw
    except Exception:
        carried = demand_tw
    return {"carried": float(carried),
            "airline": airline or "new entrant", "aircraft": best_ac, "freq": int(freq)}


def run(airports, qsi, oag_db, sabre_db, n, week):
    sys.path.insert(0, qsi)
    import duckdb, route_forecast as RF
    apc, name = _ref(qsi)
    if week is None:
        w = duckdb.connect(oag_db, read_only=True); week = w.execute("select max(week) from oag where year=2025").fetchone()[0]; w.close()

    all_out = json.load(open(OUT)) if os.path.exists(OUT) else {}
    for o in airports:
        all_out["_status"] = {"airport": o, "done": 0, "total": 0, "running": True, "phase": "finding candidate routes"}
        _atomic_write(OUT, all_out)                       # immediate: confirms the service received the request
        cands = candidates_for(o, apc, name, qsi, oag_db, n)
        # ---- BT2 batch scoring for every candidate BEFORE the slow per-route loop ----
        # Plan basis matches the engine call below: A21X (220 seats), 7x weekly.
        _bt2 = {}
        try:
            import bt2_features as BF, duckdb as _dk, datetime as _dtm
            _con = _dk.connect(oag_db, read_only=True)
            _feats, _keys = [], []
            for c in cands:
                try:
                    pm = BF.pair_metrics(_con, week, o, c["dst"], planned_freq=7)
                    _ta = BF.endpoint_seats(_con, week, o)
                    _tb = BF.endpoint_seats(_con, week, c["dst"])
                    _sis = BF.sister_flag(_con, week, paths.PREAGG,
                                          os.path.join(qsi, "reference_tables", "airport_city_country.csv"),
                                          o, c["dst"])
                    _feats.append({"seats_ly": 220 * 7 * 52 * 2, "base_mkt": float(c["market_pax_000"]) * 1000.0,
                                   "capa": pm["capa"], "freq": 7, "legs_n": pm["legs_n"], "months": 12,
                                   "gcd": pm["gcd"], "typ": "LCC", "dom": apc.get(o) == apc.get(c["dst"]),
                                   "gauge": 220, "ncar": 1, "launch_mon": (_dtm.date.today().month % 12) + 1,
                                   "qcx": pm["qcx"], "mkt_growth": 1.0, "carrier": "",
                                   "base_seats_a": 0.0, "base_seats_b": 0.0,
                                   "airport_seats_a": _ta, "airport_seats_b": _tb, "sister_flag": _sis})
                    _keys.append((c["dst"], pm["gcd"], apc.get(o) == apc.get(c["dst"])))
                except ValueError as _e:
                    print(f"  BT2 feature unsourceable for {o}-{c['dst']}: {_e}", flush=True)
            if _feats:
                for (k, _gcd, _dom), s in zip(_keys, BF.batch_score(_feats)):
                    _bt2[k] = {"score": s, "gcd": _gcd, "dom": _dom}
            _con.close()
        except Exception as _e:
            print(f"  BT2 scoring unavailable ({type(_e).__name__}: {_e}) - rows carry engine numbers only", flush=True)
        rows = []
        all_out[o] = rows
        all_out["_status"] = {"airport": o, "done": 0, "total": len(cands), "running": True}
        _atomic_write(OUT, all_out)
        for i, c in enumerate(cands, 1):
            row = {"dst": c["dst"], "name": c["name"], "market_pax_000": c["market_pax_000"], "qsi": None, "est_pax_000": None}
            try:
                t0 = time.time()
                _bm = _route_block_min(RF, o, c["dst"])
                res = RF.forecast(sabre_db, oag_db, week, o, [c["dst"]], c["comp"],
                                  aircraft="A21X", freq=7, block_min=_bm, stimulation=STIM)
                row["stimulation"] = STIM; row["block_min"] = _bm
                _bx = _bt2.get(c["dst"])               # BT2 batch result, scored before the slow loop
                if _bx:
                    _b = _bx["score"]
                    row["bt2_est_000"] = round(_b["pax"] / 1000.0, 1)
                    row["bt2_lo_000"] = round(_b["lo"] / 1000.0, 1)
                    row["bt2_hi_000"] = round(_b["hi"] / 1000.0, 1)
                    row["tier"] = _b["tier"]
                    # The segment rule is the confidence shape (Meridian note, 16 August
                    # 2026; adopted for Atlas 23 August): the split is known entirely in
                    # advance and a client can check it, where the tier is a band only.
                    # Figures from bt2_experiments.log, 9 August 2026. The plan basis
                    # here is an LCC single-aisle, so distance and domesticity decide.
                    # The rule is "under 2,500 km AND (domestic OR LCC)"; the plan basis
                    # here is always LCC, so distance alone decides the short-haul arm.
                    if _bx["gcd"] < 2500:
                        row["segment"] = "short-haul (under 2,500 km, domestic or LCC)"
                        row["segment_confidence"] = ("blind 70.4% within +-20% on this segment "
                                                     "(n=1,432, bt2_experiments.log 9 Aug 2026)")
                    elif not _bx["dom"]:
                        row["segment"] = "long-haul international"
                        row["segment_confidence"] = ("the measured pole is international full-service at "
                                                     "blind 36.5% within +-20% (n=1,090); treat this "
                                                     "estimate as low confidence")
                    else:
                        row["segment"] = "long-haul domestic"
                        row["segment_confidence"] = ("between the measured poles; no segment-level "
                                                     "blind figure is published for this shape")
                qs = _qsi(res)
                if isinstance(res, dict):
                    for _sk, _dk in (("captured_demand","p2p_000"),("connecting_feed","conx_000"),
                                     ("carried_forecast","carried_000"),("total_demand","demand_000")):
                        _v = res.get(_sk)
                        if _v is not None: row[_dk] = round(float(_v)/1000, 1)
                opt = _optimise_route(RF, o, c["dst"], c["comp"], sabre_db, oag_db, week, res)
                if opt:
                    row["est_pax_000"] = round(opt["carried"] / 1000, 1)
                    row["plan"] = {"airline": opt["airline"], "aircraft": opt["aircraft"], "freq": opt["freq"]}
                    row["source"] = f"QSI optimised route: {opt['airline']} {opt['aircraft']} {opt['freq']}x/wk ({round(time.time()-t0,1)}s)"
                else:
                    px = _pax(res)
                    row["est_pax_000"] = round(px / 1000, 1) if px is not None else None
                    row["source"] = f"QSI route forecast, carried incl connecting ({round(time.time()-t0,1)}s)"
                row["qsi"] = qs
            except Exception as e:
                row["source"] = f"failed: {type(e).__name__}: {e}"
            rows.append(row)
            all_out["_status"] = {"airport": o, "done": i, "total": len(cands), "running": i < len(cands)}
            _atomic_write(OUT, all_out)      # rewrite after EACH route so the cockpit sees it
            print(f"  {o}-{c['dst']}: {row.get('est_pax_000')}k  qsi {row.get('qsi')}  [{i}/{len(cands)}]")
    all_out["_status"]["running"] = False
    _atomic_write(OUT, all_out)
    print("done ->", OUT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--airports", default=",".join(DEMO))
    ap.add_argument("--n", type=int, default=10)
    # Defaults resolve through avia_forecast/paths.py. They were three Windows literals
    # until 8 August 2026, so setting AVIA_QSI_APP repointed the service and not this
    # runner, and the two ran against different trees without saying so.
    ap.add_argument("--qsi", default=paths.QSI_APP)
    ap.add_argument("--oag", default=(paths.serve_copy() or paths.OAG_DB))
    ap.add_argument("--sabre", default=paths.SABRE_DB)
    ap.add_argument("--week", default=None)
    a = ap.parse_args()
    run([x.strip().upper() for x in a.airports.split(",") if x.strip()], a.qsi, a.oag, a.sabre, a.n, a.week)


if __name__ == "__main__":
    main()

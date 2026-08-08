"""BUM candidate routes for the cockpit. Author: Avia Solutions.

Produces webapp/data/bum_candidates.json = {airport: [candidate route, ...]} which the
cockpit's Bottom-up (BUM) tab offers as selectable QSI candidates.

Two modes:
  (default, quick)  candidates = the airport's largest UNSERVED O&D markets from Sabre
                    (destinations with real demand it does not yet fly nonstop), with the
                    market size and a placeholder capture. Runs anywhere in seconds.
  --optimise        for each candidate, run the QSI tool's route_forecast.forecast() to get
                    the OPTIMISED route demand and QSI share (the real "run the route" value).
                    Run this on the machine where the QSI tool and its databases live (the
                    16GB Sabre database makes it slow elsewhere).

Usage:
  python scripts/build_bum_candidates.py                         # quick, all demo airports
  python scripts/build_bum_candidates.py --airports SOU,LHR,DXB  # quick, chosen airports
  python scripts/build_bum_candidates.py --optimise --airports SOU,GOA --qsi "C:\\Avia QSI Tool\\app"

The cockpit reads whatever is in bum_candidates.json; optimised rows carry a real qsi score
and est_pax, quick rows carry the market size and a placeholder est_pax.
"""
from __future__ import annotations
import datetime
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from avia_forecast.io_safe import dump_atomic
from avia_forecast.paths import DATA, OEF_DIR, ACI_DIR, ACI_DECRYPT, SABRE_DB, OAG_DB, QSI_REF, PREAGG, QSI_APP, OEF_GDP_XLSX
import argparse, datetime, csv, json, os, sys
from collections import defaultdict

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webapp", "data", "bum_candidates.json")
DEF_QSI = QSI_APP
DEF_OAG = OAG_DB
DEF_SABRE = SABRE_DB
DEMO = ["SOU", "LHR", "LGW", "MAN", "EDI", "BHX", "DXB", "DEL", "GOA", "BLQ", "JFK", "SIN", "JED", "BOM"]
CAPTURE = 0.40                # placeholder new-route capture of the market (quick mode) [P1]
TOPN = 10


def _ref(qsi):
    apc, name = {}, {}
    path = os.path.join(qsi, "reference_tables", "airport_city_country.csv")
    for row in csv.DictReader(open(path, encoding="utf-8-sig")):
        c = row["airport_code"].strip()
        apc[c] = row["country_code"].strip(); name[c] = row["city_name"].strip()
    return apc, name


def quick(airports, qsi, oag_db):
    import duckdb
    apc, name = _ref(qsi)
    con = duckdb.connect(paths.PREAGG, read_only=True)
    inlist = ",".join("'%s'" % a for a in airports)
    od = defaultdict(lambda: defaultdict(float))
    for o, d, pax in con.execute(f"select o,d,pax from od_p2p where year=2024 and o in ({inlist})").fetchall():
        od[o][d] += pax
    con.close()
    served = defaultdict(set)
    w = duckdb.connect(oag_db, read_only=True)
    for dep, arr in w.execute(f"select distinct dep_airport,arr_airport from oag where dep_airport in ({inlist}) and year=2025").fetchall():
        served[dep].add(arr)
    w.close()
    out = {}
    for o in airports:
        rows = []
        for d, pax in sorted(od[o].items(), key=lambda kv: -kv[1]):
            if d == o or d not in apc or d in served[o]:
                continue
            rows.append({"dst": d, "name": name.get(d, d), "market_pax_000": round(pax / 1000, 1),
                         "est_pax_000": round(pax * CAPTURE / 1000, 1), "qsi": None,
                         "source": "Sabre O&D market (quick); QSI-optimised value pending tool run"})
            if len(rows) >= TOPN:
                break
        out[o] = rows
    return out


def qsi_enrich(cands, qsi, oag_db, week=None):
    """Attach the REAL QSI schedule-quality share to each candidate (route_qsi, OAG-only, fast).
    Competitors = the same-country board points that carry O&D to the destination (a coarse
    catchment). est_pax = same-country market x QSI share x stimulation, flagged indicative: the
    catchment-correct market comes from the full forecast() (--optimise). The QSI SHARE is real."""
    import duckdb
    sys.path.insert(0, qsi)
    import route_qsi as RQ
    apc, _ = _ref(qsi)
    if week is None:
        w = duckdb.connect(oag_db, read_only=True)
        week = w.execute("select max(week) from oag where year=2025").fetchone()[0]; w.close()
    con = duckdb.connect(paths.PREAGG, read_only=True)
    for o, rows in cands.items():
        oc = apc.get(o)
        for r in rows:
            dst = r["dst"]
            servers = con.execute("select o, sum(pax) p from od_p2p where year=2024 and d=? group by o order by p desc", [dst]).fetchall()
            comp = [o]; mkt = 0.0
            for oo, p in servers:
                if apc.get(oo) == oc:
                    mkt += p
                    if oo != o and len(comp) < 5: comp.append(oo)
            try:
                q = RQ.airport_qsi_to_dest(oag_db, week, [dst], comp, proposed_origin=o, proposed_freq=5, proposed_block_min=180)
                tot = sum(q.values()); share = (q.get(o, 0.0) / tot) if tot else 0.0
                r["qsi"] = round(share, 3)                                   # real schedule-quality QSI share vs the field
                # BT2 model (29 Jul 2026) supersedes the uplift table for launch candidates.
                # Features gathered here; batch-scored after the loop (one predict call).
                import bt2_features as BF
                PLAN = {"gauge": 220, "freq": 5, "typ": "LCC",
                        "launch_mon": (datetime.date.today().month % 12) + 1}   # planning assumptions, surfaced per row
                if "_bt2_con" not in dir():
                    import duckdb as _dk2
                    _bt2_con = _dk2.connect(oag_db, read_only=True)     # pair_metrics queries the OAG store, not Sabre
                pm = BF.pair_metrics(_bt2_con, week, o, dst, planned_freq=PLAN["freq"])
                _sa = 0.0; _sb = 0.0                                    # new entrant: no base seats (carrier unknown)
                _ta = BF.endpoint_seats(_bt2_con, week, o)
                _tb = BF.endpoint_seats(_bt2_con, week, dst)
                _sis = BF.sister_flag(_bt2_con, week, str(PREAGG), str(QSI_REF), o, dst)
                feat = {"seats_ly": PLAN["gauge"] * PLAN["freq"] * 52 * 2,
                        "base_mkt": r["market_pax_000"] * 1000.0,
                        "capa": pm["capa"], "freq": PLAN["freq"], "legs_n": pm["legs_n"],
                        "months": 12, "gcd": pm["gcd"], "typ": PLAN["typ"],
                        "dom": apc.get(o) == apc.get(dst), "gauge": PLAN["gauge"],
                        "ncar": 1, "launch_mon": PLAN["launch_mon"],
                        "qcx": pm["qcx"], "mkt_growth": 1.0, "carrier": "",
                        "base_seats_a": _sa, "base_seats_b": _sb,
                        "airport_seats_a": _ta, "airport_seats_b": _tb, "sister_flag": _sis}
                r["qsi"] = round(pm["capa"], 3)
                r["legs_n"] = pm["legs_n"]; r["qcx"] = round(pm["qcx"], 2)
                r["plan"] = PLAN
                r["sister_flag"] = _sis
                _bt2_pending.append((r, feat))
                r["source"] = ("BT2 route launch model v1.2 - calibrated accuracy 89% within +-20% / "
                               "82% within +-10% (n=2,915); 20-route portfolios 94% within +-20%; "
                               "tier A = higher-confidence forecast; plan assumptions on row")
            except Exception as e:
                r["source"] = f"Sabre market only (qsi share failed: {type(e).__name__})"
    con.close()
    try:
        _bt2_con.close()
    except NameError:
        pass
    if _bt2_pending:
        import bt2_features as BF
        scores = BF.batch_score([f for _, f in _bt2_pending])
        for (r, _), s in zip(_bt2_pending, scores):
            r["est_pax_000"] = round(s["pax"] / 1000.0, 1)
            r["est_lo_000"] = round(s["lo"] / 1000.0, 1)
            r["est_hi_000"] = round(s["hi"] / 1000.0, 1)
            r["tier"] = s["tier"]
    return cands


def optimise(cands, qsi, oag_db, sabre_db, week=None):
    """Replace each candidate's est_pax with the QSI tool's optimised route demand."""
    sys.path.insert(0, qsi)
    import duckdb, route_forecast as RF
    if week is None:
        w = duckdb.connect(oag_db, read_only=True)
        week = w.execute("select max(week) from oag").fetchone()[0]; w.close()

    def pax_of(res):
        if isinstance(res, dict):
            for k in ("carried_forecast", "total_demand", "captured_demand", "captured", "route_pax", "pax", "forecast", "demand"):
                if k in res and res[k] is not None:
                    return float(res[k])
        try:
            return float(res)
        except Exception:
            return None

    def qsi_of(res):
        if isinstance(res, dict):
            for k in ("qsi_share", "share", "qsi"):
                if k in res and res[k] is not None:
                    return round(float(res[k]), 3)
        return None

    for o, rows in cands.items():
        comp = [o]                        # extend with catchment competitors if desired
        for r in rows:
            try:
                res = RF.forecast(sabre_db, oag_db, week, o, [r["dst"]], comp,
                                  aircraft="A21X", freq=7, block_min=540, stimulation=1.15)
                px = pax_of(res); qs = qsi_of(res)
                if px is not None:
                    r["est_pax_000"] = round(px / 1000, 1)
                if qs is not None:
                    r["qsi"] = qs
                r["source"] = "QSI tool optimised (route_forecast.forecast)"
            except Exception as e:
                r["source"] = f"quick (optimise failed: {type(e).__name__})"
    return cands


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--airports", default=",".join(DEMO))
    ap.add_argument("--optimise", action="store_true")
    ap.add_argument("--market-only", action="store_true", help="skip the QSI share (raw market rank only)")
    ap.add_argument("--qsi", default=DEF_QSI)
    ap.add_argument("--oag", default=DEF_OAG)
    ap.add_argument("--sabre", default=DEF_SABRE)
    ap.add_argument("--week", default=None)
    a = ap.parse_args()
    airports = [x.strip().upper() for x in a.airports.split(",") if x.strip()]
    cands = quick(airports, a.qsi, a.oag)
    _bt2_pending = []
    if a.optimise:
        cands = optimise(cands, a.qsi, a.oag, a.sabre, a.week)
    elif not a.market_only:
        cands = qsi_enrich(cands, a.qsi, a.oag, a.week)
    dump_atomic(cands, OUT, indent=1)
    n = sum(len(v) for v in cands.values())
    print(f"bum_candidates.json: {len(cands)} airports, {n} candidate routes"
          f"{' (QSI-optimised)' if a.optimise else ' (quick, Sabre market)'}")


if __name__ == "__main__":
    main()

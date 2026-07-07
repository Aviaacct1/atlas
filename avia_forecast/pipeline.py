"""Two-pass build orchestration (Fable Q1: no fixed point in v1), generalised to a
UK airport set with real catchments. Pass 1 is the capacity-free unconstrained
world, computed exactly; pass 2 is the constrained world (spill, order-free
catchment redistribution to theta*K, both-ends composition, constrained
connecting, leg-based RPK). Every identity T-A..T-F runs; a failure raises.
Author: Avia Solutions.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import pandas as pd

from . import fixtures as fx
from .demand import core as demand
from .overlays import connecting as cx
from .capacity import spill as sp
from .aggregate import rpk as agg
from .aggregate import reconcile as rec
from .config import get


@dataclass
class Results:
    tidy: pd.DataFrame
    summary: dict
    exceptions: list = field(default_factory=list)          # hard identity/tolerance flags
    escalations: list = field(default_factory=list)         # soft diagnostics (e.g. T-E re-grow > 2%)


def _series(d, years):
    return [d[y] for y in years]


def run(vintage: str = "pilot", scenario: str = "Baseline", pilot=None, use_propensity: bool = False) -> Results:
    P = pilot or fx.make_pilot()
    years, base = P.years, P.base
    Gs = _series(fx.gdp_index(scenario), years)
    F = fx.fare_index()
    hub = P.hub_iata()
    Ms = {a.iata: (fx.hub_M() if a.hub else fx.feeder_M(a.iata)) for a in P.airports}
    conx_base = fx.conx_base_hub(P)

    # ---------- Pass 1: unconstrained ----------
    OD = {}
    if use_propensity:
        cheadroom = fx.catchment_headroom_series(P, scenario, years)   # per-catchment saturation
        term_log = demand.np.log(1.0 + get("propensity.terminal_tpc_growth"))
        for a in P.airports:   # per-cell: airport bG + GDP driver preserved; damped by the airport's CATCHMENT headroom
            hlist = _series(cheadroom[a.catchment], years)
            OD[a.iata] = {r: demand.od_recursion_damped(a.base_od[r], Gs, _series(F[fx.SEGMENT[r]], years),
                                                        a.bG, P.bF[fx.SEGMENT[r]], hlist, term_log) for r in P.regions}
    else:
        for a in P.airports:
            OD[a.iata] = {r: demand.od_recursion(a.base_od[r], Gs, _series(F[fx.SEGMENT[r]], years),
                                                 a.bG, P.bF[fx.SEGMENT[r]]) for r in P.regions}

    def od(iata, r, y):
        return OD[iata][r][years.index(y)]

    flow = {r: {y: sum(od(a.iata, r, y) for a in P.airports) for y in years} for r in P.regions}

    feeder_od = lambda r, y: sum(od(a.iata, r, y) for a in P.feeders())
    CONX = {hub: {r: {y: cx.connecting_growth(conx_base[r], feeder_od(r, y) / feeder_od(r, base))
                      for y in years} for r in conx_base}}

    exceptions = []
    escalations = []
    TERM_u = {}
    for a in P.airports:
        TERM_u[a.iata] = {}
        cx_a = CONX.get(a.iata, {})
        for y in years:
            od_by_region = {r: od(a.iata, r, y) for r in P.regions}
            nd = cx.final_to_next(od_by_region, Ms[a.iata])
            if y == base:
                rec.check_TA(sum(od_by_region.values()), sum(nd.values()))       # T-A
            conx_total = sum(cx_a[r][y] for r in cx_a)
            term = cx.terminal_unconstrained(od_by_region, conx_total)
            rec.check_TB(term, sum(od_by_region.values()), conx_total)           # T-B
            TERM_u[a.iata][y] = term

    implied = sum(cx.implied_connections({r: a.base_od[r] for r in P.regions}, Ms[a.iata])
                  for a in P.airports)
    tf = rec.check_TF(implied, sum(conx_base.values()))                          # T-F (base year)
    if not tf.ok:
        exceptions.append(f"T-F base-year off-tolerance (scale {tf.conx_scale:.3f})")

    # ---------- Pass 2: constrained ----------
    rows = []
    cap_req = {a.iata: {} for a in P.airports}
    for y in years:
        solves = {a.iata: sp.airport_solve(TERM_u[a.iata][y], a.K) for a in P.airports}

        # hub spill allocation (connecting first at 1.5x); feeders spill O&D only
        od_ret = {}
        for a in P.airports:
            od_tot = sum(od(a.iata, r, y) for r in P.regions)
            if a.iata == hub:
                conx_tot = sum(CONX[hub][r][y] for r in CONX[hub])
                od_red, conx_red = sp.allocate_shortfall(od_tot, conx_tot, solves[a.iata].spill)
                od_ret[a.iata] = 1.0 - (od_red / od_tot if od_tot else 0.0)
                conx_c_hub = sp.constrained_connecting(conx_tot, conx_red)
                conx_ret_hub = conx_c_hub / conx_tot if conx_tot else 1.0
            else:
                od_ret[a.iata] = solves[a.iata].retention

        # per-catchment order-free redistribution to theta*K
        received = {}
        for group in P.catchments.values():
            redis = sp.catchment_redistribute([solves[i] for i in group])
            received.update(dict(zip(group, redis.redistributed)))
            totU = sum(solves[i].U for i in group)
            totC = sum(solves[i].C for i in group)
            assert abs((totC + redis.redistributed_total + redis.suppressed_total) - totU) < 1e-6

        # both-ends per outbound flow (destinations unmodelled: rho_d = 1)
        flow_u_y, flow_c_y = {}, {}
        for r in P.regions:
            fu = flow[r][y]
            fc = sum(od(a.iata, r, y) * od_ret[a.iata] for a in P.airports)
            be = sp.both_ends(fu, (fc / fu if fu else 1.0), 1.0)
            rec.check_TD(fu, be)                                                 # T-D
            flow_u_y[r] = fu; flow_c_y[r] = be.flow_c
            rows.append({"iata": "-", "metric": "flow_u", "region": r, "year": y, "value": fu})
            rows.append({"iata": "-", "metric": "flow_c", "region": r, "year": y, "value": be.flow_c})

        # constrained connecting per market + T-E regrow diagnostic (Fable review)
        conx_c_by = {r: CONX[hub][r][y] * conx_ret_hub for r in CONX[hub]}
        for r in conx_c_by:
            rows.append({"iata": hub, "metric": "conx_c", "region": r, "year": y, "value": conx_c_by[r]})
        te = rec.regrow_diagnostic(hub, conx_c_by, {r: CONX[hub][r][y] for r in CONX[hub]},
                                   {r: flow_c_y[r] for r in conx_c_by}, {r: flow_u_y[r] for r in conx_c_by},
                                   TERM_u[hub][y])                               # T-E
        if te.escalate:
            escalations.append(f"T-E {hub} {y}: connecting re-grow gap {te.gap_share:.1%} of terminal (>2%)")

        for a in P.airports:
            sv = solves[a.iata]
            cr = sv.U - sv.C
            cap_req[a.iata][y] = cr
            assert cr >= -1e-9 and sv.C <= sv.U + 1e-9
            served = sv.C + received[a.iata]
            assert a.K <= 0 or served <= a.K + 1e-6   # K<=0 is the unconstrained sentinel (no ceiling)
            rows += [
                {"iata": a.iata, "metric": "term_u", "region": "-", "year": y, "value": sv.U},
                {"iata": a.iata, "metric": "term_c", "region": "-", "year": y, "value": sv.C},
                {"iata": a.iata, "metric": "spill_redistributed", "region": "-", "year": y, "value": received[a.iata]},
                {"iata": a.iata, "metric": "term_served", "region": "-", "year": y, "value": served},
                {"iata": a.iata, "metric": "cap_requirement", "region": "-", "year": y, "value": cr},
            ]

        # ---------- RPK (leg ledger, unconstrained) ----------
        nd_records, conx_records = [], []
        for a in P.airports:
            nd = cx.final_to_next({r: od(a.iata, r, y) for r in P.regions}, Ms[a.iata])
            for r, v in nd.items():
                nd_records.append({"airport": a.iata, "region": r, "value": v, "is_domestic": (r == "Domestic")})
        for r in CONX[hub]:
            conx_records.append({"hub": hub, "region": r, "value": CONX[hub][r][y]})
        distfn = (lambda ap, rg: P.dist[ap][rg]) if P.dist else (lambda ap, rg: fx.DIST[rg])
        led = agg.build_leg_ledger(nd_records, conx_records, distfn)
        od_intl = sum(od(a.iata, r, y) for a in P.airports for r in P.regions if r != "Domestic")
        od_dom = sum(od(a.iata, "Domestic", y) for a in P.airports)
        conx_all = sum(CONX[hub][r][y] for r in CONX[hub])
        rec.check_TC(led["total_leg_pax"], od_intl, od_dom, conx_all)            # T-C
        by_ap = {}
        for leg in led["legs"]:
            by_ap[leg.airport] = by_ap.get(leg.airport, 0.0) + leg.rpk
        for ap, v in by_ap.items():
            rows.append({"iata": ap, "metric": "rpk_u_bn", "region": "-", "year": y, "value": v / 1000.0})
        rows.append({"iata": "-", "metric": "rpk_u_bn", "region": "-", "year": y, "value": led["rpk_total"] / 1000.0})

        # constrained RPK: constrained O&D (x airport retention) and constrained connecting
        nd_c, conx_c_rec = [], []
        for a in P.airports:
            odc = {r: od(a.iata, r, y) * od_ret[a.iata] for r in P.regions}
            for rr, v in cx.final_to_next(odc, Ms[a.iata]).items():
                nd_c.append({"airport": a.iata, "region": rr, "value": v, "is_domestic": (rr == "Domestic")})
        for r in conx_c_by:
            conx_c_rec.append({"hub": hub, "region": r, "value": conx_c_by[r]})
        led_c = agg.build_leg_ledger(nd_c, conx_c_rec, distfn)
        rows.append({"iata": "-", "metric": "rpk_c_bn", "region": "-", "year": y, "value": led_c["rpk_total"] / 1000.0})

    last = years[-1]
    summary = {"vintage": vintage, "scenario": scenario, "years": years,
               "n_airports": len(P.airports),
               "term_u_last_global": round(sum(TERM_u[a.iata][last] for a in P.airports), 3),
               "cap_req_last_global": round(sum(cap_req[a.iata][last] for a in P.airports), 3),
               "identities": "T-A,T-B,T-C,T-D,T-E,T-F enforced; constrained<=unconstrained; CapReq>=0"}
    summary["t_e_escalations"] = len(escalations)
    return Results(pd.DataFrame(rows), summary, exceptions, escalations)

"""airports/instance - generic single-airport configured instance of the engine.

Reads config/airports/<name>.yaml (a self-contained, reproducible snapshot) and produces the
airport forecast: a configurable market GDP-elasticity spine + carrier-block capacity paths (with a
net-new stimulation ramp F(y)) + segment splits + ATM conversion. The market scheme, the carrier
blocks and their ramps are whatever the config carries, so a fiddly bespoke airport runs off the
core engine rather than a bespoke spreadsheet. Overrides (from a cockpit pack) replace config paths
where supplied. Author: Avia Solutions.
"""
from __future__ import annotations
from pathlib import Path
import yaml

AIRPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "airports"


def load(name: str) -> dict:
    with open(AIRPORTS_DIR / f"{name}.yaml", "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---- market spine -------------------------------------------------------------------------------

def _gdp_series(cfg: dict, key: str) -> dict:
    """GDP index for a market. Either given directly in gdp_index[key], or composed from member
    economies via that market's gdp_recipe (weighted mean of member indices), so a region-scheme
    airport can define markets without precomputing every series."""
    gi = cfg.get("gdp_index", {})
    if key in gi:
        return gi[key]
    recipe = cfg["markets"][key].get("gdp_recipe")
    if recipe:
        members = recipe["members"]                      # {economy_key: weight}
        tw = sum(members.values()) or 1.0
        anyk = next(iter(members))
        return {ys: sum((w / tw) * gi[e][ys] for e, w in members.items()) for ys in gi[anyk]}
    raise KeyError(f"market '{key}' has neither a gdp_index series nor a gdp_recipe")


def _composition_source(cfg: dict):
    """Resolve the base-composition source and its per-airport stamp. base_composition.source is
    true_od or oag_seats; where true_od is requested but GDD coverage falls below the threshold, the
    OAG direct-seats structure is the fallback (long-haul routes via hubs, so direct seats understate
    it - a documented, stamped fallback rather than a silent one)."""
    bc = cfg.get("base_composition") or {}
    src = bc.get("source", "true_od")
    thr = bc.get("gdd_coverage_threshold")
    cov = bc.get("gdd_coverage")
    if src == "true_od" and thr is not None and cov is not None and cov < thr:
        return "oag_seats", (f"true_od requested but GDD coverage {cov:.2f} below threshold {thr:.2f}; "
                             f"fell back to OAG seats structure")
    stamp = src if cov is None else f"{src} (GDD coverage {cov:.2f})"
    return src, stamp


def _market_weight(cfg: dict, key: str, source: str) -> float:
    """A market's base weight under the chosen composition source (weights[source]), falling back to
    the market's plain base_weight when it carries no per-source weights."""
    m = cfg["markets"][key]
    w = m.get("weights") or {}
    return float(w.get(source, m["base_weight"]))


def composition(cfg: dict, source=None):
    """International market composition (weights normalised over the non-domestic markets) under the
    given or resolved source. Returns ({market: share}, source)."""
    if source is None:
        source, _ = _composition_source(cfg)
    mk = cfg["markets"]; dm = _domestic_market(cfg)
    intl = [k for k in mk if k != dm]
    tw = sum(_market_weight(cfg, k, source) for k in intl) or 1.0
    return {k: _market_weight(cfg, k, source) / tw for k in intl}, source


def long_haul_weight(cfg: dict, source=None):
    """Combined weight of the long_haul_markets as a share of international, under the given/resolved
    source. Returns (weight, source)."""
    comp, src = composition(cfg, source)
    return sum(comp.get(k, 0.0) for k in cfg.get("long_haul_markets", [])), src


def _organic(cfg: dict, y: int, source=None) -> float:
    mk = cfg["markets"]
    if source is None:
        source, _ = _composition_source(cfg)
    tw = sum(_market_weight(cfg, k, source) for k in mk) or 1.0
    return sum((_market_weight(cfg, k, source) / tw) * (_gdp_series(cfg, k)[str(y)] ** mk[k]["elasticity"]) for k in mk)


def _domestic_market(cfg: dict):
    """The market whose GDP drives domestic demand: named by config (domestic_market), else a
    market flagged role: domestic. None when the airport carries no domestic segment."""
    dm = cfg.get("domestic_market")
    if dm:
        return dm
    for k, m in cfg["markets"].items():
        if m.get("role") == "domestic":
            return k
    return None


# ---- carrier-block capacity paths + net-new ramp (O-4, O-5) -------------------------------------

def _interp_clamp(path: dict, y: int) -> float:
    """Linear interpolation of a {year: value} path, clamped flat outside its endpoints."""
    sp = {int(k): float(v) for k, v in path.items()}
    xs = sorted(sp)
    if not xs:
        return 0.0
    if y <= xs[0]:
        return sp[xs[0]]
    if y >= xs[-1]:
        return sp[xs[-1]]
    for i in range(len(xs) - 1):
        if xs[i] <= y <= xs[i + 1]:
            a, b = xs[i], xs[i + 1]
            return sp[a] + (sp[b] - sp[a]) * (y - a) / (b - a)
    return 0.0


def _ramp(spec: dict, y: int) -> float:
    """Net-new stimulation ramp F(y): the share of net-new capacity that becomes net-new demand.
    {start, end, start_year, end_year, shape}. 'linear' extrapolates past the end year (matching the
    Zagreb calibration); 'smoothstep' is a bounded s-curve clamped to [start, end]. Empty spec = 1.0
    (all net-new capacity is stimulated)."""
    if not spec:
        return 1.0
    s = float(spec.get("start", 1.0)); e = float(spec.get("end", 1.0))
    y0 = spec.get("start_year"); y1 = spec.get("end_year")
    if y0 is None or y1 is None or y1 == y0:
        return e
    t = (y - y0) / (y1 - y0)
    if spec.get("shape") == "smoothstep":
        tc = min(1.0, max(0.0, t)); t = tc * tc * (3 - 2 * tc)
    return s * (1 - t) + e * t


def _block_path(cfg: dict, blk: dict) -> dict:
    """Net/seat capacity path for net_pax and gross_seats blocks: a path_ref to a top-level series,
    else an inline path."""
    if blk.get("path_ref"):
        return cfg.get(blk["path_ref"], {})
    return blk.get("path", {})


def _gross_path(cfg: dict, blk: dict) -> dict:
    """Gross capacity path for a ramped_gross block: a gross_path_ref to a top-level series, else an
    inline gross_path."""
    if blk.get("gross_path_ref"):
        return cfg.get(blk["gross_path_ref"], {})
    return blk.get("gross_path", {})


def _block_pax(cfg: dict, blk: dict, y: int, overrides=None) -> float:
    """Net pax contributed by one carrier block in year y. Entrant-gated; a cockpit override_key
    supplies a direct net path (bypassing ramp/gross); otherwise converted from the basis
    (net_pax direct | gross_seats x load_factor | ramped_gross = base_level + F(y) x (gross-base_level))
    and lifted by fleet-grid upgauge compounding from the base year. Share caps apply in _carrier_net."""
    ent = blk.get("entrant_year")
    if ent and y < int(ent):
        return 0.0
    okey = blk.get("override_key")
    if overrides and okey and overrides.get(okey):
        return _interp_clamp(overrides[okey], y)
    basis = blk.get("basis", "net_pax")
    if basis == "ramped_gross":
        base_level = float(blk.get("base_level", 0.0))
        gross = _interp_clamp(_gross_path(cfg, blk), y)
        raw = base_level + _ramp(blk.get("ramp", {}), y) * (gross - base_level)
    elif basis == "gross_seats":
        raw = _interp_clamp(_block_path(cfg, blk), y) * float(blk.get("load_factor", 0.0))
    else:  # net_pax
        raw = _interp_clamp(_block_path(cfg, blk), y)
    up = float(blk.get("upgauge_pa", 0.0))
    if up:
        raw *= (1.0 + up) ** (y - cfg["meta"]["base_year"])
    return raw


def _carrier_net(cfg: dict, y: int, organic_base: float, overrides=None) -> float:
    """Summed net pax from all carrier blocks in year y. Falls back to the legacy single lcc_net_path
    when no carrier_blocks are configured. Share caps hold each block's share of the projected total
    (organic base + blocks) at its cap (single-block exact; sequential where several bind)."""
    blocks = cfg.get("carrier_blocks")
    if not blocks:
        return _lcc_net(cfg, y, overrides)
    raw = [_block_pax(cfg, b, y, overrides) for b in blocks]
    for i, b in enumerate(blocks):
        cap = b.get("share_cap")
        if cap and 0 < cap < 1:
            others = organic_base + sum(raw) - raw[i]
            cap_val = cap * others / (1 - cap)            # r / (others + r) = cap
            if raw[i] > cap_val:
                raw[i] = cap_val
    return sum(raw)


def _lcc_net(cfg: dict, y: int, overrides=None) -> float:
    """Legacy single-block LCC net pax path (kept for configs without carrier_blocks)."""
    if overrides and overrides.get("lccSpot"):
        return _interp_clamp(overrides["lccSpot"], y)
    return float(cfg.get("lcc_net_path", {}).get(str(y), 0.0))


# ---- overlays, categories, seasonality, assumptions surface (O-8) -------------------------------

def _headwind_factor(cfg: dict) -> dict:
    """Per-year multiplicative factor from config.headwinds: mild permanent drags that compound from
    their start year, the first year taken at part_year_weight. Empty when no headwinds are set."""
    by = cfg["meta"]["base_year"]; hz = cfg["meta"]["horizon"]
    fac = {y: 1.0 for y in range(by, hz + 1)}
    for h in cfg.get("headwinds") or []:
        d = float(h.get("annual_drag", 0.0)); s = int(h.get("start_year", by)); w = float(h.get("part_year_weight", 1.0))
        for y in range(by, hz + 1):
            if y >= s:
                fac[y] *= (1.0 + d) ** (w + (y - s))
    return fac


def monthly_shares(cfg: dict, winter_uplift: float = 0.0) -> dict:
    """The 12 monthly shares from config.seasonality, with a winter-uplift control lifting the winter
    months (Nov-Mar) before renormalising to sum to one."""
    s = cfg.get("seasonality") or {}
    if not s:
        return {}
    months = {int(k): float(v) for k, v in s.items()}
    winter = {11, 12, 1, 2, 3}
    adj = {m: (v * (1.0 + winter_uplift) if m in winter else v) for m, v in months.items()}
    tot = sum(adj.values()) or 1.0
    return {m: adj[m] / tot for m in sorted(adj)}


def assumptions_table(cfg: dict) -> list:
    """Auto-listed assumptions for the deliverable's assumptions register: markets, carrier blocks,
    headwinds, categories, base-composition source and seasonality, each with a reason code."""
    rows = []
    src, stamp = _composition_source(cfg)
    rows.append({"category": "base_composition", "name": "source", "value": src, "reason": stamp})
    for k, m in cfg.get("markets", {}).items():
        rows.append({"category": "market", "name": k, "value": {"elasticity": m.get("elasticity")},
                     "reason": "GDP elasticity"})
    for b in cfg.get("carrier_blocks", []):
        rows.append({"category": "carrier_block", "name": b.get("name"),
                     "value": {"basis": b.get("basis"), "ramp": b.get("ramp"),
                               "share_cap": b.get("share_cap"), "entrant_year": b.get("entrant_year")},
                     "reason": "capacity path"})
    for h in cfg.get("headwinds", []):
        rows.append({"category": "headwind", "name": h.get("name"),
                     "value": {"annual_drag": h.get("annual_drag"), "part_year_weight": h.get("part_year_weight")},
                     "reason": h.get("reason", "HEADWIND")})
    conv = cfg.get("conversions", {})
    for cat in ("charter_share", "ga_share", "transit_share"):
        if cat in conv:
            rows.append({"category": "category", "name": cat, "value": conv[cat], "reason": "measured share"})
    if cfg.get("seasonality"):
        rows.append({"category": "seasonality", "name": "monthly", "value": "12-month profile",
                     "reason": "winter-uplift control"})
    return rows


# ---- near-term pack operations (O-7): reason-coded, no script edit -------------------------------

def _pack_factor(cfg: dict, out: dict, overrides=None) -> dict:
    """Per-year multiplicative factor from the reason-coded pack ops ACTUALS-REBASE and YTD-TRIM.
    ACTUALS-REBASE {base_actual}: anchor the base year to a published actual and regrow at the model
    ratios (one whole-series scale). YTD-TRIM {trims:{year:value}, taper_years:N}: set a near year to
    its YTD-implied full-year value and taper the adjustment linearly back to the model path by
    year+N. The two compose (rebase then trim)."""
    by = cfg["meta"]["base_year"]
    factor = {y: 1.0 for y in out}
    ov = overrides or {}
    reb = ov.get("actualsRebase")
    if reb and reb.get("base_actual") and out[by]["total"]:
        k = float(reb["base_actual"]) / out[by]["total"]
        for y in factor:
            factor[y] *= k
    trim = ov.get("ytdTrim")
    if trim and trim.get("trims"):
        n = max(1, int(trim.get("taper_years", 3)))
        for ys, v in trim["trims"].items():
            y0 = int(ys)
            model_after_rebase = out[y0]["total"] * factor[y0]
            f0 = (float(v) / model_after_rebase) if model_after_rebase else 1.0
            for y in factor:
                if y0 <= y < y0 + n:
                    factor[y] *= 1.0 + (f0 - 1.0) * max(0.0, (y0 + n - y) / n)
    return factor


# ---- forecast -----------------------------------------------------------------------------------

def forecast(cfg: dict, overrides=None) -> dict:
    by = cfg["meta"]["base_year"]; hz = cfg["meta"]["horizon"]
    base = cfg["base"]; conv = cfg.get("conversions", {})
    dom_up = (overrides or {}).get("domUplift", cfg.get("demand", {}).get("domestic_uplift_pa", 0.0))
    NONLCC0 = base["non_lcc"]; BT = base["total"]
    BDOM = base.get("domestic", 0.0); BTRA = base.get("transit", 0.0)
    dm = _domestic_market(cfg)
    has_dom = bool(dm) and BDOM > 0
    dgi = _gdp_series(cfg, dm) if has_dom else None
    dm_el = cfg["markets"][dm]["elasticity"] if has_dom else 0.0
    up = conv.get("upgauge_pa", 0.0)
    comp_source, _ = _composition_source(cfg)
    out = {}
    for y in range(by, hz + 1):
        if y == by:
            out[y] = {"total": float(BT), "international": float(base["international"]),
                      "domestic": float(BDOM), "transit": float(BTRA),
                      "charter": float(base.get("charter", 0.0)), "ga": float(base.get("ga", 0.0)),
                      "commercial_atm": float(base["commercial_atm"]),
                      "landed_tonnage": float(base.get("landed_tonnage", 0.0)),
                      "non_lcc": float(base["non_lcc"]), "lcc": float(base.get("lcc", 0.0))}
            continue
        organic = NONLCC0 * _organic(cfg, y, comp_source)
        tot = organic + _carrier_net(cfg, y, organic, overrides)
        dom = BDOM * (dgi[str(y)] ** dm_el) * ((1 + dom_up) ** (y - by)) if has_dom else 0.0
        tra = BTRA * (tot / BT)
        gauge = (1 - up) ** (y - by)
        atm = base["commercial_atm"] * (tot / BT) * gauge
        mtow = (1 + conv.get("mtow_growth_pa", 0.0)) ** (y - by)
        ga_val = conv.get("ga_share", 0.0) * tot                        # GA is its own category (as at base year)
        out[y] = {"total": tot, "international": tot - dom - tra - ga_val, "domestic": dom, "transit": tra,
                  "charter": conv.get("charter_share", 0.0) * tot, "ga": ga_val,
                  "commercial_atm": atm,
                  "landed_tonnage": float(base.get("landed_tonnage", 0.0)) * (atm / base["commercial_atm"]) * mtow,
                  "non_lcc": organic, "lcc": tot - organic}
    hw = _headwind_factor(cfg)                      # base-case drags (config)
    for y in out:
        if hw.get(y, 1.0) != 1.0:
            out[y] = {k: (v * hw[y] if isinstance(v, (int, float)) else v) for k, v in out[y].items()}
    f = _pack_factor(cfg, out, overrides)           # near-term corrections (pack)
    for y in out:
        if f[y] != 1.0:
            out[y] = {k: (v * f[y] if isinstance(v, (int, float)) else v) for k, v in out[y].items()}
    return out


def output_rows(cfg: dict, overrides=None, spots=None, cagr_windows=None) -> dict:
    """The full native deliverable row set a generic writer consumes: every headline series by year,
    the spot years, CAGRs over the standard windows, the auto-listed assumptions register and the
    monthly seasonality profile. All computed engine-side; no 007-specific logic. non_lcc + lcc and
    the segments reconcile to total by construction."""
    fc = forecast(cfg, overrides)
    by = cfg["meta"]["base_year"]; hz = cfg["meta"]["horizon"]
    years = sorted(fc)
    keys = ["total", "international", "domestic", "transit", "charter", "ga",
            "non_lcc", "lcc", "commercial_atm", "landed_tonnage"]
    series = {k: {y: fc[y].get(k, 0.0) for y in years} for k in keys}
    if spots is None:
        spots = sorted({y for y in [by, by + 1, by + 7, by + 12, by + 17, by + 20, hz] if by <= y <= hz})
    if cagr_windows is None:
        cagr_windows = [(by, by + 5), (by + 5, by + 20), (by + 20, hz)]

    def _cagr(k, a, b):
        va, vb = series[k].get(a), series[k].get(b)
        if va and vb and b > a and va > 0:
            return (vb / va) ** (1.0 / (b - a)) - 1.0
        return None
    cagr = {f"{a}-{b}": {k: _cagr(k, a, b) for k in keys} for a, b in cagr_windows if b <= hz}
    src, stamp = _composition_source(cfg)
    from ..outputs import run_id as _rid
    rid = _rid.run_id(_rid.CODE_VERSION, overrides or {},
                      {"vintage": by, "composition_source": src, "airport": cfg["meta"].get("airport")})
    return {"meta": {"airport": cfg["meta"].get("airport"), "base_year": by, "horizon": hz,
                     "composition_source": src, "composition_stamp": stamp, "run_id": rid},
            "years": years, "series": series, "spots": spots, "cagr": cagr,
            "assumptions": assumptions_table(cfg), "assumptions_register": assumptions_register(cfg, overrides),
            "seasonality": monthly_shares(cfg)}


def _norm_years(d: dict) -> dict:
    return {int(k): float(v) for k, v in d.items()}


def verify(references: dict, tol: float = 0.02,
           truth_order=("published_actuals", "working_sheets", "engine", "output_tab")) -> list:
    """Multi-series client-model cross-check. references = {series: {source: {year: value}}}. For each
    series-year with at least two sources, the highest-priority available source is truth and every
    other source is flagged when it diverges by more than tol. Runs BEFORE calibration; the flags are
    what the analyst reviews. Returns a list of
    {series, year, source, truth_source, value, truth, delta, ok}."""
    flags = []
    for series, sources in references.items():
        norm = {sname: _norm_years(d) for sname, d in sources.items()}
        years = set()
        for d in norm.values():
            years |= set(d)
        for y in sorted(years):
            avail = {sname: d[y] for sname, d in norm.items() if y in d}
            if len(avail) < 2:
                continue
            truth_src = next((t for t in truth_order if t in avail), None)
            if truth_src is None:
                continue
            tv = avail[truth_src]
            for sname, v in avail.items():
                if sname == truth_src:
                    continue
                delta = (v / tv - 1.0) if tv else 0.0
                flags.append({"series": series, "year": y, "source": sname, "truth_source": truth_src,
                              "value": v, "truth": tv, "delta": delta, "ok": abs(delta) <= tol})
    return flags


def verify_instance(cfg: dict, client_sources: dict = None, tol: float = 0.02):
    """Mandatory pre-calibration cross-check at instance creation: the engine's headline series against
    the client's output tab, working sheets and published actuals. client_sources =
    {series: {source: {year: value}}}. Returns (flags, ok). ok is False if any series diverges beyond
    tol, so instance creation can block and surface the disagreements before any calibration."""
    fc = forecast(cfg)
    refs = {}
    for series in ("total", "international", "domestic", "transit", "commercial_atm"):
        refs[series] = {"engine": {y: fc[y][series] for y in fc}}
    for series, srcs in (client_sources or {}).items():
        refs.setdefault(series, {}).update(srcs)
    flags = verify(refs, tol)
    return flags, all(f["ok"] for f in flags)


def benchmark_exhibit(independent: dict, subject: dict, base_year=None) -> dict:
    """Board exhibit (O-14): the independent engine view vs a subject third-party forecast. Returns the
    gap by year and a log decomposition of the end gap into a base-year level component and a growth
    component. independent/subject = {year: value}; subject may be spot years (linearly interpolated,
    clamped at the ends). Third-party data is passed in and never persisted to a vintage (guard G-V);
    elasticity and capacity attribution need the subject's own assumptions and are noted, not invented."""
    import math
    ind = {int(k): float(v) for k, v in independent.items()}
    sub = {int(k): float(v) for k, v in subject.items()}
    xs = sorted(sub)

    def sub_at(y):
        if y <= xs[0]:
            return sub[xs[0]]
        if y >= xs[-1]:
            return sub[xs[-1]]
        for i in range(len(xs) - 1):
            if xs[i] <= y <= xs[i + 1]:
                a, b = xs[i], xs[i + 1]
                return sub[a] + (sub[b] - sub[a]) * (y - a) / (b - a)
        return sub[xs[-1]]

    years = sorted(ind)
    rows = [{"year": y, "independent": ind[y], "subject": sub_at(y),
             "gap": ind[y] - sub_at(y),
             "subject_vs_independent": (sub_at(y) / ind[y] - 1.0) if ind[y] else 0.0} for y in years]
    by = base_year if base_year is not None else years[0]
    ty = years[-1]
    ib, it, sb, st = ind[by], ind[ty], sub_at(by), sub_at(ty)
    base_comp = math.log(ib / sb) if (ib > 0 and sb > 0) else 0.0
    growth_comp = (math.log(it / ib) - math.log(st / sb)) if all(x > 0 for x in (it, ib, st, sb)) else 0.0
    total_log = math.log(it / st) if (it > 0 and st > 0) else 0.0
    worst = min(rows, key=lambda r: r["subject_vs_independent"])
    return {"rows": rows, "base_year": by, "horizon": ty,
            "attribution": {"base_year_level": base_comp, "growth": growth_comp, "total_log_gap": total_log,
                            "note": "log decomposition into base-year level and growth; elasticity and "
                                    "capacity attribution require the subject's assumptions"},
            "headline": {"year": worst["year"], "subject_vs_independent": worst["subject_vs_independent"]}}


def assumptions_register(cfg: dict, overrides=None) -> dict:
    """The resolved assumptions register a buyer's modelling team reads: every input with its resolved
    value, source and reason code, plus every applied override with its reason. Names sources; carries
    no source data (passes the licence filter). O-13."""
    src, stamp = _composition_source(cfg)
    rows = [{"group": "base_composition", "input": "source", "resolved": src,
             "source": "MIDT true O&D / OAG direct seats", "reason": stamp}]
    for k, m in cfg.get("markets", {}).items():
        rows.append({"group": "market", "input": f"{k}.elasticity", "resolved": m.get("elasticity"),
                     "source": "OEF GDP elasticity regression", "reason": "GDP elasticity"})
        if m.get("weights"):
            rows.append({"group": "market", "input": f"{k}.weight", "resolved": _market_weight(cfg, k, src),
                         "source": "true O&D / OAG seats", "reason": f"composition {src}"})
    for b in cfg.get("carrier_blocks", []):
        rows.append({"group": "carrier_block", "input": b.get("name"),
                     "resolved": {"basis": b.get("basis"), "ramp": b.get("ramp"),
                                  "share_cap": b.get("share_cap"), "entrant_year": b.get("entrant_year")},
                     "source": "OAG capacity / carrier plans", "reason": "capacity path"})
    for h in cfg.get("headwinds", []):
        rows.append({"group": "headwind", "input": h.get("name"),
                     "resolved": {"annual_drag": h.get("annual_drag"), "part_year_weight": h.get("part_year_weight")},
                     "source": "analyst judgement", "reason": h.get("reason", "HEADWIND")})
    conv = cfg.get("conversions", {})
    for cat in ("charter_share", "ga_share", "transit_share"):
        if cat in conv:
            rows.append({"group": "category", "input": cat, "resolved": conv[cat],
                         "source": "flight summary (measured)", "reason": "measured share"})
    for cat in ("upgauge_pa", "mtow_growth_pa"):
        if cat in conv:
            rows.append({"group": "conversion", "input": cat, "resolved": conv[cat],
                         "source": "OAG fleet grid", "reason": "fleet renewal"})
    for k, v in (overrides or {}).items():
        reason = v.get("reason") if isinstance(v, dict) else None
        rows.append({"group": "override", "input": k, "resolved": v, "source": "cockpit pack",
                     "reason": reason or "OVERRIDE"})
    return {"airport": cfg["meta"].get("airport"), "vintage": cfg["meta"].get("base_year"),
            "resolved_source": src, "rows": rows}


def dashboard_airport_register(meta: dict, iata: str) -> dict:
    """Per-airport assumptions register for a dashboard airport page, from the global extract meta
    (global engine assumptions, not an instance config). O-13."""
    candidates = [
        ("coverage", "coverage_source", meta.get("coverage_source"), "ACI country totals", "grossing"),
        ("connecting", "connecting_share_method", meta.get("connecting_share_method"),
         "Sabre legs + ACI residual", "measured/blended"),
        ("gdp", "both_ends_gdp", meta.get("both_ends_gdp"), "OEF GDP", "gravity driver"),
        ("elasticity", "bG_basis", meta.get("bG_basis", "country ACI panel, book-clamped"),
         "OEF GDP regression", "income elasticity"),
    ]
    rows = [{"group": g, "input": i, "resolved": r, "source": s, "reason": rn}
            for g, i, r, s, rn in candidates if r is not None]
    return {"airport": iata, "vintage": meta.get("base_year"), "rows": rows}


def benchmark_check(cfg: dict, tol: float = 0.02):
    fc = forecast(cfg); bm = cfg.get("benchmark") or cfg.get("benchmark_007") or {}
    rows = []
    for ys, bv in bm.items():
        y = int(ys); mv = fc[y]["total"]; d = mv / bv - 1
        rows.append((y, mv, bv, d, abs(d) <= tol))
    return rows

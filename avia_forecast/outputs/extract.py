"""outputs/extract - static dashboard/cockpit extract (Data Architecture 5.1).

Turns a pipeline run into the file a front end reads: per-level series (global,
region, country, airport) for the unconstrained and constrained cases, the
capacity requirement, RPK, and region-pair flows. The front end renders this; it
never re-computes the forecast. This file is the engine-to-front-end contract.
Author: Avia Solutions.
"""
from __future__ import annotations
import json
from pathlib import Path

AIRPORT_METRICS = ["term_u", "term_c", "cap_requirement", "spill_redistributed", "rpk_u_bn"]
AGG_METRICS = ["term_u", "term_c", "cap_requirement", "rpk_u_bn"]


def _series(tidy, iata, metric, years):
    d = tidy[(tidy.iata == iata) & (tidy.metric == metric)].set_index("year")["value"]
    return [round(float(d.get(y, 0.0)), 4) for y in years]


def _sum_series(tidy, iatas, metric, years):
    cols = [_series(tidy, i, metric, years) for i in iatas]
    return [round(sum(c[k] for c in cols), 4) for k in range(len(years))]


def _flow_series(tidy, metric, region, years):
    d = tidy[(tidy.metric == metric) & (tidy.region == region)].set_index("year")["value"]
    return [round(float(d.get(y, 0.0)), 4) for y in years]


def build_extract(results, pilot) -> dict:
    t = results.tidy
    years = results.summary["years"]
    iatas = [a.iata for a in pilot.airports]

    airports = {a.iata: {"name": a.name, "hub": a.hub, "catchment": a.catchment,
                         **{m: _series(t, a.iata, m, years) for m in AIRPORT_METRICS}}
                for a in pilot.airports}

    # origin-side aggregates: all pilot airports are one country/region here
    agg = {m: _sum_series(t, iatas, m, years) for m in AGG_METRICS}
    home_region = pilot.home_region

    dest_regions = sorted({r for r in pilot.regions})
    flows = {f"{home_region}|{r}": {"flow_u": _flow_series(t, "flow_u", r, years),
                                    "flow_c": _flow_series(t, "flow_c", r, years)}
             for r in dest_regions}

    return {
        "meta": {"vintage": results.summary["vintage"], "scenario": results.summary["scenario"],
                 "base_year": pilot.base, "years": years, "regions": pilot.regions,
                 "units": {"term": "m pax", "rpk_u_bn": "bn RPK", "flow": "m pax",
                           "cap_requirement": "m pax"},
                 "note": "synthetic pilot, illustrative only",
                 "identities": results.summary.get("identities", "")},
        "levels": {
            "global": agg,
            "region": {home_region: dict(agg)},
            "country": {"United Kingdom": dict(agg)},
            "airport": airports,
        },
        "flows": flows,
        "exceptions": results.exceptions,
    }


def write_extract(extract: dict, path: str | Path) -> Path:
    path = Path(path)
    path.write_text(json.dumps(extract, indent=2), encoding="utf-8")
    return path


def write_tidy_csv(results, path: str | Path) -> Path:
    path = Path(path)
    results.tidy.to_csv(path, index=False)
    return path


def write_exception_report(results, path: str | Path) -> Path:
    path = Path(path)
    lines = ["Avia Global Aviation Forecast - exception report",
             f"vintage={results.summary['vintage']} scenario={results.summary['scenario']}",
             f"identities: {results.summary.get('identities','')}", ""]
    lines += (results.exceptions or ["No exceptions raised; all identities within tolerance."])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path

r"""Avia against Boeing, region by region, on BOEING's regional classification.

Why. Our six regions cannot be reconciled against Boeing's ten: our single Asia Pacific
faces five of theirs, whose published growth runs from 2.4% to 7.0%. Atlas forecasts
airport by airport and every airport carries a country, so their classification is a
lookup table over the same forecast, not a different model.

Reads config/region_schemes.yaml for the partition and config/comparators.yaml for the
published figures, so nothing in this script is a typed number.

    python scripts/compare_regions_boeing.py                 report to the terminal
    python scripts/compare_regions_boeing.py --json out.json save it for the deck build

Basis. Boeing publishes RPK. Atlas passenger forecasts are converted to RPK through
avia_forecast/stage_length.py, which carries a per-region base distance and a per-region
annual growth rate estimated from Sabre O&D journey length over 2013-2025. The levels are
representative averages and remain [P1], so the comparison is indicative on levels.

The growth term was added on 9 August 2026 and it changes what this script measures. A
CONSTANT stage length cancels inside our own CAGR, so our RPK CAGR equalled our passenger
CAGR to the decimal place while Boeing's carried their stage length growth inside it. Two
thirds of the headline gap was that convention. Run with --constant-stage to reproduce the
old basis; the JSON carries both, so the bridge between them can be drawn without a second
script.

Author: Avia Solutions.
"""
from __future__ import annotations
import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from avia_forecast import stage_length as sl_mod
from avia_forecast.config import _load as cfg_load

DASH = os.path.join(REPO, "webapp", "data", "dashboard.json")
# The served dashboard record carries the country NAME, for display. A region scheme is a
# partition of ISO2 codes, so the join runs through the airport meta file, which is the
# authoritative source of the code. Matching on names would work until it met "Korea".
META = os.path.join(REPO, "data", "global_airport_meta_2025.json")

# The stage length constants that used to live here, and in two measurement scripts, are
# now in config/stage_length.yaml and read through avia_forecast/stage_length.py.


def load_scheme(name="boeing_cmo"):
    s = cfg_load("region_schemes.yaml")["schemes"][name]
    lookup = {}
    for region, codes in (s.get("regions") or {}).items():
        for c in codes:
            if c in lookup:
                raise SystemExit(f"{c} appears in both {lookup[c]} and {region} in scheme "
                                 f"{name}. A region scheme must be a partition.")
            lookup[c] = region
    return s, lookup


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scheme", default="boeing_cmo")
    ap.add_argument("--scenario", default="Baseline")
    ap.add_argument("--json", default=None)
    ap.add_argument("--constant-stage", action="store_true",
                    help="hold stage length constant, the basis this script used before "
                         "9 August 2026, for the bridge between the two")
    a = ap.parse_args()

    if not os.path.isfile(DASH):
        raise SystemExit(f"{DASH} not found. Run scripts/build_dashboard_data.py first.")
    d = json.load(open(DASH))
    YRS, AP = d["years"], d["airports"]
    scheme, lookup = load_scheme(a.scheme)
    default = scheme.get("default")

    published = (d.get("comparators", {}).get("boeing_cmo", {}) or {}).get("prior_edition", {})
    pub_note = published.get("note", "")
    # regional rates live in the note of the prior edition, which is the one whose
    # workbook we hold. Parse them rather than retyping them here.
    pub = {}
    if "Africa" in pub_note:
        for part in pub_note.split("workbook:")[-1].split(","):
            part = part.strip().rstrip(".")
            if not part or "%" not in part:
                continue
            name, val = part.rsplit(" ", 1)
            try:
                pub[name.strip()] = float(val.strip().rstrip("%")) / 100.0
            except ValueError:
                pass

    w = published.get("window") or [2024, 2044]
    n = w[1] - w[0]
    y0 = max(w[0], YRS[0])
    y1 = min(y0 + n, YRS[-1])
    i0, i1 = YRS.index(y0), YRS.index(y1)

    if not os.path.isfile(META):
        raise SystemExit(f"{META} not found; it carries the ISO2 country per airport.")
    meta = json.load(open(META))

    # 476 of the 2,430 forecast airports are absent from the meta file, mostly small
    # fields. Their ISO2 is recovered from the country NAME the dashboard carries, using a
    # name-to-code map built from the airports that ARE in meta. Self-contained: no
    # dependency, and no country name is guessed that the estate does not already resolve.
    name2iso = {}
    for apt in AP:
        rec = meta.get(apt["iata"]) or {}
        c, n = rec.get("country"), apt.get("country")
        if c and n:
            name2iso.setdefault(n, c)

    agg, unmapped = {}, {}
    for apt in AP:
        s = apt["scen"].get(a.scenario)
        if not isinstance(s, list):
            continue
        rec = meta.get(apt["iata"]) or {}
        # The dashboard's country field is MIXED: some records carry a name ("Algeria"),
        # some carry the ISO2 code ("BR"). Try the meta code, then the field itself if it
        # already looks like a code, then the name map. Assuming one form silently lost
        # 441 airports, including every Brazilian and Indian field, to Unassigned.
        raw = apt.get("country")
        cty = (rec.get("country")
               or (raw if isinstance(raw, str) and len(raw) == 2 and raw.isupper() else None)
               or name2iso.get(raw))
        reg = lookup.get(cty)
        if reg is None:
            # Never silently absorbed into a real region: an unassignable airport is shown
            # as unassigned, so it stays in the world total and stays visible.
            unmapped[apt.get("country") or "no country"] = unmapped.get(apt.get("country") or "no country", 0) + 1
            reg = "Unassigned"
        # Level from the engine region the airport record carries, growth from the Boeing
        # region the comparison runs on. Both ends of the window are converted at their
        # own year's distance, which is the whole point: at a constant distance the two
        # conversions cancel and our RPK CAGR is our passenger CAGR.
        base_km = sl_mod.base_km(apt.get("region"))
        f0 = 1.0 if a.constant_stage else sl_mod.factor(reg, y0)
        f1 = 1.0 if a.constant_stage else sl_mod.factor(reg, y1)
        v = agg.setdefault(reg, [0.0, 0.0, 0, 0.0, 0.0])
        v[0] += float(s[i0] or 0) * base_km * f0
        v[1] += float(s[i1] or 0) * base_km * f1
        v[2] += 1
        v[3] += float(s[i0] or 0) * base_km          # the same sum at a constant distance,
        v[4] += float(s[i1] or 0) * base_km          # so the bridge needs no second run

    rows = []
    for reg in sorted(set(list(agg) + list(pub))):
        v = agg.get(reg)
        ours = ((v[1] / v[0]) ** (1 / (i1 - i0)) - 1) if (v and v[0] > 0) else None
        flat = ((v[4] / v[3]) ** (1 / (i1 - i0)) - 1) if (v and v[3] > 0) else None
        theirs = pub.get(reg)
        rows.append({"region": reg, "airports": (v[2] if v else 0), "avia": ours,
                     "avia_constant_stage": flat,
                     "stage_growth": (None if a.constant_stage else sl_mod.growth(reg)),
                     "boeing": theirs,
                     "diff_pp": ((ours - theirs) * 100 if (ours is not None and theirs is not None) else None)})

    tot = [sum(x[0] for x in agg.values()), sum(x[1] for x in agg.values())]
    world = (tot[1] / tot[0]) ** (1 / (i1 - i0)) - 1
    tot_f = [sum(x[3] for x in agg.values()), sum(x[4] for x in agg.values())]
    world_flat = (tot_f[1] / tot_f[0]) ** (1 / (i1 - i0)) - 1
    wpub = published.get("cagr")

    print(f"Avia against {scheme['label']}, RPK CAGR, {a.scenario} case")
    print(f"Avia window {y0}-{y1}; Boeing {w[0]}-{w[1]} ({published.get('edition','edition not recorded')})")
    print("Stage length held constant" if a.constant_stage else
          "Stage length grows on the rates in config/stage_length.yaml, estimated from "
          "Sabre O&D\njourney length 2013-2025. See MEASUREMENTS.md section 7.")
    print()
    print(f"  {'region':<18}{'airports':>9}{'constant':>10}{'stage':>8}{'Avia':>9}"
          f"{'Boeing':>9}{'diff':>9}")
    for r in sorted(rows, key=lambda r: -(r["avia"] or 0)):
        av = f"{r['avia']*100:.1f}%" if r["avia"] is not None else "n/a"
        fl = f"{r['avia_constant_stage']*100:.1f}%" if r["avia_constant_stage"] is not None else "n/a"
        sg = f"{r['stage_growth']*100:.2f}%" if r.get("stage_growth") is not None else "n/a"
        bo = f"{r['boeing']*100:.1f}%" if r["boeing"] is not None else "n/a"
        df = f"{r['diff_pp']:+.1f}pp" if r["diff_pp"] is not None else "n/a"
        print(f"  {r['region']:<18}{r['airports']:>9}{fl:>10}{sg:>8}{av:>9}{bo:>9}{df:>9}")
    wd = f"{(world - wpub) * 100:+.1f}pp" if wpub else "n/a"
    wsg = ("n/a" if a.constant_stage else f"{sl_mod.growth('World')*100:.2f}%")
    print(f"  {'WORLD':<18}{sum(r['airports'] for r in rows):>9}{world_flat*100:>9.1f}%"
          f"{wsg:>8}{world*100:>8.1f}%{(wpub*100 if wpub else 0):>8.1f}%{wd:>9}")

    if unmapped:
        top = sorted(unmapped.items(), key=lambda kv: -kv[1])[:12]
        print(f"\n  {sum(unmapped.values())} airports in {len(unmapped)} countries could not be "
              f"assigned and are shown as Unassigned:")
        print("   " + ", ".join(f"{c} ({k})" for c, k in top))
        print("  Add them to config/region_schemes.yaml. A silent catch-all is how a region "
              "ends up quietly wrong.")

    if a.json:
        json.dump({"scheme": a.scheme, "label": scheme["label"], "scenario": a.scenario,
                   "avia_window": [y0, y1], "boeing_window": w,
                   "boeing_edition": published.get("edition"),
                   "rows": rows, "world_avia": world,
                   "world_avia_constant_stage": world_flat,
                   "world_stage_growth": (None if a.constant_stage
                                          else sl_mod.growth("World")),
                   "stage_length_basis": ("constant" if a.constant_stage
                                          else "config/stage_length.yaml, estimated from "
                                               "Sabre O&D journey length 2013-2025"),
                   "world_boeing": wpub,
                   "unmapped": unmapped}, open(a.json, "w"), indent=1)
        print(f"\nwritten: {a.json}")


if __name__ == "__main__":
    main()

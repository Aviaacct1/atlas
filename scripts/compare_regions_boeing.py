r"""Avia against Boeing, region by region, on BOEING's regional classification.

Why. Our six regions cannot be reconciled against Boeing's ten: our single Asia Pacific
faces five of theirs, whose published growth runs from 2.4% to 7.0%. Atlas forecasts
airport by airport and every airport carries a country, so their classification is a
lookup table over the same forecast, not a different model.

Reads config/region_schemes.yaml for the partition and config/comparators.yaml for the
published figures, so nothing in this script is a typed number.

    python scripts/compare_regions_boeing.py                 report to the terminal
    python scripts/compare_regions_boeing.py --json out.json save it for the deck build

Basis. Boeing publishes RPK. Atlas passenger forecasts are converted to RPK using the
per-region stage lengths the dashboard uses, which are representative averages and are
already flagged as a [P1] item: the comparison is therefore indicative on levels and
sound on growth, because a constant stage length cancels in a CAGR. Where our stage
length itself should grow, it does not, and that is one candidate for the gap this
script is built to explain.

Author: Avia Solutions.
"""
from __future__ import annotations
import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from avia_forecast.config import _load as cfg_load

DASH = os.path.join(REPO, "webapp", "data", "dashboard.json")
# The served dashboard record carries the country NAME, for display. A region scheme is a
# partition of ISO2 codes, so the join runs through the airport meta file, which is the
# authoritative source of the code. Matching on names would work until it met "Korea".
META = os.path.join(REPO, "data", "global_airport_meta_2025.json")

# Per-region stage length, km per passenger, as the dashboard applies it. Keyed on OUR
# regions because that is what the airport records carry. [P1] representative averages.
SL = {"Europe": 1.35, "Asia Pacific": 1.95, "North America": 1.6, "South America": 1.45,
      "Middle East": 2.9, "Africa": 1.8, "_G": 1.72}


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
        sl = SL.get(apt.get("region"), SL["_G"])
        v = agg.setdefault(reg, [0.0, 0.0, 0])
        v[0] += float(s[i0] or 0) * sl
        v[1] += float(s[i1] or 0) * sl
        v[2] += 1

    rows = []
    for reg in sorted(set(list(agg) + list(pub))):
        v = agg.get(reg)
        ours = ((v[1] / v[0]) ** (1 / (i1 - i0)) - 1) if (v and v[0] > 0) else None
        theirs = pub.get(reg)
        rows.append({"region": reg, "airports": (v[2] if v else 0), "avia": ours,
                     "boeing": theirs,
                     "diff_pp": ((ours - theirs) * 100 if (ours is not None and theirs is not None) else None)})

    tot = [sum(x[0] for x in agg.values()), sum(x[1] for x in agg.values())]
    world = (tot[1] / tot[0]) ** (1 / (i1 - i0)) - 1
    wpub = published.get("cagr")

    print(f"Avia against {scheme['label']}, RPK CAGR, {a.scenario} case")
    print(f"Avia window {y0}-{y1}; Boeing {w[0]}-{w[1]} ({published.get('edition','edition not recorded')})\n")
    print(f"  {'region':<18}{'airports':>9}{'Avia':>9}{'Boeing':>9}{'diff':>9}")
    for r in sorted(rows, key=lambda r: -(r["avia"] or 0)):
        av = f"{r['avia']*100:.1f}%" if r["avia"] is not None else "n/a"
        bo = f"{r['boeing']*100:.1f}%" if r["boeing"] is not None else "n/a"
        df = f"{r['diff_pp']:+.1f}pp" if r["diff_pp"] is not None else "n/a"
        print(f"  {r['region']:<18}{r['airports']:>9}{av:>9}{bo:>9}{df:>9}")
    wd = f"{(world - wpub) * 100:+.1f}pp" if wpub else "n/a"
    print(f"  {'WORLD':<18}{sum(r['airports'] for r in rows):>9}{world*100:>8.1f}%"
          f"{(wpub*100 if wpub else 0):>8.1f}%{wd:>9}")

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
                   "rows": rows, "world_avia": world, "world_boeing": wpub,
                   "unmapped": unmapped}, open(a.json, "w"), indent=1)
        print(f"\nwritten: {a.json}")


if __name__ == "__main__":
    main()

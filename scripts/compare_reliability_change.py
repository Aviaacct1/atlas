"""Report the effect of the T1-T6 reliability rule and the corrected fare prior.

Run it after estimate_airport_diagnostics.py. It compares the new verdict (`reliable`, the book's
six-test rule) against the verdict the forecast used before (`reliable_legacy`, the three-condition
shortcut), says which test did the rejecting, and reports the world growth rate from whichever
served bundle it can find, so the impact is measured rather than asserted. Author: Avia Solutions.
"""
from __future__ import annotations
import json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(HERE, "data", "airport_regress.json")


def _load(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def world_cagr():
    """Whole-horizon world growth rate from any served bundle that carries a world series."""
    for rel in (("webapp", "data", "dashboard.json"), ("webapp", "data", "world.json"),
                ("data", "global_terminal_2024_2050.json")):
        d = _load(os.path.join(HERE, *rel))
        if not isinstance(d, dict):
            continue
        for key in ("world", "world_terminal", "totals"):
            s = d.get(key)
            if isinstance(s, dict) and len(s) > 2:
                yrs = sorted(int(y) for y in s if str(y).isdigit())
                if len(yrs) > 1:
                    a, b = s[str(yrs[0])], s[str(yrs[-1])]
                    try:
                        a, b = float(a), float(b)
                        if a > 0:
                            return os.path.join(*rel), yrs[0], yrs[-1], (b / a) ** (1.0 / (yrs[-1] - yrs[0])) - 1.0
                    except Exception:
                        pass
    return None, None, None, None


def main():
    reg = _load(REG)
    if not reg:
        print("airport_regress.json not found. Run scripts/estimate_airport_diagnostics.py first.")
        return 1

    n = len(reg)
    new = [k for k, v in reg.items() if v.get("reliable")]
    old = [k for k, v in reg.items() if v.get("reliable_legacy")]
    lost = sorted(set(old) - set(new))
    gained = sorted(set(new) - set(old))
    rule = next((v.get("rule") for v in reg.values() if v.get("rule")), "unknown")
    prior = next((v.get("bF_prior") for v in reg.values() if v.get("bF_prior") is not None), "unknown")

    print("=" * 72)
    print("ELASTICITY SET: effect of the six-test rule and the corrected fare prior")
    print("=" * 72)
    print(f"  airports fitted                      {n}")
    print(f"  rule applied                         {rule}")
    print(f"  fare prior used in the fit           {prior}   (was +0.293, the rejected estimate)")
    print(f"  used their own elasticity BEFORE     {len(old)}")
    print(f"  use their own elasticity NOW         {len(new)}")
    print(f"  lost their own elasticity            {len(lost)}")
    print(f"  gained their own elasticity          {len(gained)}")

    fails = {}
    for v in reg.values():
        t = v.get("tests") or {}
        if t and not v.get("reliable"):
            for k in ("T1_sign", "T2_range", "T3_significance", "T4_fit", "T5_history", "T6_cagr_cross_check"):
                if t.get(k) is False:
                    fails[k] = fails.get(k, 0) + 1
    if fails:
        print("\n  why airports were rejected (an airport can fail more than one test):")
        for k, c in sorted(fails.items(), key=lambda x: -x[1]):
            print(f"    {k:24s} {c}")

    if lost:
        big = sorted(lost, key=lambda k: -(reg[k].get("tests", {}).get("avg_flow_mppa") or 0))[:15]
        print("\n  largest airports that now fall back to the published research value:")
        for k in big:
            v = reg[k]; t = v.get("tests") or {}
            why = ", ".join(x for x in ("T1_sign", "T2_range", "T3_significance", "T4_fit",
                                        "T5_history", "T6_cagr_cross_check") if t.get(x) is False)
            print(f"    {k}  {t.get('avg_flow_mppa','?'):>6} mppa   bG {v.get('bG_est')}   failed: {why or 'n/a'}")

    src, y0, y1, g = world_cagr()
    print("\n" + "=" * 72)
    if g is not None:
        print(f"WORLD GROWTH RATE  {g*100:.2f}% a year, {y0} to {y1}   (from {src})")
        print("Compare with the 3.05% the forecast shipped before this change, and ACI's 3.4%.")
    else:
        print("WORLD GROWTH RATE  no served bundle found yet. Re-run after the dashboard build.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())

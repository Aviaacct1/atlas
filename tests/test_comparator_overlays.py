"""Every overlay comparator resolves to a real colour on the dashboard.

Guards the fault found 16 August 2026: the comparator keys changed from boeing/airbus
to boeing_cmo/airbus_gmf when the rates moved into config/comparators.yaml (9 August),
the page's colour map kept the old keys, and every overlay line drew with
stroke="undefined": the toggle chip worked and the line was invisible. The page now
resolves colours by prefix with a visible grey fallback; this test asserts that every
overlay key in the yaml matches a prefix the page's colour map defines, so a rename
shows up here before it shows up as an invisible line. Author: Avia Solutions.
"""
import os
import re

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = open(os.path.join(REPO, "webapp", "dashboard.html"), encoding="utf-8").read()
CMP = yaml.safe_load(open(os.path.join(REPO, "config", "comparators.yaml"), encoding="utf-8"))


def _page_colour_prefixes():
    m = re.search(r"const OVLC=\{([^}]*)\}", PAGE)
    assert m, "OVLC colour map not found in dashboard.html"
    return {k.strip() for k in re.findall(r"(\w+):", m.group(1))}


def test_every_overlay_key_has_a_colour_prefix():
    prefixes = _page_colour_prefixes()
    for key, c in (CMP.get("comparators") or {}).items():
        if c.get("overlay"):
            assert any(key.startswith(p) for p in prefixes), (
                f"comparator '{key}' has overlay: true but no colour prefix in OVLC; "
                f"its line would fall back to grey. Add the prefix to OVLC in dashboard.html.")


def test_page_resolves_colours_by_prefix_not_raw_key():
    # the raw lookup that produced stroke="undefined" must not return
    assert "ovlColour" in PAGE
    assert 'stroke="${OVLC[d.k]}"' not in PAGE

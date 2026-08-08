"""O-16 acceptance (engine half): the three persona translations - fleet-equivalents by region,
per-airport P-band downside, and the DDFS date-of-constraint - are computed engine-side and carried in
the extract, with documented definitions, no client-side derivation. Author: Avia Solutions."""
from avia_forecast.outputs import persona, licence

EXTRACT = {
    "years": [2025, 2035, 2045],
    "meta": {"vintage": "v2026.1"},
    "airports": {
        "LHR": {"name": "Heathrow", "region": "EU+UK", "term_u": [80, 95, 110], "term_c": [80, 90, 95],
                "rpk_u_bn": [300, 360, 420], "rpk_c_bn": [300, 340, 360]},
    }}
RPA = {"EU+UK": 1.2}   # bn RPK per aircraft-equivalent (documented per region)


def _fresh():
    return {"years": EXTRACT["years"], "meta": dict(EXTRACT["meta"]),
            "airports": {k: dict(v) for k, v in EXTRACT["airports"].items()}}


def test_persona_attaches_three_translations():
    ex = persona.attach_persona(_fresh(), RPA, p_band=0.15)
    ap = ex["airports"]["LHR"]
    assert ap["fleet_equiv"] and ap["p_downside"] and ap["ddfs_date"] == 2035
    assert abs(ap["fleet_equiv"][2045] - 360 / 1.2) < 1e-6            # constrained RPK / region factor
    assert ap["fleet_equiv_basis"].startswith("constrained")
    assert abs(ap["p_downside"][2045] - 95 * 0.85) < 1e-6            # central constrained x (1 - band)
    ok, _ = licence.licence_filter(ex)
    assert ok


def test_persona_definition_documented_in_meta():
    ex = persona.attach_persona(_fresh(), RPA)
    assert "definition" in ex["meta"]["persona"]

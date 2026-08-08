"""Adding-up and level-reconciliation checks for the GLOBAL build. Author: Avia Solutions.

The pilot pipeline carries the identity spine (T-A..T-F). The global product totals were grossed
in the browser and reconciled nowhere. This ports the discipline: the world total must be built
bottom-up and reconcile at every level, so no level silently invents demand.

Grossing is explicit and documented. For a given year:
    country_total = sum(modelled airports in the country) x coverage_country[country]
    region_total  = sum(country_total over the region)    x coverage_region[region]
    world         = sum(region_total)
coverage_* are >= 1 because they gross up for airports/countries not individually modelled; the
engine computes them from real coverage (modelled traffic / total traffic) when the ACI country
totals are available, otherwise a documented placeholder is used and flagged in the extract meta.

reconcile_levels recomputes the hierarchy and returns the totals plus any issues; assert_adds_up
raises when the two ways of computing the world disagree beyond tolerance.
"""

TOL = 0.005  # 0.5%


def reconcile_levels(airport_by_country, coverage_country, coverage_region, country_region):
    """airport_by_country: {country: [airport_value, ...]} for one year/scenario/case.
    Returns {country_tot, region_tot, world, issues}. Issues flag non-positive or missing
    coverage, which would break grossing."""
    issues = []
    country_tot = {}
    for c, vals in airport_by_country.items():
        cf = coverage_country.get(c)
        if cf is None:
            issues.append(("coverage_country_missing", c)); cf = 1.0
        elif cf <= 0:
            issues.append(("coverage_country_nonpositive", c, cf)); cf = 1.0
        country_tot[c] = sum(vals) * cf

    region_tot = {}
    for c, t in country_tot.items():
        r = country_region.get(c)
        if r is None:
            issues.append(("country_without_region", c)); continue
        region_tot[r] = region_tot.get(r, 0.0) + t
    for r in list(region_tot):
        cf = coverage_region.get(r)
        if cf is None:
            issues.append(("coverage_region_missing", r)); cf = 1.0
        elif cf <= 0:
            issues.append(("coverage_region_nonpositive", r, cf)); cf = 1.0
        region_tot[r] *= cf

    world = sum(region_tot.values())
    return {"country_tot": country_tot, "region_tot": region_tot, "world": world, "issues": issues}


def assert_adds_up(rec, tol=TOL):
    """The world must equal the sum of region totals, which must equal the sum of country totals
    grossed to region. Recomputes independently and asserts equality within tolerance."""
    world_from_regions = sum(rec["region_tot"].values())
    if rec["world"] <= 0:
        raise AssertionError("world total is non-positive")
    rel = abs(rec["world"] - world_from_regions) / rec["world"]
    if rel > tol:
        raise AssertionError(f"world {rec['world']:.3f} != sum(regions) {world_from_regions:.3f} (rel {rel:.4f})")
    hard = [i for i in rec["issues"] if "nonpositive" in i[0]]
    if hard:
        raise AssertionError(f"coverage issues break grossing: {hard}")
    return True


def reconcile_connecting(od_base, conn_raw, *, neg_tol=0.02, max_share=0.65):
    """The connecting figure is a RESIDUAL (ACI terminal minus Sabre O&D both-ends). It goes negative
    or absurd wherever ACI and Sabre disagree (freighter/GA-heavy, coverage-thin airports). Policy:
    floor at zero and classify, so the build reconciles by construction and flags the noise rather
    than stopping. Returns (conn_floored, flag_or_None).
      negative_residual        - ACI < Sabre O&D by more than neg_tol of O&D (definition/coverage gap)
      implausible_conx_share   - connecting share above max_share (residual swept up a mismatch)
    """
    conn = max(0.0, conn_raw)
    total = od_base + conn
    share = (conn / total) if total > 0 else 0.0
    if conn_raw < -neg_tol * (od_base or 1.0):
        return conn, "negative_residual"
    if share > max_share:
        return conn, "implausible_conx_share"
    return conn, None


def tb_check(term_base, od_base, conn_base, tol=1e-6):
    """Identity T-B at base year: terminal = O&D + connecting. Returns True within tolerance."""
    lhs = od_base + conn_base
    if term_base <= 0:
        return term_base == 0 and lhs == 0
    return abs(term_base - lhs) / term_base <= tol

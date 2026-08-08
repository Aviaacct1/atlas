#!/usr/bin/env python3
"""
Avia Solutions - Genoa NYC comparator / stimulation / fare-premium extract.
==========================================================================
Read-only against the Sabre store (C:\\Avia\\sabre.duckdb, table 'sabre').
Bidirectional O&D (both directions summed). NYC = JFK+EWR+LGA.

Three analyses for the Genoa-NYC deck:
  A. Comparator trajectories 2013-2025: secondary-city NYC markets, year by year,
     nonstop vs connecting, and the operating carrier on the nonstop (the strategy
     and survival signal). Marks the launch year.
  B. Measured stimulation: market step-change around each nonstop launch (replaces
     the assumed 1.5-2.0x multiples on slide 7 with real numbers).
  C. Origin split (US / home country / other) per comparator - inbound vs outbound.
  D. Nonstop fare premium: nonstop vs connecting pax-weighted yield.

Saves small CSVs to C:\\Avia for the slide build, and prints everything.

  py -3.12 C:\\Avia\\comparator_extract.py
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import duckdb, csv, os

DB  = _paths.SABRE_DB
OUT = _paths.AVIA
con = duckdb.connect(DB, read_only=True)
NYC = "('JFK','EWR','LGA')"
NONSTOP_FLOOR = 1000   # bidirectional pax/yr to count a market as "nonstop served"

# Comparator set: Italian secondaries + European secondary analogues + references.
# home = ISO-ish country name as it appears in poo_country_name (checked below).
COMPS = [
    ("GOA", "Genoa",     "ITALY"),
    ("NAP", "Naples",    "ITALY"),
    ("BLQ", "Bologna",   "ITALY"),
    ("CTA", "Catania",   "ITALY"),
    ("PMO", "Palermo",   "ITALY"),
    ("PSA", "Pisa",      "ITALY"),
    ("TRN", "Turin",     "ITALY"),
    ("VCE", "Venice",    "ITALY"),
    ("NCE", "Nice",      "FRANCE"),
    ("OPO", "Porto",     "PORTUGAL"),
    ("KRK", "Krakow",    "POLAND"),
    ("MXP", "Milan MXP", "ITALY"),   # reference: established nonstop
    ("FCO", "Rome FCO",  "ITALY"),   # reference: established nonstop
]

# years actually present in the store (2020 is merged into the 2021 source file)
YEARS = sorted(r[0] for r in con.execute(
    "SELECT DISTINCT source_year FROM sabre WHERE source_year IS NOT NULL").fetchall())
print("years in store:", YEARS)

def both(ap, yr, nonstop=None):
    """Bidirectional pax for airport<->NYC in a year. nonstop True/False/None."""
    cond = ""
    if nonstop is True:  cond = " AND connecting_airport1 IS NULL"
    if nonstop is False: cond = " AND connecting_airport1 IS NOT NULL"
    q = f"""SELECT sum(passengers) FROM sabre WHERE source_year={yr}{cond} AND (
      (origin_airport='{ap}' AND destination_airport IN {NYC}) OR
      (destination_airport='{ap}' AND origin_airport IN {NYC}))"""
    return con.execute(q).fetchone()[0] or 0

def ns_carriers(ap, yr, n=3):
    q = f"""SELECT operating_airline, sum(passengers) p FROM sabre WHERE source_year={yr}
      AND connecting_airport1 IS NULL AND (
      (origin_airport='{ap}' AND destination_airport IN {NYC}) OR
      (destination_airport='{ap}' AND origin_airport IN {NYC}))
      GROUP BY 1 HAVING sum(passengers)>0 ORDER BY 2 DESC LIMIT {n}"""
    return con.execute(q).fetchall()

# ----------------------------------------------------------------------------
print("="*78)
print("OUTPUT A: comparator NYC trajectories (bidirectional), nonstop vs connecting")
rowsA = []
for ap, name, home in COMPS:
    print(f"\n-- {name} ({ap}) --")
    print(f"   {'yr':>4} {'total':>9} {'nonstop':>9} {'connect':>9}  top nonstop carrier(s)")
    launch = None
    for yr in YEARS:
        tot = both(ap, yr); ns = both(ap, yr, True); cx = both(ap, yr, False)
        cs = ns_carriers(ap, yr)
        cstr = ", ".join(f"{c}:{int(v):,}" for c, v in cs) if cs else ""
        if ns >= NONSTOP_FLOOR and launch is None:
            launch = yr
        mark = "  <== nonstop launch" if yr == launch else ""
        print(f"   {yr:>4} {tot:>9,.0f} {ns:>9,.0f} {cx:>9,.0f}  {cstr}{mark}")
        rowsA.append([name, ap, yr, round(tot), round(ns), round(cx), cstr,
                      1 if yr == launch else 0])
    print(f"   nonstop launch year: {launch if launch else 'no nonstop in window'}")

with open(os.path.join(OUT, "comparator_trajectories.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["city","airport","year","total","nonstop","connecting","nonstop_carriers","is_launch_year"])
    w.writerows(rowsA)

# ----------------------------------------------------------------------------
print("\n" + "="*78)
print("OUTPUT B: measured stimulation around nonstop launch")
print("   pre = mean total over up to 2 yrs before launch (all-connecting base)")
print("   post = mean total over launch year + up to 2 yrs after")
rowsB = []
for ap, name, home in COMPS:
    series = {yr: both(ap, yr) for yr in YEARS}
    nss = {yr: both(ap, yr, True) for yr in YEARS}
    launch = next((yr for yr in YEARS if nss[yr] >= NONSTOP_FLOOR), None)
    if not launch or launch == YEARS[0]:
        print(f"   {name:<11} no usable pre/post window (launch={launch})")
        continue
    pre_yrs  = [y for y in YEARS if y < launch][-2:]
    post_yrs = [y for y in YEARS if y >= launch][:3]
    pre  = sum(series[y] for y in pre_yrs)/len(pre_yrs) if pre_yrs else 0
    post = sum(series[y] for y in post_yrs)/len(post_yrs) if post_yrs else 0
    ratio = post/pre if pre else 0
    rstr = f"x{ratio:.2f}" if pre else "x n/a (no pre base)"
    post_ns_share = (sum(nss[y] for y in post_yrs)/sum(series[y] for y in post_yrs)) if sum(series[y] for y in post_yrs) else 0
    print(f"   {name:<11} launch {launch}  pre {pre:>8,.0f} ({pre_yrs})  post {post:>8,.0f} ({post_yrs})  {rstr}  nonstop share post {post_ns_share:.0%}")
    rowsB.append([name, ap, launch, round(pre), round(post), round(ratio,2), round(post_ns_share,3)])

with open(os.path.join(OUT, "comparator_stimulation.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["city","airport","launch_year","pre_mean","post_mean","stimulation_x","nonstop_share_post"])
    w.writerows(rowsB)

# ----------------------------------------------------------------------------
print("\n" + "="*78)
print("OUTPUT C: origin split (point-of-origin country), latest year, all itineraries")
latest = YEARS[-1]
rowsC = []
for ap, name, home in COMPS:
    tot = both(ap, latest)
    if tot < 200:
        print(f"   {name:<11} too small ({tot:,.0f})"); continue
    q = f"""SELECT poo_country_name, sum(passengers) p FROM sabre WHERE source_year={latest} AND (
      (origin_airport='{ap}' AND destination_airport IN {NYC}) OR
      (destination_airport='{ap}' AND origin_airport IN {NYC}))
      GROUP BY 1 ORDER BY 2 DESC"""
    rows = con.execute(q).fetchall()
    USKEYS = ("UNITED STATES", "U.S.A", "USA", "U.S.")
    us   = sum(v for c, v in rows if c and any(k in str(c).upper() for k in USKEYS))
    hm   = sum(v for c, v in rows if c and str(c).upper() == home)
    oth  = tot - us - hm
    top3 = ", ".join(f"{c}:{int(v):,}" for c, v in rows[:3])
    print(f"   {name:<11} {latest}: total {tot:>8,.0f}  US {us/tot:>4.0%}  {home.title()} {hm/tot:>4.0%}  other {oth/tot:>4.0%}   | top: {top3}")
    rowsC.append([name, ap, latest, round(tot), round(us/tot,3), round(hm/tot,3), round(oth/tot,3)])

with open(os.path.join(OUT, "comparator_origin_split.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["city","airport","year","total","us_share","home_share","other_share"])
    w.writerows(rowsC)

# ----------------------------------------------------------------------------
print("\n" + "="*78)
print("OUTPUT D: nonstop fare premium, pax-weighted yield (total_revenue_usd / pax)")
def yield_of(ap_list, yr, nonstop=None, origin_only=False):
    aset = "(" + ",".join(f"'{a}'" for a in ap_list) + ")"
    cond = ""
    if nonstop is True:  cond = " AND connecting_airport1 IS NULL"
    if nonstop is False: cond = " AND connecting_airport1 IS NOT NULL"
    if origin_only:
        where = f"origin_airport IN {aset} AND destination_airport IN {NYC}"
    else:
        where = f"((origin_airport IN {aset} AND destination_airport IN {NYC}) OR (destination_airport IN {aset} AND origin_airport IN {NYC}))"
    r = con.execute(f"""SELECT sum(passengers), sum(total_revenue_usd) FROM sabre
      WHERE source_year={yr}{cond} AND {where}""").fetchone()
    pax, rev = r[0] or 0, r[1] or 0
    return (rev/pax if pax else 0, pax)

print(f"-- {latest} --")
for label, aps in [("Milan MXP", ["MXP"]), ("Rome FCO", ["FCO"]), ("Genoa GOA", ["GOA"])]:
    ny, pn = yield_of(aps, latest, True)
    cy, pc = yield_of(aps, latest, False)
    print(f"   {label:<11} nonstop yield ${ny:>6,.0f} ({pn:>8,.0f} pax)   connecting yield ${cy:>6,.0f} ({pc:>8,.0f} pax)")
# headline premium: MXP nonstop vs GOA connecting (what a GOA pax pays today vs nonstop benchmark)
mxp_ns = yield_of(["MXP"], latest, True)[0]
goa_cx = yield_of(["GOA"], latest, False)[0]
itl = [a for a, n, h in COMPS if h == "ITALY"]
it_ns = yield_of(itl, latest, True)
it_cx = yield_of(itl, latest, False)
print(f"\n   Italy-NYC overall: nonstop ${it_ns[0]:,.0f} vs connecting ${it_cx[0]:,.0f}  -> nonstop premium {(it_ns[0]/it_cx[0]-1)*100:+.0f}%" if it_cx[0] else "")
print(f"   GOA connecting ${goa_cx:,.0f} vs MXP nonstop ${mxp_ns:,.0f}  -> nonstop benchmark {(mxp_ns/goa_cx-1)*100:+.0f}% above GOA's current connecting fare" if goa_cx else "")

with open(os.path.join(OUT, "fare_premium.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["year","scope","nonstop_yield","connecting_yield"])
    for label, aps in [("MXP",["MXP"]),("FCO",["FCO"]),("GOA",["GOA"]),("Italy_all",itl)]:
        w.writerow([latest, label, round(yield_of(aps,latest,True)[0]), round(yield_of(aps,latest,False)[0])])

con.close()
print("\nDONE. CSVs written to C:\\Avia: comparator_trajectories, comparator_stimulation, comparator_origin_split, fare_premium.")
print("Note: Sabre has no aircraft-type field; carrier identifies the strategy. Map carrier->aircraft in the slide (e.g. UA NAP=767, Neos=787, JetBlue/Aer Lingus=A321neo/XLR).")

#!/usr/bin/env python3
"""
Avia Solutions - Genoa-NYC first-draft QSI forecast (transparent model)
=======================================================================
Structure: addressable market (catchment) -> QSI capture (schedule) ->
booked passengers (load-factor convergence). Every input is labelled MEASURED
(from the Sabre store) or ASSUMED (a defendable starting point you flex).

Demand anchors are read from the Sabre store if reachable, else the figures we
measured on 26 June 2026 are used as fallbacks. The QSI capture is taken from a
multi-hub OAG run when --oag is given (run_multihub_qsi), else the ASSUMED value.

  py -3.12 goa_nyc_forecast.py                 # runs on assumptions + store demand
  py -3.12 goa_nyc_forecast.py --oag "<2025 Hub Airports file>"   # real QSI capture
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import argparse

# ---------------------------------------------------------------------------
# ASSUMED inputs (edit these; each is a judgement, not a measurement)
# ---------------------------------------------------------------------------
A = dict(
    catchment_primary   = 1_500_000,   # Province of Genoa, 60-min drive
    catchment_secondary = 3_200_000,   # 90-min drive
    italy_population    = 59_000_000,   # to derive an NYC trip rate per head
    leakage_share_of_mxp = 0.04,        # Genoa-area share of Milan-NYC traffic (needs postcode/Stage 1)
    stimulation          = 1.20,        # a direct service grows the market vs indirect-only
    qsi_capture          = 0.50,        # share of the addressable Genoa-NYC market the direct service wins
                                        #   (REPLACED by the OAG run when --oag is given)
    seats                = 180,         # narrowbody transatlantic (e.g. A321XLR / 737 MAX)
    freq_per_week        = 3,           # summer-weighted starting assumption
    weeks                = 30,          # summer-weighted season (set 52 for year-round)
    target_lf            = 0.80,
)

# ---------------------------------------------------------------------------
# MEASURED fallbacks (2025 Sabre, both directions) - overwritten if store reachable
# ---------------------------------------------------------------------------
M = dict(goa_nyc=9_278, mxp_nyc=708_445, italy_nyc=2_366_882)


def from_store(db=_paths.SABRE_DB):
    try:
        import duckdb
        con = duckdb.connect(db, read_only=True)
        nyc = "('JFK','EWR','LGA')"
        def bidir(a):
            return con.execute(f"""SELECT sum(passengers) FROM sabre WHERE source_year=2025 AND (
              (origin_airport='{a}' AND destination_airport IN {nyc}) OR
              (destination_airport='{a}' AND origin_airport IN {nyc}))""").fetchone()[0] or 0
        it = con.execute(f"""SELECT sum(passengers) FROM sabre WHERE source_year=2025 AND
              poo_country_name ILIKE 'Ital%' AND (destination_airport IN {nyc} OR origin_airport IN {nyc})""").fetchone()[0] or M['italy_nyc']
        out = dict(goa_nyc=bidir('GOA'), mxp_nyc=bidir('MXP'), italy_nyc=it)
        con.close()
        return out, True
    except Exception as e:
        return dict(M), False


def qsi_from_oag(oag, mct=None):
    """Direct Genoa-JFK QSI capture of the GOA market, from a 2025 multi-hub OAG pull."""
    try:
        import run_multihub_qsi as R
        res = R.run(oag, ['JFK', 'EWR', 'LGA'],
                    proposed=R._proposed_leg("XX,GOA,JFK,1000,1330,570"),
                    circuity_cut=1.25, mct_file=mct)
        for r in res['rows']:
            if r['market'] == 'GOA':
                return r['proposed_capture'], True
        return None, False
    except Exception:
        return None, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oag", default=None, help="2025 multi-hub OAG file for the real QSI capture")
    ap.add_argument("--mct", default=None)
    a = ap.parse_args()

    M2, live = from_store()
    cap, cap_live = (qsi_from_oag(a.oag, a.mct) if a.oag else (None, False))
    qsi = cap if cap_live and cap is not None else A['qsi_capture']

    per_capita = M2['italy_nyc'] / A['italy_population']     # Italy NYC O&D per head, both ways
    addr_primary   = A['catchment_primary']   * per_capita
    addr_secondary = A['catchment_secondary'] * per_capita
    addr_leakage   = M2['goa_nyc'] + M2['mxp_nyc'] * A['leakage_share_of_mxp']
    seats_year = A['seats'] * A['freq_per_week'] * A['weeks'] * 2

    print("="*68)
    print("GENOA-NYC FIRST-DRAFT QSI FORECAST  (transparent model)")
    print("="*68)
    print(f"Demand anchors {'(MEASURED, live store)' if live else '(MEASURED, fallback figures)'}:")
    print(f"  Genoa-NYC O&D today        : {M2['goa_nyc']:>10,.0f}")
    print(f"  Milan-NYC O&D              : {M2['mxp_nyc']:>10,.0f}")
    print(f"  Italy-NYC O&D              : {M2['italy_nyc']:>10,.0f}")
    print(f"  Italy NYC trips per head   : {per_capita:.4f}")
    print(f"\nQSI capture of the direct service: {qsi:.0%}  {'(from OAG run)' if cap_live else '(ASSUMED - awaiting 2025 OAG)'}")
    print(f"\nAddressable Genoa-area NYC market (three views):")
    print(f"  A. observed + Milan leakage @ {A['leakage_share_of_mxp']:.0%}  : {addr_leakage:>10,.0f}   (ASSUMED leakage)")
    print(f"  B. primary catchment 1.5m x rate        : {addr_primary:>10,.0f}   (ASSUMED catchment)")
    print(f"  C. secondary catchment 3.2m x rate      : {addr_secondary:>10,.0f}   (ASSUMED catchment)")

    print("\nFORECAST (addressable x stimulation x QSI capture), and load factor:")
    print(f"  capacity offered/yr = {A['seats']} seats x {A['freq_per_week']}/wk x {A['weeks']} wks x 2 = {seats_year:,.0f}")
    for label, addr in [("A observed+leakage", addr_leakage), ("B primary catchment", addr_primary), ("C secondary catchment", addr_secondary)]:
        pax = addr * A['stimulation'] * qsi
        lf = pax / seats_year if seats_year else 0
        print(f"  {label:22}: {pax:>9,.0f} pax  -> LF {lf:>5.0%}")

    print("\nSENSITIVITY - forecast passengers by QSI capture x addressable view:")
    caps = [0.30, 0.40, 0.50, 0.60, 0.70]
    print("   capture |  A leak   B prim   C sec")
    for c in caps:
        row = "   ".join(f"{addr*A['stimulation']*c:>7,.0f}" for addr in (addr_leakage, addr_primary, addr_secondary))
        print(f"     {c:.0%}   |  {row}")

    print("\nNOTES: capture replaced by the 2025 OAG run when available. The catchment/leakage")
    print("views (A/B/C) are the Stage 1 question (postcode/cell data) - shown, not asserted.")
    print("Seasonality (weeks) is an operating-model assumption pending the monthly Sabre pull.")


if __name__ == "__main__":
    main()

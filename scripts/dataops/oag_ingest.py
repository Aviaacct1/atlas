#!/usr/bin/env python3
"""
Avia Solutions - OAG schedules ingest to DuckDB.
================================================
Loads one OAG region/airport schedules file (.xlsx) into a local DuckDB OAG store
(C:\\Avia\\oag.duckdb, table 'oag'), so the connection builder can query per market
instead of loading the whole world into memory. Idempotent per (week, region).

  py -3.12 oag_ingest.py --xlsx "<region file>"            # week+region inferred
  py -3.12 oag_ingest.py --xlsx "<file>" --week 2025-05-26 --region Europe
Use ingest_all_oag.py to load a whole folder in one go.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
import argparse, os, sys, subprocess, datetime, re

def _need(mod, pip=None):
    try: return __import__(mod)
    except ImportError:
        print(f"installing {pip or mod} ...", flush=True)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", pip or mod])
        return __import__(mod)

duckdb = _need("duckdb")
pd = _need("pandas")
_need("python_calamine", "python-calamine")

COLMAP = {
 "carrier":["Carrier Code","Carrier1"], "carrier_name":["Carrier Name","Carrier1Name"],
 "flight_no":["Flight No","FlightNo1"], "carrier2":["Carrier 2","Carrier2"],
 "dep_airport":["Dep Airport Code","DepAirport"], "dep_terminal":["Dep Terminal","DepTerminal"],
 "dep_city":["Dep City Code","DepCity"], "dep_country":["Dep IATA Country Code","DepIATACtry"],
 "dep_region":["Dep Region Code","DepReg"],
 "arr_airport":["Arr Airport Code","ArrAirport"], "arr_terminal":["Arr Terminal","ArrTerminal"],
 "arr_city":["Arr City Code","ArrCity"], "arr_country":["Arr IATA Country Code","ArrIATACtry"],
 "arr_region":["Arr Region Code","ArrReg"],
 "local_dep_time":["Local Dep Time","LocalDepTime"], "local_arr_time":["Local Arr Time","LocalArrTime"],
 "local_arr_day":["Local Arr Day","LocalArrday"], "days_of_op":["Local Days Of Op","LocaldaysOfOp"],
 "arr_days_of_op":["Local Days Of Op Arr","ArrdaysOfOp"], "service_type":["Service Type","Service"],
 "seats":["Seats"], "first_seats":["First Seats","FstSeats"], "business_seats":["Business Seats","BusSeats"],
 "economy_seats":["Economy Seats","EcoSeats"], "eff_from":["Effective From","EffFrom"],
 "eff_to":["Effective To","EffTo"], "elapsed_time":["Elapsed Time","ElapsedTime"],
 "flying_time":["Flying Time","FlyingTime"], "ground_time":["Ground Time","GroundTime"],
 "stops":["No of Stops","Stops"], "aircraft_code":["Specific Aircraft Code"],
 "aircraft_name":["Specific Aircraft Name"], "alliance":["Carrier Alliance"],
 "carrier_category":["Mainline/Low Cost"], "dup_marker":["Dup Marker"], "pass_class":["Pass Class"],
 "gcd_km":["GCD (km)"], "gcd_mi":["GCD (m)"], "asks":["ASKs"], "frequency":["Frequency"],
 "seats_total":["Seats (Total)"],
}
COLS = list(COLMAP) + ["week", "region", "year", "source_file"]
REGIONS = ["Europe","North America","Latin America","Africa","Middle East","Asia","Southwest Pacific"]
MONTHS = {m:i+1 for i,m in enumerate(
    ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"])}


def infer(fname):
    """Infer (week ISO, region) from names like 'Europe wc 27May19.xlsx'."""
    base = os.path.basename(fname)
    region = next((r for r in REGIONS if r.lower() in base.lower()), None)
    if region is None:                       # filename typo aliases seen in the Data Store
        _alias = {"pacifc": "Southwest Pacific", "pacfic": "Southwest Pacific",
                  "latam": "Latin America", "mid east": "Middle East"}
        for k, v in _alias.items():
            if k in base.lower():
                region = v; break
    week = None
    # split-month exports ('Asia 01Aug to 15Aug 2018', 'Asia 16Augto31Aug2018') - files
    # OAG's row limit forced into two halves. Keyed YYYY-MMpDD so the halves coexist.
    # MUST run before the weekly pattern, which mis-reads '...to31Aug2018' as a week.
    ms = re.search(r'(\d{1,2})\s*([A-Za-z]{3})[a-z]*\s*to\s*(\d{1,2})\s*([A-Za-z]{3})?[a-z]*\s*(20\d{2})', base, re.IGNORECASE)
    if ms and ms.group(2).lower() in MONTHS:
        week = f"{ms.group(5)}-{MONTHS[ms.group(2).lower()]:02d}p{int(ms.group(1)):02d}"
        return week, region
    m = re.search(r'(\d{1,2})\s*([A-Za-z]{3})[a-z]*\s*(\d{2})(?!\d)', base)   # 27May19
    if m and m.group(2).lower() in MONTHS:
        week = f"{2000+int(m.group(3)):04d}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    if not week:
        m2 = re.search(r'(20\d{2})[-_ ]?(\d{2})[-_ ]?(\d{2})', base)           # 2019-05-27
        if m2:
            week = f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)}"
    if not week:                                                       # 'Europe Jan 2015.xlsx' (monthly, full-year pull)
        m3 = re.search(r'\b([A-Za-z]{3})[a-z]*\s+(20\d{2})\s*\.', base)
        if m3 and m3.group(1).lower() in MONTHS:
            week = f"{m3.group(2)}-{MONTHS[m3.group(1).lower()]:02d}"
    if not week:                                                       # 'Africa H1 2016.xlsx' (half-year)
        m4 = re.search(r'\b(H[12])\s+(20\d{2})\s*\.', base, re.IGNORECASE)
        if m4:
            week = f"{m4.group(2)}-{m4.group(1).upper()}"
    if not week:                                                       # 'North America 2015.xlsx' (annual)
        m5 = re.search(r'\b(20\d{2})\s*\.', base)
        if m5:
            week = m5.group(1)
    return week, region


def _read_all_sheets(xlsx):
    """Read EVERY data sheet and concatenate. OAG exports spill past Excel's
    1,048,576-row sheet cap onto continuation sheets (usually headerless);
    reading only the first sheet silently drops the tail (found 21 Jul 2026:
    NA/SWP/LatAm annual and half-year files all capped)."""
    xl = pd.ExcelFile(xlsx, engine="calamine")
    frames, cols_ref = [], None
    for sn in xl.sheet_names:
        if sn.lower().startswith("note"):
            continue
        raw = pd.read_excel(xl, sheet_name=sn, header=None, dtype=str)
        if raw.empty or raw.shape[1] < 5:
            continue
        row0 = [str(v).strip() for v in raw.iloc[0].tolist()]
        if any(h in row0 for h in ("Dep Airport Code", "DepAirport")):
            cols_ref = row0
            body = raw.iloc[1:].copy()
            body.columns = cols_ref
            frames.append(body)
        elif cols_ref is not None and raw.shape[1] == len(cols_ref):
            raw.columns = cols_ref                      # headerless continuation sheet
            frames.append(raw)
    if not frames:
        raise ValueError("no data sheets recognised")
    df = pd.concat(frames, ignore_index=True)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def ingest_one(xlsx, week, region, db):
    year = int(week[:4])
    df = _read_all_sheets(xlsx)
    clean = pd.DataFrame()
    for tgt, srcs in COLMAP.items():
        col = next((s for s in srcs if s in df.columns), None)
        clean[tgt] = df[col] if col else None
    clean["week"] = week; clean["region"] = region; clean["year"] = year
    clean["source_file"] = os.path.basename(xlsx)
    clean = clean[COLS]
    con = duckdb.connect(db)
    con.register("clean", clean)
    con.execute("CREATE TABLE IF NOT EXISTS oag AS SELECT * FROM clean WHERE 0=1")
    con.execute("DELETE FROM oag WHERE week=? AND region=?", [week, region])
    con.execute("INSERT INTO oag SELECT * FROM clean")
    n = con.execute("SELECT count(*) FROM oag WHERE week=? AND region=?", [week, region]).fetchone()[0]
    tot = con.execute("SELECT count(*) FROM oag").fetchone()[0]
    con.close()
    return n, tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--week"); ap.add_argument("--region")
    ap.add_argument("--db", default=_paths.OAG_DB)
    a = ap.parse_args()
    if not os.path.exists(a.xlsx):
        print("ERROR: file not found:", a.xlsx); sys.exit(1)
    iw, ir = infer(a.xlsx)
    week, region = a.week or iw, a.region or ir
    if not week or not region:
        print(f"ERROR: could not infer week/region; pass --week and --region (got week={week}, region={region})")
        sys.exit(1)
    t0 = datetime.datetime.now()
    print(f"Reading {os.path.basename(a.xlsx)}  week={week} region={region}  ({os.path.getsize(a.xlsx)/1e6:.0f}MB)...", flush=True)
    n, tot = ingest_one(a.xlsx, week, region, a.db)
    print(f"DONE in {(datetime.datetime.now()-t0).total_seconds():.0f}s. Loaded {n:,} flights for {region} {week}. Store holds {tot:,}.", flush=True)


if __name__ == "__main__":
    main()

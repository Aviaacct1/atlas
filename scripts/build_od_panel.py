"""Build the true-O&D-by-airport-year panel from Sabre (endpoints only, transfers excluded) and write
data/od_panel.json. HEAVY: run on the box with the 16GB Sabre DB, not in the sandbox (a single airport
query alone is ~39s). Author: Avia Solutions."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from avia_forecast.paths import SABRE_DB
from avia_forecast.io_safe import dump_atomic

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    import duckdb
    con = duckdb.connect(SABRE_DB, read_only=True)
    rows = con.execute("""
        SELECT ep AS iata, year, SUM(passengers) AS od FROM (
            SELECT origin_airport AS ep, year, passengers FROM sabre
            UNION ALL
            SELECT destination_airport AS ep, year, passengers FROM sabre
        ) WHERE ep IS NOT NULL GROUP BY ep, year""").fetchall()
    con.close()
    panel = {}
    for iata, year, od in rows:
        if iata and year and od:
            panel.setdefault(iata, {})[str(int(year))] = float(od)
    out = os.path.join(REPO, "data", "od_panel.json")
    dump_atomic(panel, out, indent=0)
    print(f"od_panel.json: {len(panel)} airports -> {out}")


if __name__ == "__main__":
    main()

"""Per-airport CONNECTING throughput measured directly from Sabre itinerary legs. Author: Avia Solutions.

Connecting passengers at an airport = those transferring THROUGH it (it appears as connecting_airport1/2/3
on the O&D itinerary), summed both directions. This is the leg-MEASURED connecting for the identity build,
replacing the ACI-minus-O&D residual as the primary source; the residual stays as the fallback for airports
Sabre does not cover. Writes data/connecting_sabre_<year>.json = {IATA: connecting_pax}.

    python scripts/build_connecting_sabre.py [--year 2024]
"""
import os
import sys
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from avia_forecast.io_safe import dump_atomic
from avia_forecast.paths import SABRE_DB

REPO_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def run(year=2024):
    import duckdb
    con = duckdb.connect(SABRE_DB, read_only=True)
    q = f"""
    select ap, sum(pax) conx from (
      select connecting_airport1 ap, cast(passengers as double) pax from sabre where year={year} and connecting_airport1 is not null and connecting_airport1<>''
      union all
      select connecting_airport2, cast(passengers as double) from sabre where year={year} and connecting_airport2 is not null and connecting_airport2<>''
      union all
      select connecting_airport3, cast(passengers as double) from sabre where year={year} and connecting_airport3 is not null and connecting_airport3<>''
    ) group by ap
    """
    rows = con.execute(q).fetchall()
    con.close()
    out = {ap: round(v) for ap, v in rows if ap and v}
    dump_atomic(out, os.path.join(REPO_DATA, f"connecting_sabre_{year}.json"))
    print(f"connecting_sabre_{year}.json: {len(out)} airports (leg-measured connecting from Sabre)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    run(ap.parse_args().year)

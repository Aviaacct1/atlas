"""ingest/oag_store - the OAG store reading conventions, in one place.
Author: Avia Solutions.

Lifted from scripts/backtest_seats_anchor.py so that the backtests and the capacity
work read the store the same way. The backtest script should import from here rather
than keep its own copy; two implementations of these rules will drift, and the
symptom of drift is a number that looks plausible.

What the store is, established by reading it on 3 August 2026:

  * ONE ROW PER OPERATED FLIGHT. NZ1 LHR-LAX appears 30 times in the 2019-06 file,
    once per operating day, each row carrying frequency 1 and the full season window
    2019-03-31 to 2019-10-20. eff_from and eff_to are the SEASON window and must
    never be used to place a row on a date.

  * `week` is the PERIOD KEY of the file the row came from: YYYY-MM (monthly),
    YYYY-MMpNN (split month), YYYY-MM-DD (single week), YYYY-Hn and YYYY (legacy
    slices). Several tilings of the same year can coexist, so exactly one tiling per
    region-year must be summed or the year is counted twice.

  * `region` is the region file. A flight spanning two regions is listed in BOTH:
    NZ1 sits in North America and in Europe, 30 rows in each. Taking each airport's
    HOME region file (where its row count is largest) removes that duplication and
    keeps all of its flights, because the home file covers the airport itself.

  * `dup_marker` is NOT a codeshare marker and must not be filtered on. BA57 LHR-JNB,
    operated by BA with no operating-carrier override, carries 'D', and 'D' is 84.7%
    of Heathrow's 2019 rows.

  * Numeric columns (seats, frequency, seats_total) are VARCHAR. Cast, always.

  * local_dep_time and local_arr_time are HHMM with NO leading zero: "700" is 07:00.

Validation anchor, Heathrow 2019, home region only, service_type J:

    movements   477,954 against Heathrow's published "over 470,000"
    seats       100.4m, which against the published 80.9m passengers implies an actual
                load factor of 0.806
    passengers  82.3m on the assumptions-book load factor of 0.82, so 1.7% high

The seats extraction is therefore right and the 1.7% is the book load factor running
1.4 points above Heathrow's actual. The peak hour SHARE is unaffected, because the load
factor cancels between the peak and the annual total, so the fitted elasticity does not
depend on it. Where an airport's own load factor matters, it should be read rather than
defaulted. Sources: Heathrow media centre, "Heathrow reports outstanding end to 2019",
and the daily figure cross-check with John Carter, 3 August 2026 (70 to 80 ATM/hr across
an 05:00 to 23:00 day gives 630 to 720 departures; the store gives 678 for June 2019,
against 934 read raw across all region files).
"""
from __future__ import annotations
from functools import lru_cache

WEEKLY_KEY_PATTERN = "20__-__-__"          # YYYY-MM-DD, a single-week pull


def preferred_tilings(con, table: str = "oag") -> dict:
    """{(region, year): {week keys to sum}} - exactly one tiling per region-year.

    Full monthly set first (split-month parts count where both halves are present),
    else both halves, else the annual key. Single-week keys are excluded here: they
    are a different basis and are handled separately.

    A split month's parts are read as a PARTITION, using part_spans. Asia 2025 carries
    2025-01p01, 2025-01p16 and 2025-01p23 for January; every part is kept and each one
    ends where the next begins.
    """
    pref: dict = {}
    q = f"""SELECT region, CAST(substr(week, 1, 4) AS INT) AS yr, list(DISTINCT week)
            FROM "{table}" WHERE week NOT LIKE '{WEEKLY_KEY_PATTERN}' GROUP BY 1, 2"""
    for region, yr, keys in con.execute(q).fetchall():
        ks = set(keys)
        monthly = {k for k in ks if len(k) == 7 and k[4] == "-" and k[5:].isdigit()}
        parts: dict = {}
        for k in ks:
            if len(k) > 7 and k[7] == "p":
                parts.setdefault(k[5:7], set()).add(k)
        month_cov = {k[5:7] for k in monthly} | {mm for mm, s in parts.items() if len(s) >= 2}
        halves = {k for k in ks if k.endswith("H1") or k.endswith("H2")}
        annual = {k for k in ks if len(k) == 4}
        if len(month_cov) == 12:
            part_keys = set().union(*[s for mm, s in parts.items() if len(s) >= 2]) if parts else set()
            pref[(region, int(yr))] = monthly | part_keys
        elif len({k[-2:] for k in halves}) == 2:
            pref[(region, int(yr))] = halves
        elif annual:
            pref[(region, int(yr))] = annual
    return pref


def part_spans(keys) -> dict:
    """{key: (first_date, last_date)} for a set of period keys, read as a partition.

    period_span reads one key in isolation and has to guess where a split-month part
    ends. It assumes two parts, so 2025-01p16 comes back as 16 to 31 January. Asia
    2025 has THREE parts for January: p01, p16 and p23. Read in isolation, p16 runs
    to the 31st and swallows p23, so 23 to 31 January gets counted twice.

    What that cost, before it was found on 4 August 2026 by comparing our panel with
    one Jess Rowden built independently: Asian annual seats 2.5% high, which is nine
    duplicated days out of 365 and small enough to pass for noise, and the 30th
    busiest hour 7.4% high at the median and 24% high at the worst, because the
    duplicated days go straight to the top of the ranking. Tokyo Haneda read 33% above
    Jess's figure against agreement inside 0.1% on the annual.

    A first attempt at the fix dropped p23 as redundant. That was wrong in the same
    way the original was wrong: plausible, and it quietly discarded 2.5% of Asian
    traffic. The parts are not two-with-a-duplicate, they are three-that-partition.
    So each part ends the day before the next part begins, and the last part ends with
    the month. Nothing is dropped and nothing is doubled.
    """
    import calendar
    import datetime
    out, months = {}, {}
    for k in keys:
        if len(k) > 7 and k[7] == "p":
            months.setdefault(k[:7], []).append(k)
        else:
            span = period_span(k)
            if span:
                out[k] = span
    for ym, ks in months.items():
        try:
            y, mth = int(ym[:4]), int(ym[5:7])
        except ValueError:
            continue
        last = calendar.monthrange(y, mth)[1]
        starts = sorted((int(k[8:] or 1), k) for k in ks)
        for i, (start, k) in enumerate(starts):
            end = (starts[i + 1][0] - 1) if i + 1 < len(starts) else last
            end = max(start, min(end, last))
            out[k] = (datetime.date(y, mth, start).isoformat(),
                      datetime.date(y, mth, end).isoformat())
    return out


def home_regions(con, table: str = "oag", airports=None) -> dict:
    """{iata: region} - the region file holding most of an airport's departures.

    That file also holds the rest of them, so reading only the home file removes the
    cross-region duplication without losing any flight. Pass `airports` to restrict
    the scan: this table is large, and the unrestricted group-by is the slowest step
    in the panel build.
    """
    where = "dep_airport IS NOT NULL"
    if airports:
        inlist = ",".join("'" + a.replace("'", "''") + "'" for a in sorted(set(airports)))
        where += f" AND dep_airport IN ({inlist})"
    q = f"""SELECT dep_airport, region, COUNT(*) AS n FROM "{table}"
            WHERE {where} GROUP BY 1, 2"""
    best: dict = {}
    for iata, region, n in con.execute(q).fetchall():
        cur = best.get(iata)
        if cur is None or n > cur[1]:
            best[iata] = (region, n)
    return {k: v[0] for k, v in best.items()}


def period_span(week: str):
    """(first_date, last_date) covered by a period key, or None where it cannot be
    read. Dates are ISO strings so they can go straight into SQL."""
    import calendar
    if not week:
        return None
    if len(week) == 4 and week.isdigit():                        # YYYY
        return f"{week}-01-01", f"{week}-12-31"
    if week.endswith("H1"):
        return f"{week[:4]}-01-01", f"{week[:4]}-06-30"
    if week.endswith("H2"):
        return f"{week[:4]}-07-01", f"{week[:4]}-12-31"
    if len(week) == 7 and week[4] == "-" and week[5:].isdigit():  # YYYY-MM
        y, mth = int(week[:4]), int(week[5:7])
        return f"{week}-01", f"{week}-{calendar.monthrange(y, mth)[1]:02d}"
    if len(week) > 7 and week[7] == "p":                          # YYYY-MMpNN
        y, mth = int(week[:4]), int(week[5:7])
        start = int(week[8:] or 1)
        last = calendar.monthrange(y, mth)[1]
        end = last if start > 15 else 15
        return f"{week[:7]}-{start:02d}", f"{week[:7]}-{end:02d}"
    if len(week) == 10 and week[4] == "-" and week[7] == "-":     # YYYY-MM-DD, one week
        import datetime
        d0 = datetime.date.fromisoformat(week)
        return week, (d0 + datetime.timedelta(days=6)).isoformat()
    return None


def hhmm_sql(col: str, alias: str = "") -> str:
    """SQL fragment giving the clock hour from an HHMM column with no leading zero.
    "700" is 07:00, so the value is left-padded before the hour is taken."""
    q = f'{alias + "." if alias else ""}"{col}"'
    return f"TRY_CAST(substr(lpad(replace(CAST({q} AS VARCHAR), ':', ''), 4, '0'), 1, 2) AS INTEGER)"


def minutes_sql(col: str, alias: str = "") -> str:
    """SQL fragment giving minutes since midnight from the same HHMM column.

    Needed for the rolling-hour convention, which cannot be built from the clock hour
    alone. Same left-padding rule as hhmm_sql: "700" is 07:00, so 420 minutes.
    """
    q = f'{alias + "." if alias else ""}"{col}"'
    p = f"lpad(replace(CAST({q} AS VARCHAR), ':', ''), 4, '0')"
    return (f"(TRY_CAST(substr({p}, 1, 2) AS INTEGER) * 60 "
            f"+ TRY_CAST(substr({p}, 3, 2) AS INTEGER))")


@lru_cache(maxsize=1)
def _cached_marker():
    return True

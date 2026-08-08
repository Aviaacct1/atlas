"""Pull the Output sheet out of every per-airport peak hour workbook.

Jess Rowden's benchmark set is one workbook per airport, circa 25MB each, because each
carries the full year of dated OAG rows. The Output sheet inside is about 20KB. This
reads ONLY that sheet, straight out of the zip, so 2.4GB on the drive costs seconds and
never has to move.

What it recovers, and why it matters: the Output sheet holds the annual total on row 5,
the ABSOLUTE PEAK hour on row 7, and the TRUE 30th BUSIEST hour on row 12. The summary
workbook links only to row 7, so the 30th busiest has been calculated for every airport
in the set and never carried across. Row 12 is the figure the industry designs to, and
it is the one Avia needs for the capacity work.

Run it where the files are, not where the code is:

    python scripts/extract_peakhour_outputs.py --folder "<Egnyte>/02 Peak Hour/Benchmarks"

Author: Avia Solutions.
"""
from __future__ import annotations
import argparse, csv, re, sys, zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# Output sheet layout, confirmed from BEG.xlsx, 4 August 2026.
# Blocks of (arrivals, departures, 2-way); row 5 annual, row 7 peak, row 12 30th busiest.
BLOCKS = {"mvt": ("D", "E", "F"), "dom_seats": ("H", "I", "J"),
          "int_seats": ("L", "M", "N"), "seats": ("P", "Q", "R")}
ROWS = {"annual": 5, "peak": 7, "busy30": 12}


def _output_part(z: zipfile.ZipFile) -> str | None:
    wb = z.read("xl/workbook.xml").decode()
    rels = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="([^"]+)"',
                           z.read("xl/_rels/workbook.xml.rels").decode()))
    for name, rid in re.findall(r'<sheet name="([^"]+)"[^>]*r:id="(rId\d+)"', wb):
        if name.strip().lower() == "output":
            t = rels.get(rid, "")
            return "xl/" + t if not t.startswith("/") else t.lstrip("/")
    return None


def read_output(path: Path) -> dict | None:
    """{cell ref: cached value} for the Output sheet, or None if there is not one."""
    with zipfile.ZipFile(path) as z:
        part = _output_part(z)
        if not part or part not in z.namelist():
            return None
        root = ET.fromstring(z.read(part))          # ~20KB, whatever the file weighs
    vals = {}
    for row in root.find(NS + "sheetData").findall(NS + "row"):
        for c in row.findall(NS + "c"):
            v = c.find(NS + "v")
            if v is not None and c.get("t") != "s":
                vals[c.get("r")] = v.text
    return vals


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True, help="folder holding the <IATA>.xlsx files")
    ap.add_argument("--out", default="data/peakhour_benchmark_outputs.csv")
    args = ap.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"not a folder: {folder}", file=sys.stderr)
        return 2

    cols = ["iata"] + [f"{r}_{b}_{s}" for r in ROWS for b in BLOCKS for s in ("arr", "dep", "2way")]
    rows, skipped = [], []
    for f in sorted(folder.glob("*.xlsx")):
        iata = f.stem.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", iata):
            continue                                 # the summary workbook and anything else
        try:
            vals = read_output(f)
        except Exception as e:                       # a locked or part-synced file
            skipped.append((iata, str(e)[:60]))
            continue
        if vals is None:
            skipped.append((iata, "no Output sheet"))
            continue
        rec = {"iata": iata}
        for rname, rnum in ROWS.items():
            for bname, letters in BLOCKS.items():
                for letter, side in zip(letters, ("arr", "dep", "2way")):
                    rec[f"{rname}_{bname}_{side}"] = vals.get(f"{letter}{rnum}")
        rows.append(rec)
        print(f"  {iata}", end="", flush=True)

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, cols); w.writeheader(); w.writerows(rows)
    print(f"\n\n{len(rows)} airports written to {out}")
    if skipped:
        print(f"skipped {len(skipped)}: {skipped[:5]}")
    # the point of the exercise, stated so nobody has to rediscover it
    n = sum(1 for r in rows if r.get("peak_seats_2way") and r.get("busy30_seats_2way"))
    if n:
        gaps = [float(r["peak_seats_2way"]) / float(r["busy30_seats_2way"])
                for r in rows if r.get("peak_seats_2way") and r.get("busy30_seats_2way")
                and float(r["busy30_seats_2way"]) > 0]
        gaps.sort()
        print(f"peak hour runs {(gaps[len(gaps)//2]-1)*100:.0f}% above the 30th busiest "
              f"at the median, across {len(gaps)} airports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

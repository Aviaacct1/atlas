r"""Check a built deck from the outside, as code rather than by eye.
Author: Avia Solutions.

The em dash and the en dash are visually close to a hyphen, so a review by eye finds
neither reliably, and a generated document is exactly where one survives: inside a
template string, a table cell, a placeholder or a chart label rather than in prose.
This opens the file as a zip and reads every XML part, so it sees text a reader of the
slides would not: chart cached values, embedded workbook strings, document properties,
speaker notes.

Checks:
  1  No em dash U+2014 anywhere in any part.
  2  No en dash U+2013 anywhere in any part.
  3  No other typographic substitute that reads as an AI tell: the horizontal bar
     U+2015, the minus sign U+2212 and the non-breaking hyphen U+2011.
  4  Author and last modified by both set to the expected name, never a library name.
  5  Editing language en-GB on every run that declares one, and no run declaring
     another language.
  6  Every slide carries a source line.
  7  Fonts limited to the pair the Observatory decks use.

Exits non-zero on any failure, so it can sit in front of delivery.

Usage:  py -3.12 scripts\check_deck.py "path\to\deck.pptx" [--author "Avia Solutions"]
"""
from __future__ import annotations

import argparse
import re
import sys
import zipfile

BANNED = {
    "—": "em dash",
    "–": "en dash",
    "―": "horizontal bar",
    "−": "minus sign",
    "‑": "non-breaking hyphen",
}
ALLOWED_FONTS = {"Cambria", "Arial", "+mn-lt", "+mj-lt", "Calibri"}
ALLOWED_LANG = {"en-GB"}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--author", default="Avia Solutions")
    ap.add_argument("--require-source-line", action="store_true", default=True)
    args = ap.parse_args(argv)

    fails, warns = [], []
    with zipfile.ZipFile(args.path) as z:
        parts = {n: z.read(n).decode("utf-8", "replace")
                 for n in z.namelist() if n.endswith((".xml", ".rels"))}

        for ch, name in BANNED.items():
            hits = []
            for n, body in parts.items():
                for m in re.finditer(re.escape(ch), body):
                    hits.append((n, body[max(0, m.start() - 45):m.start() + 45]))
            if hits:
                fails.append(f"{len(hits)} {name} characters, first in {hits[0][0]}: "
                             f"...{hits[0][1]}...")
            else:
                print(f"[PASS] no {name}")

        core = parts.get("docProps/core.xml", "")
        author = re.search(r"<dc:creator>([^<]*)</dc:creator>", core)
        lastby = re.search(r"<cp:lastModifiedBy>([^<]*)</cp:lastModifiedBy>", core)
        got = (author.group(1) if author else None, lastby.group(1) if lastby else None)
        if got == (args.author, args.author):
            print(f"[PASS] author and last modified by both {args.author}")
        else:
            fails.append(f"author and last modified by are {got}, expected "
                         f"{args.author} for both")

        langs = set()
        for n, body in parts.items():
            langs |= set(re.findall(r'\slang="([^"]+)"', body))
            langs |= set(re.findall(r'\saltLang="([^"]+)"', body))
        other = sorted(l for l in langs if l not in ALLOWED_LANG)
        if not langs:
            fails.append("no run declares a language, so Word and PowerPoint will "
                         "auto-detect each run and will tag some of it as French")
        elif other:
            fails.append(f"languages other than en-GB present: {other}")
        else:
            print(f"[PASS] every declared language is en-GB ({sorted(langs)})")

        fonts = set()
        for n, body in parts.items():
            if n.startswith("ppt/slides/") or n.startswith("ppt/charts/"):
                fonts |= set(re.findall(r'typeface="([^"]+)"', body))
        odd = sorted(f for f in fonts if f not in ALLOWED_FONTS)
        if odd:
            warns.append(f"fonts outside the Observatory pair: {odd}")
        else:
            print(f"[PASS] fonts limited to {sorted(fonts)}")

        slides = sorted(n for n in parts if re.fullmatch(r"ppt/slides/slide\d+\.xml", n))
        missing = [n for n in slides if "Source:" not in parts[n]]
        # The cover carries the copyright block rather than a source line.
        missing = [n for n in missing if "Copyright Avia Solutions" not in parts[n]]
        if missing:
            fails.append(f"{len(missing)} slides carry no source line: "
                         + ", ".join(m.split('/')[-1] for m in missing))
        else:
            print(f"[PASS] all {len(slides)} slides carry a source line or the "
                  "copyright block")

    for w in warns:
        print(f"[WARN] {w}")
    for f in fails:
        print(f"[FAIL] {f}")
    print(f"\n{'FAIL' if fails else 'PASS'}: {len(fails)} failures, {len(warns)} "
          f"warnings on {args.path}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

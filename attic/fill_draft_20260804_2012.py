"""Fill the blank rows of the Data sheet, on Jess Rowden's basis.

Edits the worksheet XML rather than round-tripping through openpyxl, because the
workbook carries twelve chartsheets that openpyxl does not preserve.

CRITICAL, learned from Excel rejecting the first two attempts: ElementTree must never
serialise the <worksheet> ROOT. The root carries mc:Ignorable="x14ac xr xr2 xr3", and
ElementTree only emits namespace declarations it can see in use, so it silently dropped
xmlns:r, xmlns:xr2 and xmlns:xr3 while leaving mc:Ignorable referring to them. That is
undeclared-prefix XML. LibreOffice and openpyxl both read it happily; Excel rejects the
part outright ("XML error. Line 2, column 0") and replaces the sheet, which takes every
INDEX(Data!...) on the downstream sheets to #REF!.

So: only the <sheetData> fragment is parsed and rewritten, and it is spliced back into
the original file text. Everything outside sheetData stays byte for byte identical.

Author: Avia Solutions.
"""
import csv, json, math, re
import xml.etree.ElementTree as ET

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
# Every prefix the ROOT declares must also be declared on the fragment wrapper, or the
# rows' x14ac:dyDescent attributes are an unbound prefix. They are stripped again on the
# way out, because the real document inherits them from <worksheet>.
NSMAP = {
    "": NS,
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "x14ac": "http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac",
    "xr": "http://schemas.microsoft.com/office/spreadsheetml/2014/revision",
    "xr2": "http://schemas.microsoft.com/office/spreadsheetml/2015/revision2",
    "xr3": "http://schemas.microsoft.com/office/spreadsheetml/2016/revision3",
}
for _p, _u in NSMAP.items():
    ET.register_namespace(_p, _u)
Q = lambda t: f"{{{NS}}}{t}"

SHARED = json.load(open('/tmp/shared.json'))
J = {r['iata']: r for r in csv.DictReader(open('/tmp/jess.csv'))}
O = {r['iata']: r for r in csv.DictReader(open('/tmp/ours.csv'))}


def fit(jkey, okey):
    xs, ys = [], []
    for a, r in J.items():
        if not r[jkey] or a not in O:
            continue
        jv, ov, av = float(r[jkey]), float(O[a][okey] or 0), float(r['ann_mvt_2w'] or 0)
        if jv > 0 and ov > 0 and av > 0:
            xs.append(math.log(av)); ys.append(math.log(jv / ov))
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return my - b * mx, b, len(xs)


A_M, B_M, N_M = fit('ph_mvt_2w', 'p_m2')
A_S, B_S, N_S = fit('bhr_seat_2w', 'p_s2')
print(f"calibration movements ln(J/O) = {A_M:+.4f} {B_M:+.5f}*ln(annual)  n={N_M}")
print(f"calibration seats     ln(J/O) = {A_S:+.4f} {B_S:+.5f}*ln(annual)  n={N_S}")


def uplift(annual, seats=False):
    if not annual or annual <= 0:
        return 1.0
    a, b = (A_S, B_S) if seats else (A_M, B_M)
    return math.exp(a + b * math.log(annual))


# column -> (ours key, is_seats_metric, is_peak). Value columns only: the ratio columns
# already carry IFERROR formulas and are left for Excel to recalculate.
COLS = {
 'C': ('a_m2', 0, 0), 'D': ('a_mA', 0, 0), 'E': ('a_mD', 0, 0),
 'F': ('p_m2', 0, 1), 'G': ('p_mA', 0, 1), 'H': ('p_mD', 0, 1),
 'L': ('a_s2', 1, 0), 'M': ('a_sA', 1, 0), 'N': ('a_sD', 1, 0),
 'O': ('p_s2', 1, 1), 'P': ('p_sA', 1, 1), 'Q': ('p_sD', 1, 1),
 'U': ('a_d2', 1, 0), 'V': ('a_dA', 1, 0), 'W': ('a_dD', 1, 0),
 'X': ('p_d2', 1, 1), 'Y': ('p_dA', 1, 1), 'Z': ('p_dD', 1, 1),
 'AD': ('a_i2', 1, 0), 'AE': ('a_iA', 1, 0), 'AF': ('a_iD', 1, 0),
 'AG': ('p_i2', 1, 1), 'AH': ('p_iA', 1, 1), 'AI': ('p_iD', 1, 1),
}
RATIO = ['I', 'J', 'K', 'R', 'S', 'T', 'AA', 'AB', 'AC', 'AJ', 'AK', 'AL']


def cidx(letter):
    n = 0
    for ch in letter:
        n = n * 26 + (ord(ch) - 64)
    return n


PATH = 'x/xl/worksheets/sheet1.xml'
raw = open(PATH, encoding='utf-8', newline='').read()
root_tag_before = re.search(r'<worksheet[^>]*>', raw).group(0)

m = re.search(r'<sheetData>.*</sheetData>', raw, re.S)
_decl = " ".join((f'xmlns="{u}"' if not p else f'xmlns:{p}="{u}"') for p, u in NSMAP.items())
frag = ET.fromstring(f'<sheetData {_decl}>' + m.group(0)[len('<sheetData>'):])

filled = skipped = cleared = 0
for rowel in frag.findall(Q('row')):
    rn = int(rowel.get('r'))
    if rn < 5:
        continue
    cells = {c.get('r'): c for c in rowel.findall(Q('c'))}
    ac = cells.get(f'A{rn}')
    if ac is None:
        continue
    v = ac.find(Q('v'))
    if v is None:
        continue
    iata = SHARED[int(v.text)] if ac.get('t') == 's' else v.text
    if not iata or iata not in O:
        continue
    c_cell = cells.get(f'C{rn}')
    if c_cell is not None and c_cell.find(Q('v')) is not None:
        skipped += 1
        continue                                  # already done; leave it alone

    o = O[iata]
    ann_m = float(o['a_m2'] or 0)
    for letter, (key, is_seat, is_peak) in COLS.items():
        rawv = o.get(key)
        if rawv in (None, '', 'None'):
            continue
        val = float(rawv)
        if is_peak:
            val *= uplift(ann_m, seats=bool(is_seat))
        ref = f'{letter}{rn}'
        c = cells.get(ref)
        if c is None:
            c = ET.SubElement(rowel, Q('c')); c.set('r', ref); cells[ref] = c
        for ch in list(c):
            c.remove(ch)
        c.attrib.pop('t', None)
        ET.SubElement(c, Q('v')).text = str(round(val))
    # the ratio formulas still cache "x" from when the row was blank; drop the cache so
    # any application must recalculate rather than show the stale value
    for letter in RATIO:
        c = cells.get(f'{letter}{rn}')
        if c is None or c.find(Q('f')) is None:
            continue
        for ve in c.findall(Q('v')):
            c.remove(ve)
        c.attrib.pop('t', None)
        cleared += 1
    rowel[:] = sorted(rowel, key=lambda c: cidx(re.match(r'([A-Z]+)', c.get('r')).group(1)))
    filled += 1

print(f"filled {filled} rows, left {skipped} of Jess's rows untouched, "
      f"cleared {cleared} stale ratio caches")

out = ET.tostring(frag, encoding='unicode')
# strip the declarations off the sheetData tag only; they are inherited from <worksheet>
_open = out[:out.index('>') + 1]
_clean = re.sub(r'\s+xmlns(:\w+)?="[^"]*"', '', _open)
out = _clean + out[out.index('>') + 1:]
raw = raw[:m.start()] + out + raw[m.end():]
open(PATH, 'w', encoding='utf-8', newline='').write(raw)

# The check that would have caught the fault: the root must be untouched.
after = open(PATH, encoding='utf-8', newline='').read()
root_tag_after = re.search(r'<worksheet[^>]*>', after).group(0)
assert root_tag_after == root_tag_before, "worksheet root tag was altered"
assert after.startswith('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
decl = re.findall(r'xmlns:(\w+)=', root_tag_after)
for p in re.search(r'mc:Ignorable="([^"]+)"', root_tag_after).group(1).split():
    assert p in decl, f"mc:Ignorable references undeclared prefix {p}"
print("root element and namespace declarations preserved")

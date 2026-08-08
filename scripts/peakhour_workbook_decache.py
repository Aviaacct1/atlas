"""Drop every cached formula result on the data sheets, so nothing stale can be plotted.

The charts do not read the Data sheet. They read four intermediate sheets that pull
from it with INDEX/MATCH. Clearing the cached values on Data alone left 124 cells on
'PH Movements' still holding the text "x" from when those airports were blank, and
Excel plots text as ZERO. That produced a line of points sitting on 0.00% along the
bottom of every chart, and a power trendline cannot be fitted through a zero, so Excel
dropped the trendline and its equation and R-squared label on all twelve.

Nothing here is recalculated by hand. Every cached result is removed from every formula
cell on the five data sheets, so Excel has no stale value to fall back on and must
compute the lot on open, which fullCalcOnLoad already asks it to do.

Author: Avia Solutions.
"""
import re

SHEETS = [f'x/xl/worksheets/sheet{i}.xml' for i in range(1, 6)]
CELL = re.compile(r'<c\b[^>]*/>|<c\b[^>]*>.*?</c>', re.S)

for path in SHEETS:
    s = open(path, encoding='utf-8', newline='').read()
    root_before = re.search(r'<worksheet[^>]*>', s).group(0)
    n = [0]

    def strip(m):
        cell = m.group(0)
        if '<f' not in cell:
            return cell                       # a literal value, leave it alone
        new = re.sub(r'<v>.*?</v>', '', cell, flags=re.S)
        # a cached type of str or e belongs to the cached value, not the formula
        new = re.sub(r'\s+t="(str|e)"', '', new)
        if new != cell:
            n[0] += 1
        return new

    s = CELL.sub(strip, s)
    assert re.search(r'<worksheet[^>]*>', s).group(0) == root_before, 'root altered'
    open(path, 'w', encoding='utf-8', newline='').write(s)
    print(f'{path.split("/")[-1]}: cleared {n[0]} cached formula results')

# nothing may remain that Excel could plot as a zero
for path in SHEETS:
    s = open(path, encoding='utf-8').read()
    for m in CELL.finditer(s):
        c = m.group(0)
        if '<f' in c and '<v>' in c:
            raise AssertionError(f'{path}: cached value survived in {c[:60]}')
print('no cached formula results remain on any data sheet')

"""Hide only the rows a power trendline cannot fit, and show everything else.

Jess's file carried a saved filter listing specific values. It looked like a leftover
view. It was not: it was load-bearing. Excel refuses to fit a POWER trendline if any
plotted point has a zero or negative value, and drops the trendline together with its
equation and R-squared label. Dubai has no domestic traffic, so its domestic seats are
zero; there are 8 such zeros and 24 blanks on the domestic sheet and 18 zeros on the
international one. Clearing the filter outright put them back into the plotted range
and killed the trendlines.

Clearing it was still right in one respect: the old filter also hid every airport Avia
added, so the charts would have refitted over the original 223 points while looking
current. The answer is neither state. Hide exactly the rows that cannot be plotted and
show all the rest, which is 434 points where the data allows and circa 400 where it
does not.

The criterion is written as a real greaterThan filter rather than a list of values, so
it keeps working when the data changes. That is the fault in the original.

Author: Avia Solutions.
"""
import csv, json, re

# chart source sheet -> the Data columns its three charts plot (annual x, then peak y)
SHEETS = {
    'x/xl/worksheets/sheet2.xml': ('PH Movements',        ['C', 'D', 'E'], ['F', 'G', 'H']),
    'x/xl/worksheets/sheet3.xml': ('BHR Seats - Total',   ['L', 'M', 'N'], ['O', 'P', 'Q']),
    'x/xl/worksheets/sheet4.xml': ('BHR Seats - Domestic', ['U', 'V', 'W'], ['X', 'Y', 'Z']),
    'x/xl/worksheets/sheet5.xml': ('BHR Seats - International', ['AD', 'AE', 'AF'], ['AG', 'AH', 'AI']),
}
FINAL = json.load(open('/tmp/final_values.json'))
J = {r['iata']: r for r in csv.DictReader(open('/tmp/jess.csv'))}

# the sheets carry the airports in the same row order as Data
order = [a for a in (r['iata'] for r in csv.DictReader(open('/tmp/jess.csv')))]

for path, (name, xcols, ycols) in SHEETS.items():
    plottable = set()
    for i, iata in enumerate(order):
        row = 5 + i
        v = FINAL.get(iata, {})
        vals = [v.get(c) for c in xcols + ycols]
        if all(x is not None and x > 0 for x in vals) and J[iata]['include'] == 'Include':
            plottable.add(row)
    s = open(path, encoding='utf-8', newline='').read()
    root_before = re.search(r'<worksheet[^>]*>', s).group(0)

    # clear whatever visibility state was saved before deciding afresh, or a row that
    # was already hidden ends up with two hidden attributes and the part is malformed
    s = re.sub(r'(<row\b[^>]*?)\s+hidden="[01]"', r'\1', s)
    counter = {'n': 0}
    def mark(m):
        tag, rn = m.group(0), int(m.group(1))
        if rn < 5 or rn in plottable:
            return tag
        counter['n'] += 1
        close = '/>' if tag.endswith('/>') else '>'
        return tag[:-len(close)] + ' hidden="1"' + close
    s = re.sub(r'<row r="(\d+)"[^>]*?/?>', mark, s)
    hidden = counter['n']
    assert 'hidden="1" hidden' not in s and s.count('hidden="1" hidden="1"') == 0

    # a real criterion, not a list of values: this one survives new data
    col = 2                                   # column C on the chart source sheet
    filt = (f'<autoFilter ref="A4:L446"><filterColumn colId="{col}">'
            f'<customFilters><customFilter operator="greaterThan" val="0"/></customFilters>'
            f'</filterColumn></autoFilter>')
    s = re.sub(r'<autoFilter[^>]*/>|<autoFilter.*?</autoFilter>', filt, s, flags=re.S)

    assert re.search(r'<worksheet[^>]*>', s).group(0) == root_before, 'root altered'
    open(path, 'w', encoding='utf-8', newline='').write(s)
    print(f'{name:26} plottable {len(plottable):>3}  hidden {hidden:>3}')

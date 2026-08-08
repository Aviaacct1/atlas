"""Clear the saved AutoFilters and hidden rows on the data sheets.

Jess's file carries a filter on each data sheet that lists SPECIFIC VALUES to show
(<filter val="103,696"/> and so on), not a criterion. Any row whose value is not in
that saved list is hidden, so the 211 airports Avia added would be filtered out. The
charts are set to plot visible cells only (plotVisOnly=1), so they would have gone on
showing the original 223 points, and the power trendline and its R-squared would have
recomputed over the OLD sample while looking entirely up to date.

That is the worst kind of wrong: a chart that silently answers a different question.

So the filters and the hidden flags are cleared and the filter buttons left in place.
Anyone who wants the old view can re-apply one. Edits are done on the raw text, never
through ElementTree, so the worksheet root elements stay byte-identical.

Author: Avia Solutions.
"""
import re, glob

FILTERED = ['x/xl/worksheets/sheet1.xml', 'x/xl/worksheets/sheet2.xml',
            'x/xl/worksheets/sheet3.xml', 'x/xl/worksheets/sheet4.xml',
            'x/xl/worksheets/sheet5.xml']

for p in FILTERED:
    s = open(p, encoding='utf-8', newline='').read()
    root_before = re.search(r'<worksheet[^>]*>', s).group(0)
    n_cols = len(re.findall(r'<filterColumn', s))
    # keep <autoFilter ref="..."> so the buttons remain, drop the saved criteria
    s = re.sub(r'(<autoFilter\b[^>]*>).*?(</autoFilter>)', r'\1\2', s, flags=re.S)
    s = re.sub(r'<autoFilter\b([^>]*?)></autoFilter>', r'<autoFilter\1/>', s)
    n_hidden = len(re.findall(r'\shidden="1"', s))
    s = re.sub(r'(<row\b[^>]*?)\s+hidden="1"', r'\1', s)
    # customHeight/ht left alone; only visibility is being reset
    assert re.search(r'<worksheet[^>]*>', s).group(0) == root_before, "root altered"
    open(p, 'w', encoding='utf-8', newline='').write(s)
    print(f'{p.split("/")[-1]}: cleared {n_cols} filter column(s), unhid {n_hidden} rows')

for p in FILTERED:
    s = open(p, encoding='utf-8').read()
    assert '<filterColumn' not in s and 'hidden="1"' not in s, f'{p} still filtered'
print('all data sheets fully visible')

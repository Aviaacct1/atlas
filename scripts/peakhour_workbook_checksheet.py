import csv, math, re, json
NS="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
J={r['iata']:r for r in csv.DictReader(open('/tmp/jess.csv'))}
O={r['iata']:r for r in csv.DictReader(open('/tmp/ours.csv'))}
A_M,B_M=1.0739,-0.08367; A_S,B_S=1.0619,-0.08157
def up(a,seat=False):
    if not a or a<=0: return 1.0
    x,y=(A_S,B_S) if seat else (A_M,B_M)
    return math.exp(x+y*math.log(a))

esc=lambda s: (str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;'))
def col(n):
    s=''
    while n: n,r=divmod(n-1,26); s=chr(65+r)+s
    return s
rows=[]
def add(r,vals):
    cs=[]
    for i,v in enumerate(vals,1):
        if v is None or v=='': continue
        ref=f'{col(i)}{r}'
        if isinstance(v,(int,float)):
            cs.append(f'<c r="{ref}"><v>{v}</v></c>')
        else:
            cs.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{esc(v)}</t></is></c>')
    rows.append(f'<row r="{r}">'+''.join(cs)+'</row>')

NOTE=[
 "Jess Rowden - 2025 Peak Hour and 30th BHR. Completed by Avia Solutions, 4 August 2026.",
 "This is Jess\'s analysis. Avia has filled the airports that were still blank and checked the ones that were not. Nothing of hers has been altered.",
 "",
 "WHAT WAS ADDED",
 "231 airports were already complete and are UNCHANGED. The 211 blank airports were filled from the Avia OAG store, 2025, service type J, arrivals and departures read as one combined flow, each airport taken from its home region file only so a flight spanning two regions is not counted twice.",
 "",
 "WHICH BASIS THE FILL IS ON, and why it matters",
 "The filled figures are on a CLOCK HOUR basis, to match what the existing 231 are believed to be. That belief is an inference and worth confirming: it rests on the per-airport Output sheets following the long-standing Avia busy-hour format, which in the older files on Egnyte (Lima 2018, Bologna, the India work) ranks clock hours, recorded as e.g. 06:00-06:59 against a date.",
 "Avia\'s own default for new work is a 60-minute window rolling on a 5-minute step, which finds a slightly higher peak than a fixed clock hour. This file is deliberately NOT on that basis, because mixing two conventions inside one column is worse than either convention on its own. If the sheet is ever rebuilt on the rolling basis, every row has to move together.",
 "",
 "HOW THE TWO CALCULATIONS COMPARE, on the 231 airports both cover",
 "Annual movements agree to a median 0.4% and annual seats to 0.4%. Two independent calculations off the same underlying source agreeing that closely makes the annual figures settled.",
 "The 30th busiest hour does not agree as well, and the gap is systematic: the Avia figure runs BELOW Jess\'s, and the shortfall widens as the airport gets smaller. +2.0% across the largest 25 airports, -4.5% at rank 51 to 100, -13.2% across the smallest 81. The worst cases are seasonal leisure airports, Antalya, Bodrum and Ercan among them.",
 "",
 "WHY, AND WHY THIS IS THE USEFUL PART",
 "The Avia store holds one row per operated flight but does not record which DATE each row flew. Flights are therefore spread evenly across the dates in their period that match their days-of-operation pattern. That is exact in total, which is why the annual figures agree, but it averages away day-to-day variation inside a period and so flattens the busiest hours. The effect is largest where daily variation is largest relative to the average, so at small and at seasonal airports.",
 "Jess\'s method does not have that problem, because it works from per-airport pulls carrying real dated hours. So this comparison is not a disagreement to be resolved; it is a measurement of a known weakness in the automated route, and it is the first time that weakness has had a number on it.",
 "What it tells Avia: our capacity screen currently OVERSTATES headroom at small and seasonal airports by roughly a tenth. That is the uncomfortable direction, and it is exactly the population where seasonal peaks bite.",
 "",
 "WHAT THE FILLED PEAK CELLS CONTAIN",
 "So that the whole sheet sits on one basis, the 211 filled PEAK values are corrected onto Jess\'s basis using the relationship fitted across the 231 overlapping airports:",
 "    ln(Jess / Avia) = 1.0739 - 0.08367 x ln(annual movements)   for movements",
 "    ln(Jess / Avia) = 1.0619 - 0.08157 x ln(annual movements)   for seats",
 "That halves the median disagreement, from about 8% to about 4.5%. ANNUAL figures are NOT corrected; they are the raw Avia values, because they already agree to 0.4%.",
 "The relationship explains about half the variance (r2 0.47) and leaves a 4.5% residual, so a filled peak should be read as good to roughly plus or minus 5%, not better. The raw uncorrected Avia figure is in the table below for every airport where a comparison exists, so the correction can be undone.",
 "",
 "ONE BUG THIS FOUND IN THE AVIA CODE, which on its own justified the exercise",
 "The Avia store splits Asia 2025 into three January parts, 2025-01p01, 2025-01p16 and 2025-01p23. Avia code read each period key in isolation, which meant assuming two parts a month, so p16 was taken to run to 31 January and swallowed p23. 23 to 31 January was counted twice.",
 "Cost: Asian annual seats 2.5% high, nine duplicated days out of 365 and easily mistaken for noise; the 30th busiest hour 7.4% high at the median and 24% at the worst, because duplicated days go straight to the top of the ranking. Tokyo Haneda came out 33% above Jess\'s figure while agreeing to 0.1% on the annual.",
 "A first attempt at the fix dropped p23 as a redundant re-pull, which was wrong in the same way the original was wrong and quietly discarded 2.5% of Asian traffic. The parts are three that partition the month. Fixed, with a regression test checking every region-year in the store for both a doubled day and a missing one. Afterwards, Asian annual agrees with Jess to 0.08% and Haneda\'s annual matches exactly.",
 "It also moved the published accuracy of the Avia peak hour model: the 2025 blind test was scoring against those inflated Asian peaks, and on rerun the typical error improved from 15.1% to 14.4%.",
 "",
 "TABLE BELOW: the 231 airports both calculations cover, worst disagreement first. CHECK marks an airport where the corrected Avia figure is still more than 15% from Jess\'s.",
 "Source: OAG schedules. Jess Rowden figures as supplied 4 August 2026. Avia Solutions analysis.",
]
r=1
for line in NOTE:
    add(r,[line]); r+=1
r+=1
HDR=['Airport','Region','Annual mvts (Jess)','Annual mvts (Avia)','Diff %',
     'Peak hr mvts (Jess)','Peak hr mvts (Avia raw)','Diff %','Peak hr mvts (Avia calibrated)',
     '30th BHR seats (Jess)','30th BHR seats (Avia raw)','Diff %','30th BHR seats (Avia calibrated)','Flag']
add(r,HDR); hdr_row=r; r+=1
n_flag=0
recs=[]
for a,jr in J.items():
    if not jr['ph_mvt_2w'] or a not in O: continue
    o=O[a]
    ja,oa=float(jr['ann_mvt_2w']),float(o['a_m2'])
    jm,om=float(jr['ph_mvt_2w']),float(o['p_m2'])
    js,os_=float(jr['bhr_seat_2w']),float(o['p_s2'])
    cm,cs=om*up(oa),os_*up(oa,True)
    dm=(om-jm)/jm; ds=(os_-js)/js; da=(oa-ja)/ja if ja else 0
    flag='CHECK' if (abs((cm-jm)/jm)>0.15 or abs((cs-js)/js)>0.15) else ''
    if flag: n_flag+=1
    recs.append((abs(dm),[a,jr['region'],round(ja),round(oa),round(da*100,1),
       round(jm),round(om,1),round(dm*100,1),round(cm),
       round(js),round(os_),round(ds*100,1),round(cs),flag]))
recs.sort(key=lambda x:-x[0])
for _,vals in recs:
    add(r,vals); r+=1
print('comparison rows',len(recs),'flagged',n_flag)
xml=('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
 f'<worksheet xmlns="{NS}"><sheetPr><tabColor rgb="FF1F4E79"/></sheetPr>'
 '<sheetViews><sheetView workbookViewId="0"><pane ySplit="'+str(hdr_row)+'" topLeftCell="A'+str(hdr_row+1)+'" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
 '<sheetFormatPr defaultRowHeight="15"/>'
 '<cols><col min="1" max="1" width="10" customWidth="1"/><col min="2" max="2" width="22" customWidth="1"/>'
 '<col min="3" max="14" width="17" customWidth="1"/></cols>'
 '<sheetData>'+''.join(rows)+'</sheetData></worksheet>')
open('x/xl/worksheets/sheet_avia.xml','w').write(xml)

# wire it in
ct=open('x/[Content_Types].xml').read()
ct=ct.replace('</Types>','<Override PartName="/xl/worksheets/sheet_avia.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
open('x/[Content_Types].xml','w').write(ct)
rels=open('x/xl/_rels/workbook.xml.rels').read()
used={int(m) for m in re.findall(r'Id="rId(\d+)"',rels)}
new=max(used)+1
rels=rels.replace('</Relationships>',f'<Relationship Id="rId{new}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet_avia.xml"/></Relationships>')
open('x/xl/_rels/workbook.xml.rels','w').write(rels)
wb=open('x/xl/workbook.xml').read()
ids={int(m) for m in re.findall(r'sheetId="(\d+)"',wb)}
wb=wb.replace('</sheets>',f'<sheet name="Avia Method Check" sheetId="{max(ids)+1}" r:id="rId{new}"/></sheets>')
wb=wb.replace('<calcPr calcId="191029"/>','<calcPr calcId="191029" fullCalcOnLoad="1"/>')
open('x/xl/workbook.xml','w').write(wb)
print('sheet wired in as rId%d'%new)

# --- keep the package self-consistent -------------------------------------------
# Two things must follow a sheet insertion or Excel offers to "repair" the file, and
# a repair renames or drops sheets, at which point every INDEX(Data!...) on the
# downstream sheets resolves to #REF!. Found the hard way on 4 August 2026.
#
# 1. docProps/app.xml carries its own list of sheet names with a size, and a
#    HeadingPairs count of worksheets. Neither updates itself.
# 2. xl/calcChain.xml caches the calculation order. Once formulas or cached values
#    are edited by hand it is stale, and the safe move is to delete it: Excel
#    rebuilds it on open.
import os
app_p = 'x/docProps/app.xml'
app = open(app_p).read()
m = re.search(r'(<TitlesOfParts><vt:vector size=")(\d+)(" baseType="lpstr">)(.*?)(</vt:vector></TitlesOfParts>)', app, re.S)
titles = m.group(4)
if '<vt:lpstr>Avia Method Check</vt:lpstr>' not in titles:
    # a new WORKSHEET goes after the last worksheet and before the chartsheets
    titles = titles.replace('<vt:lpstr>Charts</vt:lpstr>',
                            '<vt:lpstr>Charts</vt:lpstr><vt:lpstr>Avia Method Check</vt:lpstr>', 1)
    app = app[:m.start()] + m.group(1) + str(int(m.group(2)) + 1) + m.group(3) + titles + m.group(5) + app[m.end():]
    app = re.sub(r'(<vt:lpstr>Worksheets</vt:lpstr></vt:variant><vt:variant><vt:i4>)(\d+)(</vt:i4>)',
                 lambda mm: mm.group(1) + str(int(mm.group(2)) + 1) + mm.group(3), app, count=1)
    open(app_p, 'w').write(app)
    print('app.xml sheet inventory updated')

if os.path.exists('x/xl/calcChain.xml'):
    os.remove('x/xl/calcChain.xml')
    ct = open('x/[Content_Types].xml').read()
    ct = re.sub(r'<Override PartName="/xl/calcChain\.xml"[^>]*/>', '', ct)
    open('x/[Content_Types].xml', 'w').write(ct)
    rl = open('x/xl/_rels/workbook.xml.rels').read()
    rl = re.sub(r'<Relationship [^>]*Target="calcChain\.xml"[^>]*/>', '', rl)
    open('x/xl/_rels/workbook.xml.rels', 'w').write(rl)
    print('stale calcChain removed')

# --- the check that would have caught this ---------------------------------------
wb_n = len(re.findall(r'<sheet ', open('x/xl/workbook.xml').read()))
app_n = int(re.search(r'<TitlesOfParts><vt:vector size="(\d+)"', open(app_p).read()).group(1))
assert wb_n == app_n, f'sheet count mismatch: workbook.xml {wb_n}, app.xml {app_n}'
print(f'sheet inventory consistent: {wb_n}')

# --- document metadata (house rule: author is Avia Solutions, never the library) ----
import datetime
_cp = 'x/docProps/core.xml'
_s = open(_cp, encoding='utf-8', newline='').read()
_now = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
def _setel(s, tag, val):
    if re.search(rf'<{tag}[^>]*>.*?</{tag}>', s, re.S):
        return re.sub(rf'(<{tag}[^>]*>).*?(</{tag}>)', lambda m: m.group(1) + val + m.group(2), s, flags=re.S)
    return s.replace('</cp:coreProperties>', f'<{tag}>{val}</{tag}></cp:coreProperties>')
# The house rule (author is Avia Solutions, never the generating library) exists to
# keep "openpyxl" off a deliverable. It is not a licence to take a colleague's name off
# her own work. This file was created by Jess Rowden and last modified by Avia, and the
# metadata now says exactly that, which is both accurate and the courteous reading.
_creator = re.search(r'<dc:creator>([^<]*)</dc:creator>', _s)
if not _creator or not _creator.group(1).strip() or 'openpyxl' in _creator.group(1):
    _s = _setel(_s, 'dc:creator', 'Avia Solutions')
_s = _setel(_s, 'cp:lastModifiedBy', 'Avia Solutions')
_s = _setel(_s, 'dc:title', '2025 Peak Hour and 30th BHR')
_s = re.sub(r'(<dcterms:modified[^>]*>).*?(</dcterms:modified>)',
            lambda m: m.group(1) + _now + m.group(2), _s, flags=re.S)
open(_cp, 'w', encoding='utf-8', newline='').write(_s)
_ap = 'x/docProps/app.xml'
_t = open(_ap, encoding='utf-8', newline='').read()
_t = _t.replace('<Company></Company>', '<Company>Avia Solutions</Company>')
if '<Company>' not in _t:
    _t = _t.replace('</Properties>', '<Company>Avia Solutions</Company></Properties>')
open(_ap, 'w', encoding='utf-8', newline='').write(_t)
_final = open(_cp, encoding='utf-8').read()
assert '<cp:lastModifiedBy>Avia Solutions</cp:lastModifiedBy>' in _final
assert 'openpyxl' not in _final
print('metadata verified: creator',
      re.search(r'<dc:creator>([^<]*)</dc:creator>', _final).group(1),
      '| last modified by Avia Solutions')

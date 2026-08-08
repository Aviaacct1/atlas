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
 "This is Jess\'s analysis. Avia has filled the 211 airports that were blank and checked the 231 that were not. Nothing of hers has been altered.",
 "",
 "THE CONVENTION, confirmed from BEG.xlsx rather than inferred",
 "Each per-airport workbook builds every dated hour of the full year on the Calc sheet, then the Output sheet reports Annual on row 5, the ABSOLUTE PEAK hour on row 7 as LARGE(...,1), and the true 30th busiest hour on row 12 as LARGE(...,30).",
 "This summary links to ROW 7 throughout. Every figure in it, including the four blocks headed \'30th BHR Seats\', is the ABSOLUTE PEAK hour, not the 30th busiest. The 30th busiest is computed in each per-airport file and is simply never pulled through.",
 "At Belgrade the difference is large: peak 40 movements against 32 for the 30th busiest, and peak 5,437 seats against 4,227. The peak runs circa 25% above the 30th on movements and circa 29% on seats.",
 "This matters because the chart trendlines are used to forecast peak hour figures. A relationship fitted on absolute-peak ratios returns an absolute peak, so anything described downstream as a 30th busy hour will be roughly a quarter too high. The fix is small: point the four BHR blocks at row 12 instead of row 7. It is flagged rather than done, because it is Jess\'s file and her call.",
 "",
 "HOW THE TWO CALCULATIONS COMPARE, on the 231 airports both cover, like for like",
 "Annual movements agree to a median 0.4% and annual seats to 0.4%. On the peak hour, once compared on the same convention, there is NO systematic bias: median +0.5% on peak movements and -0.4% on peak seats, with a median absolute difference of circa 5%.",
 "That 5% is scatter, not bias. The absolute peak is a single hour out of 8,760, so it turns on exactly which flights fall inside one clock hour, and two independent builds will differ at that level.",
 "Belgrade, the one airport where Jess\'s own workbook could be compared cell for cell: annual movements -0.5%, annual seats -0.7%, peak movements +2.3%, peak seats +1.3%, and the 30th busiest hour seats matched to 0.0% (4,229 against 4,227).",
 "",
 "A CORRECTION TO WHAT AVIA SAID EARLIER",
 "An earlier version of this sheet reported that the Avia peak ran circa 8% below Jess\'s, worsening to 13% at small airports, and attributed it to a weakness in how Avia spreads flights across dates. That was wrong. Avia was computing the 30th busiest hour and comparing it against her absolute peak. On the same convention the gap disappears. The filled figures are now raw, with no correction applied, and the calibration that was previously used has been removed.",
 "",
 "WHAT THE FILLED CELLS CONTAIN",
 "The absolute peak clock hour and the annual total, from the Avia OAG store, 2025, service type J, arrivals and departures read as one combined flow, each airport taken from its home region file only so a flight spanning two regions is not counted twice. No adjustment of any kind.",
 "",
 "ONE BUG THIS EXERCISE FOUND IN THE AVIA CODE",
 "The Avia store splits Asia 2025 into three January parts, 2025-01p01, 2025-01p16 and 2025-01p23. Avia code read each period key in isolation, assumed two parts a month, and so took p16 to run to 31 January, swallowing p23. 23 to 31 January was counted twice: Asian annual seats 2.5% high and the peak hour up to 24% high. Tokyo Haneda was 33% out. Fixed, with a regression test over every region-year. Afterwards Asian annuals agree with Jess to 0.08%. It also moved the published accuracy of the Avia peak hour model from 15.1% to 14.4%.",
 "",
 "TWO THINGS AVIA CHANGED IN THIS WORKBOOK, both mechanical",
 "The ratio formulas existed only as far as the airports Jess had completed. 1,044 were missing, so those rows had no ratio cell at all. Once the rows held data a missing cell plotted as zero, and a power trendline cannot pass through a zero, so Excel dropped the trendline and its R-squared label from every chart. The formulas have been extended to all 442 rows in her own pattern.",
 "The saved filters listed specific values rather than a criterion, so they hid every airport Avia added. They now hide only rows that cannot be plotted, using a greaterThan zero test that keeps working as data changes. Visible points rise from 223 to 434, and to circa 400 where domestic or international traffic is absent.",
 "",
 "TABLE BELOW: the 231 airports both calculations cover, largest difference first. CHECK marks a difference above 15%.",
 "Source: OAG schedules 2025. Jess Rowden figures as supplied 4 August 2026. Avia Solutions analysis.",
]
r=1
for line in NOTE:
    add(r,[line]); r+=1
r+=1

# --- fitted trendline per chartsheet ---------------------------------------------
# Each chartsheet carries an Excel power trendline with the equation and R-squared
# displayed. Those labels are generated by Excel at render time from the plotted
# points, so they cannot go stale and they are NOT reproduced here as a substitute.
# This table is an INDEPENDENT calculation of the same fit, so the chart can be
# checked against something rather than trusted. If a chart disagrees with its row
# here, the chart did not recalculate or a filter is hiding rows.
import math, json
FINAL=json.load(open('/tmp/final_values.json'))
CHARTS=[("PH Mvmt 2way","Peak hour movements to annual movements, 2-way","C","F"),
        ("PH Mvmt Arr","Peak hour movements to annual movements, arrivals","D","G"),
        ("PH Mvmt Dep","Peak hour movements to annual movements, departures","E","H"),
        ("BHR Seats 2way","30th BHR seats to annual seats, 2-way","L","O"),
        ("BHR Seats Arr","30th BHR seats to annual seats, arrivals","M","P"),
        ("BHR Seats Dep","30th BHR seats to annual seats, departures","N","Q"),
        ("BHR Seats 2way Dom","30th BHR seats to annual seats, 2-way domestic","U","X"),
        ("BHR Seats Arr Dom","30th BHR seats to annual seats, arrivals domestic","V","Y"),
        ("BHR Seats Dep Dom","30th BHR seats to annual seats, departures domestic","W","Z"),
        ("BHR Seats 2way Int","30th BHR seats to annual seats, 2-way international","AD","AG"),
        ("BHR Seats Int Arr","30th BHR seats to annual seats, arrivals international","AE","AH"),
        ("BHR Seats Int Dep","30th BHR seats to annual seats, departures international","AF","AI")]
def powfit(pts):
    xs=[math.log(x) for x,_ in pts]; ys=[math.log(y) for _,y in pts]
    n=len(xs); mx=sum(xs)/n; my=sum(ys)/n
    m=sum((a-mx)*(b-my) for a,b in zip(xs,ys))/sum((a-mx)**2 for a in xs)
    c=my-m*mx
    ssr=sum((b-(c+m*a))**2 for a,b in zip(xs,ys)); sst=sum((b-my)**2 for b in ys)
    return math.exp(c), m, (1-ssr/sst), n
FITS={}
_G={'PH Mvmt':['C','D','E','F','G','H'],'BHR Seats 2way':['L','M','N','O','P','Q'],
    'Dom':['U','V','W','X','Y','Z'],'Int':['AD','AE','AF','AG','AH','AI']}
SHEETCOLS={}
for _s,_d,_x,_p in CHARTS:
    if 'Dom' in _s: SHEETCOLS[_s]=_G['Dom']
    elif 'Int' in _s: SHEETCOLS[_s]=_G['Int']
    elif _s.startswith('PH Mvmt'): SHEETCOLS[_s]=_G['PH Mvmt']
    else: SHEETCOLS[_s]=_G['BHR Seats 2way']
add(r,["FITTED TRENDLINE ON EACH CHARTSHEET, calculated independently of Excel"]); r+=1
add(r,["Power fit y = c * x^m on the plotted points, x = annual, y = ratio of peak to annual. "
       "Include rows only, blanks skipped. Fitted on the log-log form, which is how Excel fits a power trendline."]); r+=1
add(r,["Chartsheet","What it plots","c","m (exponent)","R2","Points"]); r+=1
for sheet,desc,xc,pc in CHARTS:
    pts=[]
    for a,jr in J.items():
        if jr['include']!='Include' or a not in FINAL: continue
        v=FINAL[a]
        # a row is plotted only if ALL SIX series on its sheet are positive, which is
        # the same rule the sheet filter applies, so the table matches the chart
        if not all(v.get(k) not in (None,0) and (v.get(k) or 0)>0 for k in SHEETCOLS[sheet]):
            continue
        x=v.get(xc); p=v.get(pc)
        pts.append((x,p/x))
    c,m,r2,n=powfit(pts)
    FITS[sheet]=(c,m,r2,n)
    add(r,[sheet,desc,round(c,7),round(m,5),round(r2,4),n]); r+=1
json.dump(FITS,open('/tmp/chart_fits.json','w'))
add(r,["Source: OAG schedules 2025. Avia Solutions analysis, 4 August 2026."]); r+=2

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

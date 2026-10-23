from pathlib import Path
import json,re,hashlib,zipfile
from pypdf import PdfReader
from docx import Document
P=Path(__file__).resolve().parent; ROOT=P.parents[2]; OUT=ROOT/'architecture_tlm/memory_savings_20261023'
c=json.loads((OUT/'CALCULATIONS.json').read_bytes());text=(OUT/'REPORT_ZH.md').read_text(encoding='utf-8')
tables=[];cur=[]
for l in text.splitlines()+['']:
    if l.startswith('|'):
        row=[s.strip() for s in l.strip('|').split('|')]
        if not all(re.fullmatch(r':?-+:?',x) for x in row):cur.append(row)
    elif cur:tables.append(cur);cur=[]
checks=[]
def equal(a,b,name):assert a==b,(name,a,b);checks.append(name)
def n(x):return float(x.replace(',','').replace('%','').strip())
whole=next(t for t in tables if 'DRAM总读写' in t[0][1])
for i,r in enumerate(c['rows']):
    for j,k in enumerate(['dram_MiB','sram_MiB','sram_reserved_KiB'],1):equal(n(whole[i+1][j]),round(r[k],2),f'whole_{i}_{k}')
att=next(t for t in tables if t[0][1]=='K读取')
for row,r in zip(att[1:],[c['rows'][i] for i in [0,2,4,5,6,7]]):
    for j,k in enumerate(['K_MiB','V_MiB','summary_MiB','attention_traffic_saving_pct'],1):equal(n(row[j]),round(r[k],2),'attention_'+row[0]+'_'+k)
energy=next(t for t in tables if t[0][0]=='只比较已计存储边界')
for row,(a,b) in zip(energy[1:],[(c['rows'][0],c['rows'][4]),(c['rows'][5],c['rows'][7])]):
    equal(n(row[1].replace('mJ','')),round(a['conditional_storage_mJ'],2),'energy_base_'+row[0])
    equal(n(row[2].replace('mJ','')),round(b['conditional_storage_mJ'],2),'energy_new_'+row[0])
    equal(n(row[3]),round(b['conditional_storage_energy_saving_pct'],2),'energy_delta_'+row[0])
docx=OUT/'概率计算架构的SRAM与DRAM节省总结.docx'; d=Document(docx)
equal(len(d.tables),len(tables),'table_count')
pdf=P/'render/word_export.pdf'; pages=PdfReader(pdf).pages
equal(len(pages),7,'pages')
for i,p in enumerate(pages):assert len(p.extract_text())>700;checks.append('nonempty_page_'+str(i+1))
with zipfile.ZipFile(docx) as z:
    assert b'<w:pBdr' not in z.read('word/styles.xml');checks.append('no_title_border')
receipt=dict(scope='derived quantities and DOCX layout/text checks, no new hardware/model simulation',checks=len(checks),passed=checks,
    renderer='Microsoft Word native PDF export + packaged render_docx.py rasterization; LibreOffice unavailable',pages=7,
    files=[dict(path=str(p.relative_to(ROOT)).replace('\\','/'),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size) for p in [OUT/'REPORT_ZH.md',OUT/'CALCULATIONS.json',OUT/'SOURCE_INDEX.json',docx]])
(P/'VALIDATION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(checks=len(checks),pages=7,pass_all=True)))

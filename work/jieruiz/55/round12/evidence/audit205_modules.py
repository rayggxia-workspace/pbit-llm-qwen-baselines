from pathlib import Path
import json,zipfile,tarfile,hashlib,statistics,math,re,subprocess
A=Path(__file__).resolve().parent;W=A.parent.parent/'tmp/pr55-review-round12-20261028';ROOT=W/'architecture_tlm/module_energy_20261028';s=json.loads((ROOT/'results/FINAL_SUMMARY.json').read_text(encoding='utf-8'));out={'head':'5bfb221544daca8c345773a4741c30d2712f75ba','packages':[],'archives':[],'windows':0,'public_source_matches':0}
def same(a,b):assert math.isclose(a,b,rel_tol=1e-8,abs_tol=1e-9),(a,b)
source=A/'module205_source';source.mkdir(exist_ok=True)
for x in s['source_packages']:
 with zipfile.ZipFile(x['path']) as z:
  pre=z.namelist()[0].split('/')[0]+'/';b=z.read(pre+'EXECUTION_MANIFEST.json');assert hashlib.sha256(b).hexdigest()==x['manifest_sha256'];files=json.loads(b)['files']
  for p,h in files.items():
   data=z.read(pre+p);assert hashlib.sha256(data).hexdigest()==h,(x['path'],p)
   if 'v2' in x['snapshot']:
    f=ROOT/p
    if f.is_file():assert hashlib.sha256(f.read_bytes()).hexdigest()==h,('published differs',p);out['public_source_matches']+=1
    if p.startswith(('rtl/','benches/','fixtures/')):
     dest=source/p;assert dest.resolve().is_relative_to(source.resolve());dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
  out['packages'].append({'snapshot':x['snapshot'],'members':len(files)})
raw={}
for x in s['report_archives']:
 with tarfile.open(x['path']) as t:
  manifest=json.load(t.extractfile('RETURN_MANIFEST.json' if 'RETURN_MANIFEST.json' in t.getnames() else 'BOOTSTRAP_MANIFEST.json'))['files']
  for p,h in manifest.items():assert hashlib.sha256(t.extractfile(p).read()).hexdigest()==h,p
  if x['status']=='calculated':
   r=json.load(t.extractfile('RESULT.json'));raw[x['path']]=r
   for w in r['windows']:
    pre=w['mode']+'_'+str(w['seed'])+'/pt/';text=t.extractfile(pre+'power.rpt').read().decode();assert 'Dynamic Power Units = 1 W' in text and 'Leakage Power Units = 1 W' in text
    for title,k in [('Total Power','total_W'),('Cell Internal Power','internal_W'),('Net Switching Power','switching_W'),('Cell Leakage Power','leakage_W')]:same(float(re.search(re.escape(title)+r'\s*=\s*([\d.eE+-]+)',text)[1]),w[k])
    for k in ['setup_slack_ns','hold_slack_ns']:same(float(t.extractfile(pre+k+'.txt').read()),w[k])
    if w['operations']:same(w['total_W']*w['window_ns']*1000/w['operations'],w['gross_pJ_per_operation'])
    out['windows']+=1
  out['archives'].append({'path':x['path'],'members':len(manifest),'status':x['status']})
for d in s['PPA']:
 r=raw[d['archive']];same(r['raw_area_um2'],d['raw_area_um2']);same(d['raw_area_um2']*.81,d['area_55eq_um2'])
 for k in ['setup_slack_ns','hold_slack_ns']:same(min(w[k] for w in r['windows']),d[k]);assert d[k]>=0
 for name,profile in d['profiles'].items():
  ws=[w for w in r['windows'] if w['mode']==name];assert len(ws)==3
  for k in ['total_W','internal_W','switching_W','leakage_W']:same(statistics.mean(w[k] for w in ws),profile[k])
  if ws[0]['operations']:same(statistics.mean(w['gross_pJ_per_operation'] for w in ws),profile['energy_pJ_per_operation'])
for x in s['composition_estimates']:same((x['predicted_pJ']-x['measured_pJ'])/x['measured_pJ'],x['relative_error'])
out.update(status='passed',designs=len(s['PPA']),functional_replays=s['functional_replays'],functional_transactions=s['functional_transactions'])
(A/'AUDIT205_MODULES.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('PASS',out['windows'],'PT windows',len(out['archives']),'archives',out['public_source_matches'],'public source matches',flush=True)

import subprocess,json,zipfile,tarfile,hashlib,statistics,math,re
from pathlib import Path
A=Path(__file__).resolve().parent;R=A.parent.parent/'pbit-llm-qwen-baselines';HEAD='9f762ced3d25b47bf3963fbf38ff8d321850854b'
def blob(p):return subprocess.check_output(['git','-C',str(R),'show',HEAD+':'+p])
s=json.loads(blob('architecture_tlm/matrix_single_scale_20261028/results/FINAL_SUMMARY.json'))
def same(a,b):assert math.isclose(a,b,rel_tol=1e-8,abs_tol=1e-10),(a,b)
res={'head':HEAD,'packages':[],'reports':[],'ppa':[]};raw={}
for x in s['source_packages']:
 with zipfile.ZipFile(x['path']) as z:
  pre=z.namelist()[0].split('/')[0]+'/';m=z.read(pre+'EXECUTION_MANIFEST.json');assert hashlib.sha256(m).hexdigest()==x['source_manifest_sha256'];files=json.loads(m)['files']
  for p,h in files.items():assert hashlib.sha256(z.read(pre+p)).hexdigest()==h,p
  res['packages'].append({'snapshot':x['snapshot'],'verified_members':len(files)})
for x in s['report_archives']:
 with tarfile.open(x['path']) as t:
  files=json.load(t.extractfile('RETURN_MANIFEST.json'))['files']
  for p,h in files.items():assert hashlib.sha256(t.extractfile(p).read()).hexdigest()==h,p
  result=json.load(t.extractfile('RESULT.json'));raw[x['path']]=result
  # Verify actual PT power/timing files, not only the generated RESULT.
  if result['status']=='calculated':
   for w in result['windows']:
    prefix=w['mode']+'_s'+str(w['seed'])+'/'
    rpt=t.extractfile(prefix+'pt/power.rpt').read().decode();assert 'Dynamic Power Units = 1 W' in rpt and 'Leakage Power Units = 1 W' in rpt
    for title,k in [('Total Power','total_W'),('Cell Internal Power','internal_W'),('Net Switching Power','switching_W'),('Cell Leakage Power','leakage_W')]:same(float(re.search(re.escape(title)+r'\s*=\s*([\d.eE+-]+)',rpt)[1]),w[k])
    names=[p for p in t.getnames() if p.startswith(prefix) and p.endswith(('total_power_w.txt','setup_slack_ns.txt','hold_slack_ns.txt'))]
    for p in names:
     v=float(t.extractfile(p).read());k={'total_power_w.txt':'total_W','setup_slack_ns.txt':'setup_slack_ns','hold_slack_ns.txt':'hold_slack_ns'}[p.rsplit('/',1)[-1]];same(v,w[k])
  res['reports'].append({'path':x['path'],'verified_members':len(files),'status':result['status']})
for row in s['PPA']:
 r=raw[row['archive']];same(r['raw_area_um2'],row['raw_area_um2']);same(row['raw_area_um2']*.81,row['area_55eq_um2']);assert r['top']==row['top']
 ws=r['windows'];active=[w for w in ws if w['mode']=='active'];idle=[w for w in ws if w['mode']=='idle'];assert len(active)==len(idle)==3
 for w in active:
  same(w['total_W']*w['window_ns']*1000/w['operations'],w['gross_pJ_per_operation']);same(w['window_ns']/10/w['operations'],w['cycles_per_operation'])
 for k in ['total_W','internal_W','switching_W','leakage_W','gross_pJ_per_operation','cycles_per_operation']:same(statistics.mean(w[k] for w in active),row[k])
 same(statistics.pstdev(w['gross_pJ_per_operation'] for w in active),row['energy_std_pJ']);same(statistics.mean(w['total_W'] for w in idle),row['idle_W'])
 for k in ['setup_slack_ns','hold_slack_ns']:same(min(w[k] for w in ws),row[k]);assert row[k]>0
 res['ppa'].append({'top':row['top'],'gross_pJ_per_operation':row['gross_pJ_per_operation'],'raw_area_um2':row['raw_area_um2'],'area_55eq_um2':row['area_55eq_um2'],'M':row['M']})
res['functional_frames']=sum(x['frames'] for x in s['functional']);res['windows']=sum(len(x['windows']) for x in s['PPA']);res['status']='passed'
(A/'AUDIT205.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('PASS',len(res['packages']),'packages',len(res['reports']),'reports',len(res['ppa']),'designs',res['windows'],'windows',res['functional_frames'],'frames')

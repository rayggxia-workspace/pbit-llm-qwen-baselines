from pathlib import Path
import json,subprocess,statistics,math,tarfile,zipfile,hashlib
A=Path(__file__).resolve().parent;R=A.parent.parent/'pbit-llm-qwen-baselines';HEAD='0a87b21c004ea0a93eba6d84491d8f037a55083f'
s=json.loads(subprocess.check_output(['git','-C',str(R),'show',HEAD+':digital_circuit_simulation_registry/summaries/20261027/PPA_SUMMARY.json']))
def same(a,b):assert math.isclose(a,b,rel_tol=1e-8,abs_tol=1e-9),(a,b)
raw=json.loads(Path(s['sources'][4]['path']).read_text())['rows'];pbit=json.loads(Path(s['sources'][0]['path']).read_text())['designs'];results=[]
for d in s['designs']:
 if d['campaign']=='calibration_v2':
  r=next(x['result'] for x in raw if x['result']['top']==d['top']);ws=r['windows'];same(statistics.mean(w['area_um2'] for w in ws),d['area_um2'])
  for mode,m in d['modes'].items():
   rows=[w for w in ws if w['mode']==mode];assert len(rows)==3
   for a,b in [('power_uW','total_W'),('internal_uW','internal_W'),('switching_uW','switching_W'),('leakage_uW','leakage_W')]:same(statistics.mean(w[b]*1e6 for w in rows),m[a])
   if m['energy_pJ_per_operation'] is not None:same(statistics.mean(w['total_W']*w['window_ns']*1e3/w['operations'] for w in rows),m['energy_pJ_per_operation'])
  for k in ['setup_slack_ns','hold_slack_ns']:same(min(w[k] for w in ws),d[k])
 else:
  r=next(x for x in pbit if x['top']==d['top'] and x['corner']==d['corner']);same(r['area_um2'],d['area_um2'])
  for mode,m in d['modes'].items():
   v=r['modes'][mode]
   for a,b in [('power_uW','total_W'),('internal_uW','internal_W'),('switching_uW','switching_W'),('leakage_uW','leakage_W')]:same(v[b]*1e6,m[a])
   if m['energy_pJ_per_operation'] is not None:same(v['pJ_per_call'],m['energy_pJ_per_operation'])
  for k in ['setup_slack_ns','hold_slack_ns']:same(r[k],d[k])
 results.append(dict(top=d['top'],corner=d['corner'],raw_area_um2=d['area_um2'],area_factor=.81,area_55eq_um2=d['area_um2']*.81))
archives=[]
materials=json.loads((A/'MATERIAL_AUDIT.json').read_text(encoding='utf-8'))['197']['verified']
for item in materials:
 p=Path(item['path'])
 if not p.name.endswith('.tar.gz'):continue
 with tarfile.open(p) as t:
  ns=t.getnames();ms=[n for n in ns if n.endswith('RETURN_MANIFEST.json')]
  count=0
  for mn in ms:
   files=json.load(t.extractfile(mn)).get('files',{});prefix=mn[:-len('RETURN_MANIFEST.json')]
   if isinstance(files,dict):
    for n,h in files.items():
     if isinstance(h,dict):h=h['sha256']
     name=prefix+n if prefix+n in ns else n
     assert hashlib.sha256(t.extractfile(name).read()).hexdigest()==h,(p,name);count+=1
  archives.append(dict(path=str(p),verified_members=count,manifest_found=bool(ms)))
out=dict(status='passed',head=HEAD,designs=results,archives=archives,formal_windows=s['formal_windows'],limitation='author source summaries reaggregated; raw tar manifests checked where present; no new EDA or 500MHz validation; original PVT and raw area unchanged')
(A/'AUDIT197.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('PASS',len(results),'designs',s['formal_windows'],'windows',len(archives),'archives')

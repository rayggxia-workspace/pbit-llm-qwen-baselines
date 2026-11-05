"""Summarize frozen synthetic fixtures and archived actual results separately."""
from pathlib import Path
import argparse,hashlib,json,math,statistics,tarfile
ROOT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def numeric():
 rows=[]
 for f in (ROOT/'fixtures').glob('*/metrics.json'):
  m=int(f.parent.name.split('_')[0][1:]);seed=int(f.parent.name.split('_s')[1])
  rows.extend(dict(x,M=m,seed=seed) for x in json.loads(f.read_text(encoding='utf-8')))
 groups=[]
 for name in sorted({x['frame'] for x in rows}):
  a=[x for x in rows if x['frame']==name];e=[x['or4_error_same_event'] for x in a];se=[x['event_error_quantized'] for x in a]
  ratio=[x['or4_error_same_event']/x['same_event_exact'] for x in a if x['same_event_exact']]
  groups.append({'frame':name,'outputs':len(a),'OR4_bias_raw':statistics.mean(e),'OR4_RMSE_raw':math.sqrt(statistics.mean(v*v for v in e)),
   'OR4_mean_abs_error_raw':statistics.mean(abs(v) for v in e),'SC_RMSE_vs_quantized_T32_raw':math.sqrt(statistics.mean(v*v for v in se)),
   'OR4_relative_error_same_event_nonzero_range':[min(ratio),max(ratio)] if ratio else None})
 r={'scope':'synthetic fixture arithmetic; not model quality or independent confidence trials','N':64,'T':32,'seeds':[17,503,1009],
   'M':[1,8],'full_scale_SC_raw':64*127*64*32,'by_frame':groups,
   'fixture_SHA256':{str(f.relative_to(ROOT)):sha(f) for f in (ROOT/'fixtures').rglob('*') if f.is_file()}}
 save(ROOT/'NUMERICAL_SUMMARY.json',r)
 for x in groups:
  if x['frame'] in ('shared_half','independent_half','positive_max','cancel'):
   print(x['frame'],'OR4 RMSE',x['OR4_RMSE_raw'],'relative range',x['OR4_relative_error_same_event_nonzero_range'])
def collect(path):
 records=[];ppa=[];functional=[]
 for f in sorted(path.rglob('reports.tar.gz')):
  with tarfile.open(f) as t:
   index=json.load(t.extractfile('RETURN_MANIFEST.json'))['files']
   for n,h in index.items():
    b=t.extractfile(n).read()
    if hashlib.sha256(b).hexdigest()!=h:raise ValueError('Archive member changed '+n)
   result=json.load(t.extractfile('RESULT.json'))
  records.append({'path':str(f),'sha256':sha(f),'bytes':f.stat().st_size,'members_verified':len(index),'status':result['status']})
  if 'functional_' in str(f.parent):functional.append({'path':str(f.parent),'result':result})
  else:ppa.append(result)
 rows=[]
 for x in ppa:
  for mode in ('active','idle'):
   ws=[w for w in x.get('windows',[]) if w['mode']==mode]
   if not ws:continue
   vals={k:statistics.mean(w[k] for w in ws) for k in ['raw_area_um2','area_55eq_um2','total_W','internal_W','switching_W','leakage_W','window_ns']}
   vals.update(top=x['top'],mode=mode,windows=len(ws),status=x['status'],setup_slack_ns=min(w['setup_slack_ns'] for w in ws),
    hold_slack_ns=min(w['hold_slack_ns'] for w in ws),all_mapped_pin_activity_verified=all(w['all_mapped_pin_activity_verified'] for w in ws),
    review_flags=sorted({v for w in ws for v in w['review_flags']}))
   if mode=='active':
    vals['gross_pJ_per_frame']=statistics.mean(w['gross_pJ_per_operation'] for w in ws)
    vals['cycles_per_frame']=statistics.mean(w['cycles_per_operation'] for w in ws)
    vals['latency_cycles_range']=[min(v for w in ws for v in w['latency_cycles_per_frame']),max(v for w in ws for v in w['latency_cycles_per_frame'])]
   rows.append(vals)
 save(ROOT/'RESULTS_SUMMARY.json',{'archives':records,'functional':functional,'PPA':rows,'raw_runs':ppa})
 print('ARCHIVES_VERIFIED',len(records),'PPA_ROWS',len(rows))
 for x in rows:
  if x['mode']=='active':print(x['top'],'area55',x['area_55eq_um2'],'uW',x['total_W']*1e6,'pJ/frame',x['gross_pJ_per_frame'],'STA',x['setup_slack_ns'],x['hold_slack_ns'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--archive',type=Path);a=p.parse_args();numeric()
 if a.archive:collect(a.archive)

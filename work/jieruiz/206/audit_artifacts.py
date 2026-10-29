"""Offline source/byte/protocol audit; never submits remote work."""
import argparse,datetime,hashlib,json,math,pathlib,statistics,struct,subprocess

def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
VARIANTS=('lane','x_max','gu_max','all_max','all_trim1','all_trim4')
SHARDS={0:('fixed',VARIANTS),1:('joint',('lane','x_max')),2:('joint',('gu_max','all_max')),3:('joint',('all_trim1','all_trim4'))}

def audit(R,final=False):
 W=R/'work/jieruiz/206';sub=load(max(W.glob('SUBMISSION_*.json'),key=lambda p:p.stat().st_mtime));src=load(W/('SOURCE_'+sub['commit'][:8]+'.json'))
 D=R/'qwen3/results/group_shared_20261028'/src['commit'][:12]
 for n,h in src['files_sha256'].items():assert hashlib.sha256(subprocess.check_output(['git','show',src['commit']+':'+n],cwd=R)).hexdigest()==h,n
 assert len(src['files_sha256'])==62
 cfg=load(R/'qwen3/group_shared/config.json');sealed=[];pending=[];cases={};targets={};raw_index=[]
 for phase,sh in [('pilot',0)]+[('main',i) for i in range(4)]:
  P=D/phase/('shard'+str(sh));f=P/'complete.json'
  if not f.exists():pending.append(dict(phase=phase,shard=sh));continue
  m=load(f);assert m['status']=='completed' and m['shard']==sh
  expected=5 if phase=='pilot' else 19 if sh==0 else 7
  assert m['cases']==expected and len(m['documents'])==expected+1
  assert sha(f)==load(f.with_suffix('.sha256.json'))['sha256']
  for n,h in m['documents'].items():assert sha(P/n)==h and load((P/n).with_suffix('.sha256.json'))['sha256']==h
  p=load(P/'provenance.json');assert p['source']==src and p['config_sha256']==sha(R/'qwen3/group_shared/config.json')
  assert p['model']==cfg['model'] and p['prepared_sha256']=='f8c6c0a754f5c7fff4a5afa0d054b4ca59493efde6ef5b742515d9ed58f054db'
  for split,x in p['data'].items():assert x['sha256']==cfg['data_sha256'][split]
  for key in ('fixed_xz','fixed_gu'):assert p[key+'_sha256']==cfg[key+'_calibration_sha256']
  c=p['effective_config'];assert c['context']==(256 if phase=='pilot' else 2048)
  assert c['decode']==(32 if phase=='pilot' else 128) and c['examples']==(1 if phase=='pilot' else 8)
  desired=['bf16']+[f"{z['GU']}_{z['variant']}_s{z['seed']}" for z in p['cases']];got=[]
  for name in m['documents']:
   if name=='provenance.json':continue
   x=load(P/name);assert x['status']=='completed' and x['scored_tokens']==c['examples']*c['decode']
   assert x['provenance_sha256']==sha(P/'provenance.json') and len(x['rows'])==c['examples']
   assert len(x['all_layer_calls'])==36 and set(x['all_layer_calls'])=={c['examples']}
   assert len(x['all_layer_input_tokens'])==36 and set(x['all_layer_input_tokens'])=={c['examples']*(c['context']+c['decode']-1)}
   assert math.isclose(sum(z['nll_sum'] for z in x['rows']),x['nll_sum'],rel_tol=0,abs_tol=1e-8)
   assert math.isclose(math.exp(x['nll_sum']/x['scored_tokens']),x['perplexity'],rel_tol=1e-12)
   positions=[v for z in x['rows'] for v in range(z['first_target'],z['last_target_exclusive'])]
   h=hashlib.sha256(b''.join(struct.pack('<q',v) for v in positions)).hexdigest();assert h==x['target_positions_sha256']
   if phase not in targets:targets[phase]=h
   assert targets[phase]==h
   if x['case']=='bf16':assert x['perplexity']==(27.312114874936853 if phase=='pilot' else 13.566049199388152)
   else:
    assert len(x['diagnostics'])==36 and x['GU_samples']==(64 if x['GU']=='fixed' else 256)
    for d in x['diagnostics'].values():
     assert d['variant']==x['variant'] and d['gu_law']==x['GU']
     assert d['nonlinear_T']==128 and d['g_u_scales_separate']
     for signal,z in d['stages'].items():
      expected_shared=(x['variant'] in ('x_max','all_max','all_trim1','all_trim4')) if signal=='x' else (x['variant'] in ('gu_max','all_max','all_trim1','all_trim4'))
      assert z['shared_group64']==expected_shared
      if expected_shared:assert z['mixed_scale_groups']==0
   cases[phase,sh,x['case']]=x;got.append(x['case'])
  assert sorted(got)==sorted(desired)
  for q in sorted(P.glob('*.json')):raw_index.append(dict(path=q.relative_to(R).as_posix(),sha256=sha(q),bytes=q.stat().st_size))
  sealed.append(dict(phase=phase,shard=sh,cases=expected,complete_sha256=sha(f)))
 log=(D/'pilot_validation.log').read_bytes();assert b'Ran 28 tests' in log and b'\nOK\n' in log
 out=dict(status='completed' if not pending else 'main_pending',source=src['commit'],source_blobs_verified=62,
  unit_checks=28,validation_log_sha256=sha(D/'pilot_validation.log'),sealed=sealed,pending=pending,
  main_scores=sum(k[0]=='main' for k in cases),expected_main_scores=40,expected_main_unique=37,
  pilot_scores=sum(k[0]=='pilot' for k in cases),target_sha256=targets,raw_originals=raw_index,full_WT2=False,
  updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
 save(W/'ARTIFACT_AUDIT.json',out)
 if final:
  assert not pending,'Main shards not all sealed'
  assert out['main_scores']==40 and targets['main']=='b8b6365968ca1937c7c332dee67df82f287db6de3f0933c21800f4732042ab1a'
  byname={x['case']:x for k,x in cases.items() if k[0]=='main'};rows=[]
  for law in ('fixed','joint'):
   baseline=[byname[f'{law}_lane_s{s}']['perplexity'] for s in (0,1,2)]
   expected=[15.551864566282788,15.467966690474148,15.074231519987723] if law=='fixed' else [15.865387583944637,16.093814459554842,15.72621827278319]
   assert baseline==expected
   for variant in VARIANTS:
    vals=[byname[f'{law}_{variant}_s{s}']['perplexity'] for s in (0,1,2)]
    stage={}
    for signal in ('x','g','u'):
     ds=[d['stages'][signal] for s in (0,1,2) for d in byname[f'{law}_{variant}_s{s}']['diagnostics'].values()]
     n=sum(z['elements'] for z in ds)
     stage[signal]=dict(mean_probability=sum(z['mean_probability']*z['elements'] for z in ds)/n,
       clip_fraction=sum(z['clip_fraction']*z['elements'] for z in ds)/n,
       layer_mean_encoding_nmse=statistics.mean(z['encoding_nmse'] for z in ds),
       scale_hist=[sum(z['scale_hist'][i] for z in ds) for i in range(4)])
    diag=[d for s in (0,1,2) for d in byname[f'{law}_{variant}_s{s}']['diagnostics'].values()]
    rows.append(dict(GU=law,variant=variant,ppl=vals,ppl_mean=statistics.mean(vals),ppl_sample_sd=statistics.stdev(vals),
     delta_pct_vs_own_lane=(statistics.mean(vals)/statistics.mean(baseline)-1)*100,
     paired_delta_nll_vs_own_lane=statistics.mean(math.log(a/b) for a,b in zip(vals,baseline)),
     stages=stage,layer_mean_AND_probability=statistics.mean(z['mean_AND_probability'] for z in diag),
     layer_mean_zero_AND_count_fraction=statistics.mean(z['zero_AND_count_fraction'] for z in diag)))
  save(D/'FINAL_SUMMARY.json',dict(status='completed',BF16=13.566049199388152,rows=rows,source=src['commit'],audit=out,protocol='1024 suffix targets;notfullWT2'))
 return out

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path);p.add_argument('--write-final',action='store_true');a=p.parse_args()
 r=audit(a.root or pathlib.Path(__file__).resolve().parents[3],a.write_final)
 print(json.dumps({k:v for k,v in r.items() if k!='raw_originals'},ensure_ascii=True))

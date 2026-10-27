"""Issue201 offline audit; only complete.json+documents establish shard completion.

Run in task checkout: python work/jieruiz/201/audit_artifacts.py [--write-final]
Requires only Python standard library and Git; never starts GPU/Slurm jobs.
"""
import argparse,datetime,hashlib,json,math,pathlib,statistics,subprocess


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def audit(root,write_final=False):
 d=root/'qwen3/results/dual_gu_20261027';w=root/'work/jieruiz/201'
 src=load(w/'SOURCE_2cd6d360.json');commit=src['commit'];checks=[]
 for name,h in src['files_sha256'].items():
  b=subprocess.check_output(['git','show',commit+':'+name],cwd=root)
  assert hashlib.sha256(b).hexdigest()==h,name
 checks.append('58 frozen execution blobs equal Git commit')
 assert len(src['files_sha256'])==58
 cfg=load(root/'qwen3/dual_gu/config.json');prep=load(d/'inputs/prepared.json')
 assert prep['model']['id']=='Qwen/Qwen3-4B'
 assert prep['model']['revision']=='1cfa9a7208912126459214e8b04321603b3df60c'
 assert len([x for x in prep['files'] if x['name'].endswith('.safetensors')])==3
 for n,x in load(d/'inputs/INDEX.json').items():assert sha(d/'inputs'/n)==x['sha256']
 checks.append('input original bytes and model/weight/tokenizer hash manifest')
 cases={};targets={};sealed=[];pending=[]
 for phase,i in [('pilot',3)]+[('main',j) for j in range(4)]:
  folder=d/'pilot' if phase=='pilot' else d/'main'/('shard'+str(i))
  done=folder/'complete.json'
  if not done.exists():pending.append(dict(phase=phase,shard=i));continue
  m=load(done);expected=4 if phase=='pilot' else 10
  assert m['status']=='completed' and m['cases']==expected and m['shard']==i
  assert len(m['documents'])==expected+1
  for n,h in m['documents'].items():
   f=folder/n;assert sha(f)==h,(str(f),'documents')
   side=f.with_suffix('.sha256.json');assert load(side)['sha256']==h,(str(f),'sidecar')
  p=load(folder/'provenance.json');assert p['source']==src
  assert p['config_sha256']==sha(root/'qwen3/dual_gu/config.json')
  assert p['prepared_sha256']==sha(d/'inputs/prepared.json')
  assert p['model']==prep['model']
  assert p['fixed_xz_sha256']==sha(d/'inputs/fixed_xz_calibration.json')
  assert p['fixed_gu_sha256']==sha(d/'inputs/fixed_gu_calibration.json')
  for split,x in p['data'].items():assert x['sha256']==cfg['data_sha256'][split]
  eff=p['effective_config'];assert eff['context']==(256 if phase=='pilot' else 2048)
  assert eff['decode']==(32 if phase=='pilot' else 128) and eff['examples']==(1 if phase=='pilot' else 8)
  token_total=eff['examples']*(eff['context']+eff['decode']-1)
  found=[]
  for n in m['documents']:
   if n=='provenance.json':continue
   x=load(folder/n);assert x['status']=='completed'
   assert x['provenance_sha256']==sha(folder/'provenance.json')
   assert x['scored_tokens']==eff['examples']*eff['decode']
   assert len(x['all_layer_calls'])==36 and set(x['all_layer_calls'])=={eff['examples']}
   assert len(x['all_layer_input_tokens'])==36 and set(x['all_layer_input_tokens'])=={token_total}
   assert len(x['rows'])==eff['examples'] and sum(y['scored_tokens'] for y in x['rows'])==x['scored_tokens']
   assert math.isclose(sum(y['nll_sum'] for y in x['rows']),x['nll_sum'],rel_tol=0,abs_tol=1e-8)
   assert math.isclose(math.exp(x['nll_sum']/x['scored_tokens']),x['perplexity'],rel_tol=1e-12)
   pos=[z for y in x['rows'] for z in range(y['first_target'],y['last_target_exclusive'])]
   import struct
   h=hashlib.sha256(b''.join(struct.pack('<q',z) for z in pos)).hexdigest()
   assert h==x['target_positions_sha256']
   if phase not in targets:targets[phase]=h
   assert targets[phase]==h
   if x['case']=='bf16':assert x['perplexity']==(27.312114874936853 if phase=='pilot' else 13.566049199388152)
   else:
    T=(32,64,128,256)[i];law=x['gu_law'];seed=x['seed']
    assert law in ('fixed','iid','joint') and seed in ((0,) if phase=='pilot' else (0,1,2))
    assert x['case']==f'{law}_T{T}_s{seed}' and x['gu_samples']==T
    grids={32:(8,4),64:(8,8),128:(16,8),256:(16,16)}
    ka,kw=grids[T]
    assert x['input_strata']==(ka if law=='joint' else min(64,T))
    assert x['weight_strata']==(kw if law=='joint' else 1 if law=='iid' else None)
    assert len(x['diagnostics'])==36
   cases[(phase,i,x['case'])]=x;found.append(x['case'])
  expected_names=['bf16']+[f'{law}_T{(32,64,128,256)[i]}_s{s}' for law in ('fixed','iid','joint') for s in ((0,) if phase=='pilot' else (0,1,2))]
  assert sorted(found)==sorted(expected_names)
  sealed.append(dict(phase=phase,shard=i,cases=expected,complete_sha256=sha(done)))
 assert load(w/'VALIDATION_RESULT.json')['log_sha256']==sha(d/'validation.log')
 assert b'Ran 18 tests' in (d/'validation.log').read_bytes() and b'\nOK\n' in (d/'validation.log').read_bytes()
 checks.append('sealed shard documents/sidecars, source/config/inputs, NLL/target SHA,36-layer input coverage')
 complete=not pending
 result=dict(status='complete' if complete else 'main_pending',checks=checks,sealed=sealed,pending=pending,target_positions_sha256=targets,
             archived_scores=len(cases),main_scores=sum(k[0]=='main' for k in cases),expected_main_scores=40,main_unique_configs=37,
             full_WT2=False,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
 save(w/'ARTIFACT_AUDIT.json',result)
 if write_final:
  assert complete,'Cannot write final summary until all four main shards are sealed'
  rows=[];bf=cases[('main',0,'bf16')]['perplexity']
  for i,T in enumerate((32,64,128,256)):
   fixed=[cases[('main',i,f'fixed_T{T}_s{s}')]['perplexity'] for s in (0,1,2)]
   for law in ('fixed','iid','joint'):
    vals=[cases[('main',i,f'{law}_T{T}_s{s}')]['perplexity'] for s in (0,1,2)]
    rows.append(dict(T=T,law=law,ppl=vals,ppl_mean=statistics.mean(vals),ppl_sample_sd=statistics.stdev(vals),
       paired_delta_nll_vs_fixed=statistics.mean(math.log(a/b) for a,b in zip(vals,fixed)),
       mean_ppl_delta_pct_vs_fixed=(statistics.mean(vals)/statistics.mean(fixed)-1)*100,
       mean_ppl_delta_pct_vs_BF16=(statistics.mean(vals)/bf-1)*100))
  save(d/'FINAL_SUMMARY.json',dict(status='completed',source=commit,protocol='1024 suffix targets,not fullWT2',bf16=bf,rows=rows,audit=result))
 return result


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path);p.add_argument('--write-final',action='store_true');a=p.parse_args()
 root=a.root or pathlib.Path(__file__).resolve().parents[3]
 print(json.dumps(audit(root,a.write_final),ensure_ascii=True))

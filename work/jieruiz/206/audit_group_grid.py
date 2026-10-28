import datetime,hashlib,json,math,pathlib,statistics,struct,subprocess
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/group64-scale-issue206-20261028');W=R/'work/jieruiz/206';base=R/'qwen3/results/group_shared_20261028'
load=lambda p:json.loads(p.read_bytes());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sub=load(next(W.glob('GRID_SUBMISSION_*.json')));src=load(W/('GRID_SOURCE_'+sub['commit'][:8]+'.json'));D=base/sub['commit'][:12];groups={}
for n,h in src['files_sha256'].items():assert hashlib.sha256(subprocess.check_output(['git','show',src['commit']+':'+n],cwd=R)).hexdigest()==h
for i in range(3):
 P=D/'grid_refinement'/('shard'+str(i));done=load(P/'complete.json');assert done['status']=='completed' and done['cases']==10
 assert sha(P/'complete.json')==load(P/'complete.sha256.json')['sha256'];prov=load(P/'provenance.json');assert prov['source']==src
 log=(P/'validation.log').read_bytes();assert b'Ran 4 tests' in log and b'\nOK\n' in log
 for n,h in done['documents'].items():
  assert sha(P/n)==h and load((P/n).with_suffix('.sha256.json'))['sha256']==h
  if n=='provenance.json':continue
  x=load(P/n);assert x['status']=='completed' and x['scored_tokens']==1024 and len(x['rows'])==8
  assert x['provenance_sha256']==sha(P/'provenance.json') and set(x['all_layer_calls'])=={8} and len(x['all_layer_calls'])==36 and set(x['all_layer_input_tokens'])=={17400}
  assert math.isclose(math.exp(x['nll_sum']/1024),x['perplexity'],rel_tol=1e-12)
  pos=[v for z in x['rows'] for v in range(z['first_target'],z['last_target_exclusive'])];assert hashlib.sha256(b''.join(struct.pack('<q',v) for v in pos)).hexdigest()==x['target_positions_sha256']=='b8b6365968ca1937c7c332dee67df82f287db6de3f0933c21800f4732042ab1a'
  if x['case']=='bf16':assert x['perplexity']==13.566049199388152;continue
  assert x['seed'] in (0,1,2) and x['grid']==prov['grid'] and x['NL_samples']==128 and x['GU_samples']==64
  for d in x['diagnostics'].values():
   assert d['gu_law']=='fixed' and d['nonlinear_T']==128
   for stage in d['stages'].values():
    if stage['shared_group64']:assert stage['mixed_scale_groups']==0
  key=('x'.join(map(str,x['grid'])),x['variant']);groups.setdefault(key,[]).append(x)
assert len(groups)==9 and all(sorted(x['seed'] for x in rows)==[0,1,2] for rows in groups.values())
rows=[]
for (grid,v),xs in sorted(groups.items()):
 p=[x['perplexity'] for x in sorted(xs,key=lambda x:x['seed'])];rows.append(dict(grid=grid,variant=v,ppl=p,mean=statistics.mean(p),sd=statistics.stdev(p),event_probability=statistics.mean(d['mean_AND_probability'] for x in xs for d in x['diagnostics'].values()),zero_event_fraction=statistics.mean(d['zero_AND_count_fraction'] for x in xs for d in x['diagnostics'].values())))
out=dict(status='completed',weight_policy='LEGACY absmax/127,NOT clarifiedPoTweight target',source=src['commit'],scores=30,unique=28,checks=4,protocol='1024 suffix targets,not fullWT2',rows=rows,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(base/'LEGACY_GRID_SUMMARY.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(rows))

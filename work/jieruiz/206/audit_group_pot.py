import datetime,hashlib,json,math,pathlib,statistics,struct,subprocess
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/group64-scale-issue206-20261028');W=R/'work/jieruiz/206';base=R/'qwen3/results/group_shared_20261028'
load=lambda p:json.loads(p.read_bytes());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sub=load(max(W.glob('POT_SUBMISSION_*.json'),key=lambda p:p.stat().st_mtime));src=load(W/('POT_SOURCE_'+sub['commit'][:8]+'.json'));D=base/sub['commit'][:12]
assert len(src['files_sha256'])==69
for n,h in src['files_sha256'].items():assert hashlib.sha256(subprocess.check_output(['git','show',src['commit']+':'+n],cwd=R)).hexdigest()==h,n
log=(D/'validation.log').read_bytes();assert b'Ran 34 tests' in log and b'\nOK\n' in log
cases={};physical=0;seals=[]
for i in range(4):
 P=D/'pot_weight'/('shard'+str(i));done=load(P/'complete.json');assert done['status']=='completed' and done['cases']==(9 if i==0 else 8) and done['shard']==i
 assert sha(P/'complete.json')==load(P/'complete.sha256.json')['sha256'];prov=load(P/'provenance.json');assert prov['source']==src
 assert prov['config_sha256']=='246f41e73a114b08e2cf787ca7335df1dd0b1bceee091c88026141a830aff2dc' and prov['prepared_sha256']=='f8c6c0a754f5c7fff4a5afa0d054b4ca59493efde6ef5b742515d9ed58f054db'
 assert prov['data']['wiki.train.raw']['sha256']=='6707892fa3788b5ab9ed78ab5ff37d9fe825f6011a2ad4fcd6a6d467f0e7da57' and prov['data']['wiki.test.raw']['sha256']=='173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08'
 for n,h in done['documents'].items():
  assert sha(P/n)==h and load((P/n).with_suffix('.sha256.json'))['sha256']==h
  if n=='provenance.json':continue
  x=load(P/n);physical+=1;assert x['status']=='completed' and x['scored_tokens']==1024 and len(x['rows'])==8
  assert x['provenance_sha256']==sha(P/'provenance.json') and set(x['all_layer_calls'])=={8} and len(x['all_layer_calls'])==36 and set(x['all_layer_input_tokens'])=={17400}
  assert math.isclose(math.exp(x['nll_sum']/1024),x['perplexity'],rel_tol=1e-12)
  assert abs(sum(z['nll_sum'] for z in x['rows'])-x['nll_sum'])<1e-8
  pos=[v for z in x['rows'] for v in range(z['first_target'],z['last_target_exclusive'])];assert hashlib.sha256(b''.join(struct.pack('<q',v) for v in pos)).hexdigest()==x['target_positions_sha256']=='b8b6365968ca1937c7c332dee67df82f287db6de3f0933c21800f4732042ab1a'
  if x['case']=='bf16':assert x['perplexity']==13.566049199388152
  else:
   assert len(x['diagnostics'])==36
   for d in x['diagnostics'].values():
    assert d['weight_policy']==x['weight_policy']
    if d['weight_policy']=='pot64':
     for m in ('Wg','Wu','Wd'):
      assert d['weight_metrics'][m]['step_is_pot'] and d['weight_metrics'][m]['tile']==[64,64] and d['weight_metrics'][m]['tile_count']==6080
     assert d['weight_metrics']['Wd_restoration']['exact_pot_coeff'] and d['weight_metrics']['Wd_restoration']['exponent_span_max']<=15
    if not d.get('weight_only_exact_silu',False):
     assert d['gu_law']=='fixed' and d['gu_T']==64
     if x['control_only']:assert not d['hardware_candidate'] and d['nonlinear_T'] is None
     else:assert d['nonlinear_T']==128
     for stage in d['stages'].values():
      if stage['shared_group64']:assert stage['mixed_scale_groups']==0
  if x['case'] in cases:assert cases[x['case']]['perplexity']==x['perplexity']
  else:cases[x['case']]=x
 seals.append(dict(shard=i,complete_sha256=sha(P/'complete.json'),execution_log_sha256=sha(P/'execution.log')))
assert physical==33 and len(cases)==27
rows=[]
for v in ('lane','x_max','gu_max','all_max'):
 xs=[cases['finiteNL_'+v+'_s'+str(s)] for s in (0,1,2)];ms=[cases['meanNL_'+v+'_s'+str(s)] for s in (0,1,2)]
 p=[x['perplexity'] for x in xs];mp=[x['perplexity'] for x in ms]
 rows.append(dict(variant=v,finite_ppl=p,finite_mean=statistics.mean(p),finite_sd=statistics.stdev(p),conditional_mean_ppl=mp,conditional_mean_mean=statistics.mean(mp),conditional_mean_sd=statistics.stdev(mp),
   event_probability=statistics.mean(d['mean_AND_probability'] for x in xs for d in x['diagnostics'].values()),zero_event_fraction=statistics.mean(d['zero_AND_count_fraction'] for x in xs for d in x['diagnostics'].values())))
weights={m:dict(unweighted_layer_mean_nmse=statistics.mean(d['weight_metrics'][m]['NMSE'] for d in cases['pot_W8_only']['diagnostics'].values()),total_tiles=sum(d['weight_metrics'][m]['tile_count'] for d in cases['pot_W8_only']['diagnostics'].values())) for m in ('Wg','Wu','Wd')}
out=dict(status='completed',source=src['commit'],scores=physical,unique=len(cases),checks=34,seals=seals,model='Qwen/Qwen3-4B posttrained',protocol='1024 suffix targets,not full WT2',BF16=cases['bf16']['perplexity'],legacy_weight_only=cases['legacy_W8_only']['perplexity'],pot_weight_only=cases['pot_W8_only']['perplexity'],weight_quantization=weights,rows=rows,mean_diagnostic_not_hardware=True,GU_restoration='FP32 numerical oracle;not fullchain bittrue',updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(base/'POT_WEIGHT_SUMMARY.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(out))

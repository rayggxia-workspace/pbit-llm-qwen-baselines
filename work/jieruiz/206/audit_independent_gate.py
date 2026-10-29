import datetime,hashlib,json,math,pathlib,statistics,struct,subprocess
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/group64-scale-issue206-20261028');W=R/'work/jieruiz/206';B=R/'qwen3/results/group_shared_20261028'
load=lambda p:json.loads(p.read_bytes());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sub=load(max(W.glob('GATE_SUBMISSION_*.json'),key=lambda p:p.stat().st_mtime));src=load(W/('GATE_SOURCE_'+sub['commit'][:8]+'.json'));D=B/sub['commit'][:12]
assert len(src['files_sha256'])==72
for n,h in src['files_sha256'].items():assert hashlib.sha256(subprocess.check_output(['git','show',src['commit']+':'+n],cwd=R)).hexdigest()==h
old=load(W/'POT_SOURCE_aa43d00d.json');assert all(src['files_sha256'][n]==h for n,h in old['files_sha256'].items()),'old modules changed'
assert b'Ran 41 tests' in (D/'validation.log').read_bytes() and b'\nOK\n' in (D/'validation.log').read_bytes()
cases={};total=0;seals=[]
for i in range(3):
 P=D/'independent_gate'/('shard'+str(i));done=load(P/'complete.json');assert done['status']=='completed' and done['cases']==(16,13,7)[i]
 assert sha(P/'complete.json')==load(P/'complete.sha256.json')['sha256'];prov=load(P/'provenance.json');assert prov['source']==src
 assert prov['config_sha256']=='246f41e73a114b08e2cf787ca7335df1dd0b1bceee091c88026141a830aff2dc' and prov['prepared_sha256']=='f8c6c0a754f5c7fff4a5afa0d054b4ca59493efde6ef5b742515d9ed58f054db'
 for n,h in done['documents'].items():
  assert sha(P/n)==h and load((P/n).with_suffix('.sha256.json'))['sha256']==h
  if n=='provenance.json':continue
  x=load(P/n);total+=1
  assert x['status']=='completed' and x['scored_tokens']==1024 and len(x['rows'])==8
  assert x['provenance_sha256']==sha(P/'provenance.json') and len(x['all_layer_calls'])==36 and set(x['all_layer_calls'])=={8} and set(x['all_layer_input_tokens'])=={17400}
  assert math.isclose(math.exp(x['nll_sum']/1024),x['perplexity'],rel_tol=1e-12)
  pos=[v for z in x['rows'] for v in range(z['first_target'],z['last_target_exclusive'])];assert hashlib.sha256(b''.join(struct.pack('<q',v) for v in pos)).hexdigest()==x['target_positions_sha256']=='b8b6365968ca1937c7c332dee67df82f287db6de3f0933c21800f4732042ab1a'
  if x['case']=='bf16':assert x['perplexity']==13.566049199388152
  else:
   assert len(x['diagnostics'])==36 and x['GU_samples']==64
   for d in x['diagnostics'].values():
    assert d['gate_mode']==x['gate_mode'] and d['amplitude_policy']==x['amplitude_policy'] and d['gu_T']==64
    if x['gate_mode']=='original_g':assert 'before amplitude clipping' in d['sigmoid']
    for st in d['stages'].values():assert st['shared_group64'] and st['mixed_scale_groups']==0
    assert d['stages']['x']['clip_fraction']>=0 and d['weight_policy']=='pot64'
  if x['case'] in cases:assert x['perplexity']==cases[x['case']]['perplexity']
  else:cases[x['case']]=x
 seals.append(dict(shard=i,complete_sha256=sha(P/'complete.json')))
assert total==36 and len(cases)==34
expected=[69.67140048601013,63.845430401311084,70.10287010403827]
assert [cases['old_coupled_s'+str(s)]['perplexity'] for s in (0,1,2)]==expected
rows=[]
for policy in ('max','g_trim1','u_trim1','both_trim1','both_trim4'):
 fs=[cases['finiteNL_'+policy+'_s'+str(s)] for s in (0,1,2)];ms=[cases['meanNL_'+policy+'_s'+str(s)] for s in (0,1,2)];p=[x['perplexity'] for x in fs];mp=[x['perplexity'] for x in ms]
 rows.append(dict(policy=policy,finite_ppl=p,finite_mean=statistics.mean(p),finite_sd=statistics.stdev(p),conditional_mean_ppl=mp,conditional_mean_mean=statistics.mean(mp),
  mean_AND_probability=statistics.mean(d['mean_AND_probability'] for x in fs for d in x['diagnostics'].values()),zero_AND_fraction=statistics.mean(d['zero_AND_count_fraction'] for x in fs for d in x['diagnostics'].values()),
  g_clip=statistics.mean(d['stages']['g']['clip_fraction'] for x in fs for d in x['diagnostics'].values()),u_clip=statistics.mean(d['stages']['u']['clip_fraction'] for x in fs for d in x['diagnostics'].values()),gate_changed_fraction=statistics.mean(d['gate_probability_changed_fraction'] for x in fs for d in x['diagnostics'].values())))
out=dict(status='completed',source=src['commit'],source_blobs=72,old69_unchanged=True,scores=total,unique=len(cases),checks=41,seals=seals,BF16=13.566049199388152,old_coupled_ppl=expected,old_coupled_mean=statistics.mean(expected),rows=rows,protocol='1024 suffix targets,not full WT2',mean_diagnostic_not_hardware=True,unchanged='x groupmax,PoTW8 GU64 NL128 accurateSDPA',no_new_scale_calibration=True,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(B/'INDEPENDENT_GATE_SUMMARY.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(out))

import datetime,gzip,hashlib,json,math,pathlib,statistics,struct,subprocess
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/group64-scale-issue206-20261028');W=R/'work/jieruiz/206';B=R/'qwen3/results/group_shared_20261028'
def raw(p):return p.read_bytes() if p.exists() else gzip.decompress(p.with_suffix(p.suffix+'.gz').read_bytes())
load=lambda p:json.loads(raw(p));sha=lambda p:hashlib.sha256(raw(p)).hexdigest()
sub=load(max(W.glob('GROUP_SWEEP_SUBMISSION_*.json'),key=lambda p:p.stat().st_mtime));src=load(W/('GROUP_SWEEP_SOURCE_'+sub['commit'][:8]+'.json'));D=B/sub['commit'][:12]
assert len(src['files_sha256'])==82
for n,h in src['files_sha256'].items():assert hashlib.sha256(subprocess.check_output(['git','show',src['commit']+':'+n],cwd=R)).hexdigest()==h
old=load(W/'RECAL_SOURCE_e8888a26.json');assert all(src['files_sha256'][n]==h for n,h in old['files_sha256'].items())
assert b'Ran 71 tests' in raw(D/'cpu_validation.log') and b'\nOK (skipped=10)\n' in raw(D/'cpu_validation.log')
oldcal=load(B/'e8888a26dace/recalibration/calibration/tables.json');assert sha(B/'e8888a26dace/recalibration/calibration/tables.json')=='9a26ddde7c2ed935e652cefbadd5bf63b9f5b4f23a269775f47d38f0963987f7'
cases={};physical=0;seals=[];gate=[]
def check_seal(p,count):
 done=load(p/'complete.json');assert done['status']=='completed' and done['cases']==count
 assert sha(p/'complete.json')==load(p/'complete.sha256.json')['sha256']
 for n,h in done['documents'].items():assert sha(p/n)==h and load((p/n).with_suffix('.sha256.json'))['sha256']==h
 pr=load(p/'provenance.json');assert pr['source']==src
 assert pr['config_sha256']=='246f41e73a114b08e2cf787ca7335df1dd0b1bceee091c88026141a830aff2dc'
 assert pr['prepared_sha256']=='f8c6c0a754f5c7fff4a5afa0d054b4ca59493efde6ef5b742515d9ed58f054db'
 assert pr['model']['revision']=='1cfa9a7208912126459214e8b04321603b3df60c'
 assert pr['old_calibration_sha256']==sub['scope']['old_calibration_sha256']
 return done

P=D/'group_size_levels/gate';gd=check_seal(P,3);assert b'Ran 71 tests' in raw(P/'execution.log') and b'\nOK\n' in raw(P/'execution.log')
assert load(P/'bf16.json')['perplexity']==13.566049199388152
assert load(P/'old_risk4_s0.json')['perplexity']==18.20000779048508
assert load(P/'pilot_g16_b8.json')['scored_tokens']==8 and set(load(P/'pilot_g16_b8.json')['all_layer_calls'])=={2}
for i,(group,count) in enumerate(sub['schemes']):
 P=D/'group_size_levels'/('shard'+str(i));done=check_seal(P,6)
 for n in done['documents']:
  if n=='provenance.json':continue
  x=load(P/n);physical+=1
  assert x['status']=='completed' and x['scored_tokens']==1024 and len(x['rows'])==8
  assert len(x['all_layer_calls'])==36 and set(x['all_layer_calls'])=={8} and set(x['all_layer_input_tokens'])=={17400}
  assert x['provenance_sha256']==sha(P/'provenance.json')
  assert math.isclose(math.exp(x['nll_sum']/1024),x['perplexity'],rel_tol=1e-12)
  positions=[v for r in x['rows'] for v in range(r['first_target'],r['last_target_exclusive'])]
  assert hashlib.sha256(b''.join(struct.pack('<q',v) for v in positions)).hexdigest()==x['target_positions_sha256']=='b8b6365968ca1937c7c332dee67df82f287db6de3f0933c21800f4732042ab1a'
  if x['case']=='bf16':assert x['perplexity']==13.566049199388152
  elif x['case'].startswith('old_risk4_s'):
   assert x['perplexity']==[18.20000779048508,17.89494970067286,17.669679075660085][i%3]
  else:
   assert x['nonlinear_group_size']==group and x['nonlinear_scale_count']==count and x['input_group_size']==64
   assert x['old_calibration_sha256']==sub['scope']['old_calibration_sha256'] and len(x['diagnostics'])==36
   for layer,d in x['diagnostics'].items():
    assert d['input_shared_group']==64 and d['nonlinear_shared_group']==group and d['nonlinear_levels']==count and d['calibration_refitted'] is False
    assert d['weight_policy']=='pot64' and d['catalog_accumulator_bound_bits']<=64
    assert d['stages']['x']['shared_group64'] and d['stages']['x']['mixed_scale_groups']==0
    e=oldcal['tables']['risk4'][layer]
    for name in ('g','u'):
     expected=[]
     for oldlevels in e[name]:
      levels=oldlevels if count==4 else list(range(oldlevels[-1]-7,oldlevels[-1]+1))
      assert set(oldlevels)<=set(levels) and levels[-1]==oldlevels[-1]
      expected.extend([levels]*(64//group))
     assert d[name+'_exponents']==expected
     st=d['stages'][name];assert st['shared_group_size']==group and st['mixed_scale_groups']==0
     assert len(st['scale_hist'])==count and sum(st['scale_hist'])==st['elements']
  if x['case'] in cases:assert x['perplexity']==cases[x['case']]['perplexity']
  else:cases[x['case']]=x
 seals.append(dict(shard=i,complete_sha256=sha(P/'complete.json')))
assert physical==36 and len(cases)==28
canonical={}
for name,value in cases.items():
 key=name.replace('old_risk4_s','finiteNL_g64_b4_s')
 if key in canonical:assert canonical[key]['perplexity']==value['perplexity']
 else:canonical[key]=value
assert len(canonical)==25
rows=[]
for group,count in sub['schemes']:
 name=f'g{group}_b{count}';fs=[cases['finiteNL_'+name+'_s'+str(s)] for s in (0,1,2)];ms=cases['meanNL_'+name+'_s0'];p=[x['perplexity'] for x in fs]
 rows.append(dict(scheme=name,group=group,levels=count,finite_ppl=p,finite_mean=statistics.mean(p),finite_sd=statistics.stdev(p),
  conditional_mean_seed0=ms['perplexity'],relative_to_g64b4=statistics.mean(p)/17.921545522272677-1,
  scale_index_bits_per_active_FFN=2*(9728//group)*int(math.log2(count)),
  mean_AND_probability=statistics.mean(d['mean_AND_probability'] for x in fs for d in x['diagnostics'].values()),
  zero_AND_fraction=statistics.mean(d['zero_AND_count_fraction'] for x in fs for d in x['diagnostics'].values()),
  g_clip=statistics.mean(d['stages']['g']['clip_fraction'] for x in fs for d in x['diagnostics'].values()),
  u_clip=statistics.mean(d['stages']['u']['clip_fraction'] for x in fs for d in x['diagnostics'].values()),
  worst_accumulator_bound_bits=max(d['catalog_accumulator_bound_bits'] for x in fs for d in x['diagnostics'].values())))
assert rows[0]['finite_mean']==17.921545522272677
out=dict(status='completed',source=src['commit'],source_blobs=82,old75_unchanged=True,CPU_tests=71,CPU_skipped=10,GPU_tests=71,
 main_physical=physical,main_unique_labels=28,main_unique_config_seed=25,duplicate_control_aliases=3,gate_scores=3,seals=seals,BF16=13.566049199388152,previous_best=17.921545522272677,
 closest_per_element_gu_reference=16.27404401852748,rows=rows,protocol='1024 suffix targets,not fullWT2',
 no_refit=True,no_PPA_or_TLM_change=True,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(B/'GROUP_SIZE_LEVELS_SUMMARY.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(out))

import datetime,gzip,hashlib,json,math,pathlib,statistics,struct,subprocess
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/group64-scale-issue206-20261028');W=R/'work/jieruiz/206';B=R/'qwen3/results/group_shared_20261028'
def raw(p):return p.read_bytes() if p.exists() else gzip.decompress(p.with_suffix(p.suffix+'.gz').read_bytes())
load=lambda p:json.loads(raw(p));sha=lambda p:hashlib.sha256(raw(p)).hexdigest()
sub=load(max(W.glob('TUNE_SUBMISSION_*.json'),key=lambda p:p.stat().st_mtime));src=load(W/('TUNE_SOURCE_'+sub['commit'][:8]+'.json'));D=B/sub['commit'][:12]
assert len(src['files_sha256'])==78
for n,h in src['files_sha256'].items():assert hashlib.sha256(subprocess.check_output(['git','show',src['commit']+':'+n],cwd=R)).hexdigest()==h
old=load(W/'RECAL_SOURCE_e8888a26.json');assert all(src['files_sha256'][n]==h for n,h in old['files_sha256'].items()),'old75 modules changed'
assert b'Ran 61 tests' in raw(D/'validation.log') and b'\nOK\n' in raw(D/'validation.log')
cal=D/'tune4/calibration';done=load(cal/'complete.json');assert done['status']=='completed';assert sha(cal/'complete.json')==load(cal/'complete.sha256.json')['sha256']
for n,h in done['documents'].items():assert sha(cal/n)==h and load((cal/n).with_suffix('.sha256.json'))['sha256']==h
cp=load(cal/'provenance.json');tables=load(cal/'tables.json');assert cp['source']==src and tables['provenance_sha256']==sha(cal/'provenance.json')
assert tables['fit_rows']==768 and tables['validation_rows']==256 and len(tables['train_starts'])==32 and tables['window_length']==2048 and len(set(tables['selected_rows']))==32
assert tables['selected_rows'][0]==1024 and tables['selected_rows'][-1]==2047 and len(tables['capture_sha256'])==36
schemes=('large_diag4','large_gram4','large_gram4_threshold','large_gram4_threshold_bias')
assert set(tables['tables'])==set(schemes)
for name,layers in tables['tables'].items():
 assert len(layers)==36
 for e in layers.values():
  for k in ('g','u'):assert len(e[k])==152 and all(len(v)==4 and v==sorted(set(v)) and all(isinstance(x,int) for x in v) for v in e[k])
  for k in ('g_delta','u_delta'):assert len(e[k])==152 and set(e[k])<=set((-1,0,1))
  if name in ('large_diag4','large_gram4'):assert set(e['g_delta'])=={0} and set(e['u_delta'])=={0}
  assert e['accumulator_bound_bits']<=64 and e['coefficient_span']<=15
assert load(cal/'bf16.json')['perplexity']==13.566049199388152
cases={};physical=0;seals=[]
for i in range(4):
 P=D/'tune4'/('shard'+str(i));done=load(P/'complete.json');assert done['status']=='completed' and done['cases']==8
 assert sha(P/'complete.json')==load(P/'complete.sha256.json')['sha256'];p=load(P/'provenance.json');assert p['source']==src
 assert p['config_sha256']=='246f41e73a114b08e2cf787ca7335df1dd0b1bceee091c88026141a830aff2dc' and p['prepared_sha256']=='f8c6c0a754f5c7fff4a5afa0d054b4ca59493efde6ef5b742515d9ed58f054db'
 assert p['old_calibration_sha256']=='9a26ddde7c2ed935e652cefbadd5bf63b9f5b4f23a269775f47d38f0963987f7'
 for n,h in done['documents'].items():
  assert sha(P/n)==h and load((P/n).with_suffix('.sha256.json'))['sha256']==h
  if n=='provenance.json':continue
  x=load(P/n);physical+=1;assert x['status']=='completed' and x['scored_tokens']==1024 and len(x['rows'])==8
  assert x['provenance_sha256']==sha(P/'provenance.json') and len(x['all_layer_calls'])==36 and set(x['all_layer_calls'])=={8} and set(x['all_layer_input_tokens'])=={17400}
  assert math.isclose(math.exp(x['nll_sum']/1024),x['perplexity'],rel_tol=1e-12)
  pos=[v for z in x['rows'] for v in range(z['first_target'],z['last_target_exclusive'])];assert hashlib.sha256(b''.join(struct.pack('<q',v) for v in pos)).hexdigest()==x['target_positions_sha256']=='b8b6365968ca1937c7c332dee67df82f287db6de3f0933c21800f4732042ab1a'
  if x['case']=='bf16':assert x['perplexity']==13.566049199388152
  elif x['case'].startswith('old_risk4_s'):assert x['perplexity']==[18.20000779048508,17.89494970067286,17.669679075660085][i%3]
  else:
   assert x['calibration_sha256']==sha(cal/'tables.json') and len(x['diagnostics'])==36 and x['GU_samples']==64
   for lid,d in x['diagnostics'].items():
    e=tables['tables'][x['scheme']][lid]
    for k in ('g','u'):assert d[k+'_exponents']==e[k] and d['threshold_'+k+'_delta']==e[k+'_delta']
    assert d['catalog_accumulator_bound_bits']<=64 and d['weight_policy']=='pot64'
    for st in d['stages'].values():assert st['shared_group64'] and st['mixed_scale_groups']==0
  if x['case'] in cases:assert x['perplexity']==cases[x['case']]['perplexity']
  else:cases[x['case']]=x
 seals.append(dict(shard=i,complete_sha256=sha(P/'complete.json')))
assert physical==32 and len(cases)==28
rows=[]
for name in schemes:
 fs=[cases['finiteNL_'+name+'_s'+str(s)] for s in (0,1,2)];ms=[cases['meanNL_'+name+'_s'+str(s)] for s in (0,1,2)];p=[x['perplexity'] for x in fs];mp=[x['perplexity'] for x in ms]
 delta={k:{str(v):sum(e[k+'_delta'].count(v) for e in tables['tables'][name].values()) for v in (-1,0,1)} for k in ('g','u')}
 rows.append(dict(scheme=name,finite_ppl=p,finite_mean=statistics.mean(p),finite_sd=statistics.stdev(p),conditional_mean_ppl=mp,conditional_mean_mean=statistics.mean(mp),
   fit_objective=sum(e['risk']['fit'] for e in tables['tables'][name].values()),validation_objective=sum(e['risk']['validation'] for e in tables['tables'][name].values()),
   fit_gram_total=sum(e['risk']['fit_gram_total'] for e in tables['tables'][name].values()),validation_gram_total=sum(e['risk']['validation_gram_total'] for e in tables['tables'][name].values()),threshold_histogram=delta,
   mean_AND_probability=statistics.mean(d['mean_AND_probability'] for x in fs for d in x['diagnostics'].values()),zero_AND_fraction=statistics.mean(d['zero_AND_count_fraction'] for x in fs for d in x['diagnostics'].values()),
   g_clip=statistics.mean(d['stages']['g']['clip_fraction'] for x in fs for d in x['diagnostics'].values()),u_clip=statistics.mean(d['stages']['u']['clip_fraction'] for x in fs for d in x['diagnostics'].values())))
out=dict(status='completed',source=src['commit'],source_blobs=78,old75_unchanged=True,checks=61,scores=32,unique=28,calibration_extra_bf16=1,seals=seals,calibration_sha256=sha(cal/'tables.json'),BF16=13.566049199388152,previous_risk4=statistics.mean(cases['old_risk4_s'+str(s)]['perplexity'] for s in (0,1,2)),closest_per_element_gu_reference=16.27404401852748,rows=rows,protocol='1024 suffix targets,not full WT2',train_only_calibration=True,within_group_gram_omits_cross_group_terms=True,initial_unique_count_corrected='29 ->28 because duplicate oldrisk4seed0 control',updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
sanity_record=W/'TUNE_SANITY_COLLECTION.json'
if sanity_record.exists():
 sr=load(sanity_record)
 if sr['status']=='completed':
  sp=D/('sanity-'+sr['probe_commit'][:12]);sd=load(sp/'complete.json')
  for n,h in sd['documents'].items():assert sha(sp/n)==h and load((sp/n).with_suffix('.sha256.json'))['sha256']==h
  sy=load(sp/'sanity.json');assert sy['foundation_source']==src and len(sy['rows'])==16 and all(r['direct_mean_equal'] for r in sy['rows']) and sum(r['parent_finite_equal'] is True for r in sy['rows'])==8
  assert hashlib.sha256(subprocess.check_output(['git','show',sr['probe_commit']+':qwen3/group_shared/tune_sanity.py'],cwd=R)).hexdigest()==sy['probe_source_sha256']
  out['representative_numeric_crosscheck']=dict(status='completed',probe_source=sr['probe_commit'],job=sr['job'],finite_parent_equal=8,direct_mean_equal=16,rows_per_check=16,layers=[0,12,24,35],sanity_sha256=sha(sp/'sanity.json'))
(B/'TUNE4_SUMMARY.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(out))

import datetime,gzip,hashlib,json,math,pathlib,statistics,struct,subprocess
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/group64-scale-issue206-20261028');W=R/'work/jieruiz/206';B=R/'qwen3/results/group_shared_20261028'
def raw(p):return p.read_bytes() if p.exists() else gzip.decompress(p.with_suffix(p.suffix+'.gz').read_bytes())
load=lambda p:json.loads(raw(p));sha=lambda p:hashlib.sha256(raw(p)).hexdigest()
sub=load(max(W.glob('RECAL_SUBMISSION_*.json'),key=lambda p:p.stat().st_mtime));src=load(W/('RECAL_SOURCE_'+sub['commit'][:8]+'.json'));D=B/sub['commit'][:12]
assert len(src['files_sha256'])==75
for n,h in src['files_sha256'].items():assert hashlib.sha256(subprocess.check_output(['git','show',src['commit']+':'+n],cwd=R)).hexdigest()==h
old=load(W/'GATE_SOURCE_32b5ed92.json');assert all(src['files_sha256'][n]==h for n,h in old['files_sha256'].items()),'old72 modules changed'
assert b'Ran 52 tests' in raw(D/'validation.log') and b'\nOK\n' in raw(D/'validation.log')
cal=D/'recalibration/calibration';cs=load(cal/'complete.json');assert cs['status']=='completed';assert sha(cal/'complete.json')==load(cal/'complete.sha256.json')['sha256']
for n,h in cs['documents'].items():assert sha(cal/n)==h and load((cal/n).with_suffix('.sha256.json'))['sha256']==h
cp=load(cal/'provenance.json');tab=load(cal/'tables.json');assert cp['source']==src and tab['provenance_sha256']==sha(cal/'provenance.json')
assert tab['fit_rows']==192 and tab['validation_rows']==64 and len(tab['train_starts'])==16 and tab['train_window_length']==512 and len(set(tab['selected_rows']))==16
assert tab['selected_rows'][0]==0 and tab['selected_rows'][-1]==511 and len(tab['capture_sha256'])==36
for name,layers in tab['tables'].items():
 assert len(layers)==36
 for entry in layers.values():
  for key in ('g','u'):
   assert len(entry[key])==152 and all(len(a)==4 and a==sorted(set(a)) and all(isinstance(e,int) for e in a) for a in entry[key])
  assert entry['Wd_coefficient_span']<=15 and entry['accumulator_bound_bits']<=64
assert load(cal/'bf16.json')['perplexity']==13.566049199388152
cases={};physical=0;seals=[]
for i in range(3):
 P=D/'recalibration'/('shard'+str(i));done=load(P/'complete.json');assert done['status']=='completed' and done['cases']==8
 assert sha(P/'complete.json')==load(P/'complete.sha256.json')['sha256'];prov=load(P/'provenance.json');assert prov['source']==src
 assert prov['config_sha256']=='246f41e73a114b08e2cf787ca7335df1dd0b1bceee091c88026141a830aff2dc' and prov['prepared_sha256']=='f8c6c0a754f5c7fff4a5afa0d054b4ca59493efde6ef5b742515d9ed58f054db'
 for n,h in done['documents'].items():
  assert sha(P/n)==h and load((P/n).with_suffix('.sha256.json'))['sha256']==h
  if n=='provenance.json':continue
  x=load(P/n);physical+=1;assert x['status']=='completed' and x['scored_tokens']==1024 and len(x['rows'])==8
  assert x['provenance_sha256']==sha(P/'provenance.json') and len(x['all_layer_calls'])==36 and set(x['all_layer_calls'])=={8} and set(x['all_layer_input_tokens'])=={17400}
  assert math.isclose(math.exp(x['nll_sum']/1024),x['perplexity'],rel_tol=1e-12)
  pos=[v for z in x['rows'] for v in range(z['first_target'],z['last_target_exclusive'])];assert hashlib.sha256(b''.join(struct.pack('<q',v) for v in pos)).hexdigest()==x['target_positions_sha256']=='b8b6365968ca1937c7c332dee67df82f287db6de3f0933c21800f4732042ab1a'
  if x['case']=='bf16':assert x['perplexity']==13.566049199388152
  elif x['case'].startswith('old_table_s'):assert x['perplexity']==[73.30699083927549,58.943168399133974,62.01589453860189][i]
  else:
   assert x['calibration_sha256']==sha(cal/'tables.json') and len(x['diagnostics'])==36 and x['GU_samples']==64
   for lid,d in x['diagnostics'].items():
    assert d['g_exponents']==tab['tables'][x['scheme']][lid]['g'] and d['u_exponents']==tab['tables'][x['scheme']][lid]['u']
    assert d['catalog_accumulator_bound_bits']<=64 and d['weight_policy']=='pot64'
    for st in d['stages'].values():assert st['shared_group64'] and st['mixed_scale_groups']==0
  if x['case'] in cases:assert cases[x['case']]['perplexity']==x['perplexity']
  else:cases[x['case']]=x
 seals.append(dict(shard=i,complete_sha256=sha(P/'complete.json')))
assert physical==24 and len(cases)==22
rows=[]
for name in ('dense2','risk4','risk4_active'):
 fs=[cases['finiteNL_'+name+'_s'+str(s)] for s in (0,1,2)];ms=[cases['meanNL_'+name+'_s'+str(s)] for s in (0,1,2)]
 p=[x['perplexity'] for x in fs];mp=[x['perplexity'] for x in ms]
 rows.append(dict(scheme=name,finite_ppl=p,finite_mean=statistics.mean(p),finite_sd=statistics.stdev(p),conditional_mean_ppl=mp,conditional_mean_mean=statistics.mean(mp),
   calibration_fit_risk=sum(e['risk']['fit'] for e in tab['tables'][name].values()),calibration_validation_risk=sum(e['risk']['validation'] for e in tab['tables'][name].values()),
   mean_AND_probability=statistics.mean(d['mean_AND_probability'] for x in fs for d in x['diagnostics'].values()),zero_AND_fraction=statistics.mean(d['zero_AND_count_fraction'] for x in fs for d in x['diagnostics'].values()),
   g_clip=statistics.mean(d['stages']['g']['clip_fraction'] for x in fs for d in x['diagnostics'].values()),u_clip=statistics.mean(d['stages']['u']['clip_fraction'] for x in fs for d in x['diagnostics'].values())))
out=dict(status='completed',source=src['commit'],source_blobs=75,old72_unchanged=True,checks=52,scores=24,unique=22,calibration_extra_bf16=1,seals=seals,calibration_sha256=sha(cal/'tables.json'),BF16=13.566049199388152,old_table_normal_g=statistics.mean(cases['old_table_s'+str(s)]['perplexity'] for s in (0,1,2)),per_element_pot_reference=15.69672197640577,rows=rows,protocol='1024 suffix targets,not full WT2',selection_uses_train_only=True,teacher_input_calibration=True,risk_is_diagonal_proxy_not_full_Wd_MSE=True,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(B/'RECALIBRATION_SUMMARY.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(out))

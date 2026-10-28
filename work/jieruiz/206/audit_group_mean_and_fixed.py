import datetime,hashlib,json,math,pathlib,statistics,struct,subprocess
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/group64-scale-issue206-20261028');W=R/'work/jieruiz/206';base=R/'qwen3/results/group_shared_20261028'
load=lambda p:json.loads(p.read_bytes())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sub=load(max(W.glob('MEAN_SUBMISSION_*.json'),key=lambda p:p.stat().st_mtime));src=load(W/('MEAN_SOURCE_'+sub['commit'][:8]+'.json'));D=base/sub['commit'][:12]
for n,h in src['files_sha256'].items():assert hashlib.sha256(subprocess.check_output(['git','show',src['commit']+':'+n],cwd=R)).hexdigest()==h,n
assert len(src['files_sha256'])==64
main_src=load(W/'SOURCE_4d6883b2.json')
assert all(src['files_sha256'][n]==h for n,h in main_src['files_sha256'].items()),'diagnosis changed frozen main code'
mean={};sealed=[]
for i in range(3):
 P=D/'mean_diagnostic'/('shard'+str(i));done=load(P/'complete.json');assert done['status']=='completed' and done['cases']==7 and done['shard']==i
 assert sha(P/'complete.json')==load(P/'complete.sha256.json')['sha256']
 for n,h in done['documents'].items():assert sha(P/n)==h and load((P/n).with_suffix('.sha256.json'))['sha256']==h
 prov=load(P/'provenance.json');assert prov['source']==src and prov['prepared_sha256']=='f8c6c0a754f5c7fff4a5afa0d054b4ca59493efde6ef5b742515d9ed58f054db'
 log=(P/'validation.log').read_bytes();assert b'Ran 2 tests' in log and b'\nOK\n' in log
 for n in done['documents']:
  if n=='provenance.json':continue
  x=load(P/n);assert x['status']=='completed' and x['scored_tokens']==1024 and len(x['rows'])==8
  assert x['provenance_sha256']==sha(P/'provenance.json')
  assert len(x['all_layer_calls'])==36 and set(x['all_layer_calls'])=={8} and set(x['all_layer_input_tokens'])=={17400}
  assert math.isclose(math.exp(x['nll_sum']/1024),x['perplexity'],rel_tol=1e-12)
  assert abs(sum(z['nll_sum'] for z in x['rows'])-x['nll_sum'])<1e-8
  pos=[v for z in x['rows'] for v in range(z['first_target'],z['last_target_exclusive'])]
  assert hashlib.sha256(b''.join(struct.pack('<q',v) for v in pos)).hexdigest()==x['target_positions_sha256']=='b8b6365968ca1937c7c332dee67df82f287db6de3f0933c21800f4732042ab1a'
  if x['case']=='bf16':assert x['perplexity']==13.566049199388152
  else:
   assert x['variant'] in prov['variants'] and x['seed'] in (0,1,2)
   assert x['control']=='nonlinear conditional mean;not finite sampler'
   for d in x['diagnostics'].values():
    assert not d['hardware_candidate'] and d['nonlinear_T'] is None and d['gu_T']==64 and d['gu_law']=='fixed'
   mean[x['variant'],x['seed']]=x
 sealed.append(dict(shard=i,complete_sha256=sha(P/'complete.json'),log_sha256=sha(P/'validation.log')))
assert len(mean)==18
P=base/'4d6883b24ad2/main/shard0';done=load(P/'complete.json');assert done['cases']==19
finite={}
for name,h in done['documents'].items():
 assert sha(P/name)==h
 if name not in ('bf16.json','provenance.json'):
  x=load(P/name);finite[x['variant'],x['seed']]=x
assert len(finite)==18
rows=[]
for v in ('lane','x_max','gu_max','all_max','all_trim1','all_trim4'):
 a=[finite[v,s]['perplexity'] for s in (0,1,2)];b=[mean[v,s]['perplexity'] for s in (0,1,2)]
 density=statistics.mean(d['mean_AND_probability'] for s in (0,1,2) for d in finite[v,s]['diagnostics'].values())
 zero=statistics.mean(d['zero_AND_count_fraction'] for s in (0,1,2) for d in finite[v,s]['diagnostics'].values())
 rows.append(dict(variant=v,fixed_finite_ppl=a,fixed_finite_mean=statistics.mean(a),fixed_finite_sd=statistics.stdev(a),
  nonlinear_mean_ppl=b,nonlinear_mean_mean=statistics.mean(b),nonlinear_mean_sd=statistics.stdev(b),
  event_probability=density,zero_AND_fraction=zero))
out=dict(status='fixed_complete_mean_diagnostic_complete_dual_pending',fixed_main_scores=19,mean_diagnostic_scores=21,mean_unique=19,
 main_source=main_src['commit'],diagnostic_source=src['commit'],common_execution_blobs_equal=62,mean_test_checks=2,mean_shards=sealed,
 protocol='1024 suffix targets,notfullWT2',diagnostic_not_hardware=True,BF16=13.566049199388152,rows=rows,
 updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(base/'FIXED_AND_MEAN_SUMMARY.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(out,ensure_ascii=True))

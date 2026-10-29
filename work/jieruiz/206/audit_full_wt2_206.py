"""Strict source/seal/coverage aggregation; suffix/pilot excluded from full scores."""
import hashlib,json,math,pathlib,statistics,sys
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/group64-scale-issue206-20261028');W=R/'work/jieruiz/206';sys.path.insert(0,str(R))
from qwen3.group_shared.full_plan import full_window_plan,verify_rows,window_seed
v=json.loads(sorted(W.glob('FULL_WT2_SUBMISSION_*.json'))[-1].read_bytes());src=json.loads((W/('FULL_WT2_SOURCE_'+v['commit'][:8]+'.json')).read_bytes());B=R/'qwen3/results/group_shared_20261028';D=B/v['commit'][:12]/'full_wt2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
expected=full_window_plan(299078,2048,1024);records={};manifest={}
for name in ['gate']+[f'task{i:02d}' for i in range(18)]:
 d=D/name
 if not (d/'complete.json').exists():continue
 seal=json.loads((d/'complete.json').read_bytes());assert seal['status']=='completed'
 for n,h in seal['documents'].items():
  p=d/n;assert sha(p)==h
  side=json.loads(p.with_suffix('.sha256.json').read_bytes());assert side['sha256']==h
  manifest[str(p.relative_to(B))]=h
 prov=json.loads((d/'provenance.json').read_bytes());assert prov['source']==src
 assert prov['phase']==('gate' if name=='gate' else 'eval')
 assert prov['old_calibration_sha256']=='9a26ddde7c2ed935e652cefbadd5bf63b9f5b4f23a269775f47d38f0963987f7'
 assert prov['config_sha256']=='246f41e73a114b08e2cf787ca7335df1dd0b1bceee091c88026141a830aff2dc'
 assert prov['full_config_sha256']==sha(R/'qwen3/group_shared/full_wt2_config.json')
 assert prov['prepared_sha256']=='f8c6c0a754f5c7fff4a5afa0d054b4ca59493efde6ef5b742515d9ed58f054db'
 assert prov['test_tokens']==299078 and prov['plan']==expected
 assert prov['model']['id']=='Qwen/Qwen3-4B' and prov['model']['revision']=='1cfa9a7208912126459214e8b04321603b3df60c'
 for split,h in [('wiki.train.raw','6707892fa3788b5ab9ed78ab5ff37d9fe825f6011a2ad4fcd6a6d467f0e7da57'),('wiki.test.raw','173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08')]:
  assert h in prov['data'][split].values()
 for n in ('bf16','g64b4'):
  r=json.loads((d/(n+'.json')).read_bytes());assert r['status']=='completed' and r['provenance_sha256']==sha(d/'provenance.json')
  wanted=[expected[0],expected[-1]] if name=='gate' else expected[len(expected)*prov['part']//6:len(expected)*(prov['part']+1)//6]
  s=verify_rows(r['rows'],wanted);assert s['nll_sum']==r['nll_sum'] and s['perplexity']==r['perplexity'] and s['scored_tokens']==r['scored_tokens'] and s['target_positions_sha256']==r['target_positions_sha256']
  assert r['all_layer_calls']==[len(wanted)]*36 and r['all_layer_input_tokens']==[sum(e['end']-e['begin']-1 for e in wanted)]*36
  if n=='g64b4':
   assert r['seed']==prov['seed']
   assert all(z['window_rng_key']==window_seed(r['seed'],z['segment_id']) for z in r['rows'])
   assert set(r['diagnostics'])==set(map(str,range(36)))
   for z in r['diagnostics'].values():assert z['group']==64 and z['levels']==4 and z['calls']==len(wanted) and all(t[8]==0 for t in z['nl_stats'])
  records[(name,n)]=r
cpu=(D/'cpu/slurm.log').read_text();assert 'Ran 77 tests' in cpu and 'OK (skipped=10)' in cpu
out=dict(source=v['commit'],full_protocol='2048/1024;complete299077targets;noBOS/chat/cache;all36FFNs/allprefix;accurateSDPA',
 completed_main=len([k for k in records if k[0]!='gate'])//2,expected_main=18,CPU_tests=77,CPU_skipped=10,
 numeric_boundary='GU FP32 restoration oracle;not fullchain bittrue;no newPPA/TLM/training',results=[])
if out['completed_main']==18:
 for seed in (0,1,2):
  row=dict(seed=seed)
  for case in ('bf16','g64b4'):
   rs=[records[(f'task{seed*6+p:02d}',case)] for p in range(6)]
   row[case]=dict(verify_rows([z for r in rs for z in r['rows']],expected),GPU_seconds_sum=math.fsum(r['seconds'] for r in rs))
   assert row[case]['scored_tokens']==299077
  row['PPL_change_percent']=(row['g64b4']['perplexity']/row['bf16']['perplexity']-1)*100;out['results'].append(row)
 vals=[x['g64b4']['perplexity'] for x in out['results']];refs=[x['bf16']['perplexity'] for x in out['results']]
 assert max(refs)-min(refs)<1e-5
 out.update(status='completed',bf16_PPL=statistics.mean(refs),g64b4_mean=statistics.mean(vals),g64b4_sample_SD=statistics.stdev(vals),g64b4_seeds=vals,
   mean_PPL_change_percent=(statistics.mean(vals)/statistics.mean(refs)-1)*100,
   windows_per_seed=len(expected),target_count_per_seed=299077,manifest_sha256=manifest,
   suffix_comparison_only=dict(bf16=13.566049199388152,g64b4_mean=17.921545522272677,warning='different scored set/window/RNG schedule;not a paired quality improvement'))
 (B/'FULL_WT2_G64B4_SUMMARY.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps({k:z for k,z in out.items() if k not in ('manifest_sha256','suffix_comparison_only')}),flush=True)
else:
 out['status']='incomplete';print(json.dumps(out),flush=True)

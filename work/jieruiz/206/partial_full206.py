import json,pathlib,sys
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/group64-scale-issue206-20261028');sys.path.insert(0,str(R))
from qwen3.group_shared.full_plan import full_window_plan,verify_rows
W=R/'work/jieruiz/206';v=json.loads(sorted(W.glob('FULL_WT2_SUBMISSION_*.json'))[-1].read_bytes());D=R/'qwen3/results/group_shared_20261028'/v['commit'][:12]/'full_wt2';plan=full_window_plan(299078,2048,1024)
for seed in (0,1,2):
 ds=[D/f'task{seed*6+p:02d}' for p in range(6)]
 if not all((d/'complete.json').exists() for d in ds):continue
 r={}
 for case in ('bf16','g64b4'):
  rows=[z for d in ds for z in json.loads((d/(case+'.json')).read_bytes())['rows']];r[case]=verify_rows(rows,plan)
 print(json.dumps(dict(seed=seed,full_coverage_verified=True,bf16=r['bf16']['perplexity'],G64B4=r['g64b4']['perplexity'],relative=(r['g64b4']['perplexity']/r['bf16']['perplexity']-1)*100)),flush=True)

"""Cross-stage audit, source closure and current publication-byte index."""
import hashlib,json,math,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[3];W=ROOT/'work/jieruiz/186'
OUT=ROOT/'architecture_tlm/unified_v6/results/locality_20261025'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
old=read(W/'LOCALITY_SOURCE_b1df81d2.json');new=read(W/'LOCALITY_SOURCE_829559dc.json')
changed=[p for p,v in old['files'].items() if new['files'][p]['sha256']!=v['sha256']]
assert set(changed)=={'architecture_tlm/unified_v6/ffn_locality.py','architecture_tlm/unified_v6/test_ffn_locality.py'}
checked=[]
for stage,commit,indices in [('',old['commit'],range(13)),('window_prefetch',new['commit'],range(2,13))]:
 for i in indices:
  p=OUT/stage/f'case_{i}';m=read(p/'MANIFEST.json');r=read(p/'RESULT_SUMMARY.json');e=read(p/'EXECUTION.json')
  assert m['status']=='completed' and r['execution_commit']==commit==e['source']['commit']
  for name in ('RESULT_SUMMARY.json','EXECUTION.json'):assert sha(p/name)==m['files'][name]['sha256']
  assert r['raw_result_sha256']==m['files']['RESULT.json']['sha256']
  if stage:
   R=r['case']['locality']['retain'];expected=36*(math.ceil(40/R)+math.ceil(152/R)-2)
   assert r['FFN_contract']['locality_counts'].get('cross_window_prefetches',0)==expected
  checked.append(dict(stage=stage or 'stage1',index=i,manifest_sha256=sha(p/'MANIFEST.json')))
for i in (5,12):
 a=read(OUT/f'case_{i}/RESULT_SUMMARY.json');b=read(OUT/'window_prefetch'/f'case_{i}/RESULT_SUMMARY.json')
 assert a['metrics']['TPOT_ms']==b['metrics']['TPOT_ms'],'full-K mapping should be unaffected by boundary repair'
files={}
for p in [ROOT/'architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md',ROOT/'architecture_tlm/unified_v6/FFN_LOCALITY_ZH.md',OUT/'COMPARISON.csv',OUT/'AGGREGATE.json',OUT/'STAGE1_COMPARISON.csv',W/'LOCALITY_MATRIX.json']:
 files[p.relative_to(ROOT).as_posix()]=dict(bytes=p.stat().st_size,sha256=sha(p))
result=dict(status='24 complete source/manifest/SHA verified',source_change=changed,
 control_reuse='only optional locality implementation and its test changed; native SC/digital controls unchanged',
 no_physical_PPA_or_PPL=True,checked=checked,documents=files)
(OUT/'DELIVERY_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(status=result['status'],documents=len(files))))

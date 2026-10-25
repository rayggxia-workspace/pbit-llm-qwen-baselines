"""Audit sealed full-model common-resource cases; not independent full event replay."""
import json,pathlib,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[3];B=ROOT/'architecture_tlm/unified_v6/results/scheduling_20261025'
A=json.loads((B/'COMPARISON.json').read_text(encoding='utf-8'));assert A['verified_cases']==45 and not A['missing']
checks=[]
for p in B.glob('*/*/RESULT_SUMMARY.json'):
 r=json.loads(p.read_text(encoding='utf-8'));c=r['config'];d=r['DRAM'];name=r['case']['name']
 assert c['core_hz']==100000000 and c['random']['clock_hz']==c['core_hz']
 assert c['sram']['banks']==64 and c['sram']['capacity_bytes']==8*1024**2
 assert d['details']['configuration_sha256']=='ddbdd1aee7f20d5e3eaf12d73b7e300894ad3ab5cc50ae2a8aa5fd121b2fa419'
 assert d['details']['capacity_bytes']==16*1024**3
 for k,v in d['traffic'].items():
  if k.endswith('_physical_bytes'):assert v==64*d['traffic'][k[:-15]+'_bursts'],(name,k)
 if r['case']['ffn']=='sc':assert r['FFN_activity']['SC_64x64_tiles']==656640 and r['FFN_activity']['online_absmax_calls']==0
 if name.startswith('corrected_') or name.startswith('w8_pv_'):assert c['digital_w8_restore']=='block64'
 for side in ('digital','sc'):
  q=r.get('tile_pipeline',{}).get(side)
  if q:assert q['counts'].get('issued',0)==q['counts'].get('retired',0) and not q['pending'] and not q['active']
 checks.append({'case':name,'source':r['execution_commit'],'summary_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'contract_checked':True})
assert len(checks)==45
out={'status':'passed','cases':45,'scope':'sealed identities/config, common clock/memory, burst-byte conservation, no pending tile, latest FFN work count, corrected W8 labels; not every event independently replayed','rows':checks}
(B/'FINAL_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n')
print('45 contract audits passed')

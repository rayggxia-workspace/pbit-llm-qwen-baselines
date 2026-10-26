"""Verify sealed full-model cases and derive inspectable PPA tables."""
import hashlib,json,math,subprocess
from pathlib import Path
from .ppa import estimate,usage_from_tlm,read,sha
D=Path(__file__).resolve().parent
def save(p,v):
 p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def main():
 matrix=read(D/'MATRIX.json')['cases'];anchors=read(D/'PPA_ANCHORS.json');rows=[];inputs={}
 for i,c in enumerate(matrix):
  f=D/'results'/('case_'+str(i));m=read(f/'MANIFEST.json');assert m['status']=='completed'
  for name in ('RESULT_SUMMARY.json','EXECUTION.json'):
   assert sha(f/name)==m['files'][name]['sha256']
  r=read(f/'RESULT_SUMMARY.json');cfg=r['config']
  assert r['case']==c and cfg['core_hz']==500000000 and cfg['sram']['clock_hz']==80000000
  assert cfg['random']['clock_hz']==cfg['core_hz']
  assert r['DRAM']['details']['status']=='finished'
  assert r['DRAM']['details'].get('energy_valid') is not True
  assert r['metrics']['elapsed_ns']>0
  assert abs(sum(r['phase_ns'].values())-r['metrics']['elapsed_ns'])<.01
  if cfg['ffn']['mode']=='sc':
   assert r['FFN_activity']['SC_64x64_tiles']==656640
   assert cfg['ffn']['samples']==64
  gate=r['clock_gating']
  for k,v in gate['resources'].items():
   assert abs(v['clock_on_ns']+v['off_ns']-gate['lifetime_ns'])<.001
  pp=estimate(r,usage_from_tlm(r),anchors)
  pp['analysis_commit']=subprocess.check_output(['git','log','-1','--format=%H','--','architecture_tlm/clock500_resource_20261026/analyze.py','architecture_tlm/clock500_resource_20261026/ppa.py','architecture_tlm/clock500_resource_20261026/PPA_ANCHORS.json'],cwd=D.parents[1]).decode().strip()
  pp['execution_commit']=r['execution_commit']
  pp['source_sha256']={'RESULT_SUMMARY.json':sha(f/'RESULT_SUMMARY.json'),'PPA_ANCHORS.json':sha(D/'PPA_ANCHORS.json'),'ppa.py':sha(D/'ppa.py')}
  save(f/'PPA_ESTIMATE.json',pp)
  ffntime=sum(r['phase_ns'].get(k,0) for k in ('FFN_gate_up','FFN_nonlinear_encoding','FFN_AND_direct_down','ffn_output_conversion'))/1e6
  rows.append(dict(index=i,name=c['name'],TPOT_ms=r['metrics']['TPOT_ms'],core_cycles=r['metrics']['elapsed_ns']*.5,
   FFN_ms=ffntime,phase_ms={k:v/1e6 for k,v in r['phase_ns'].items()},
   DRAM_bytes=sum(v for k,v in r['DRAM']['traffic'].items() if k.endswith('_physical_bytes')),
   SRAM_bytes=sum(v for k,v in r['SRAM']['traffic'].items() if k.endswith('_physical_bytes')),
   priced_energy_J=pp['priced_subtotal_J'],priced_average_W=pp['priced_subtotal_average_W'],
   area_subtotal_mm2=pp['known_area_subtotal_mm2'],full_physical_power_W=None,full_physical_area_mm2=None,
   gate=pp['counter_restore_only_clock_gating'],module_PPA=pp['modules'],stage_busy_ms={k:v/1e6 for k,v in r['stage_busy_ns'].items()},
   execution_commit=r['execution_commit']))
  inputs[str(i)]=dict(summary_sha256=sha(f/'RESULT_SUMMARY.json'),manifest_sha256=sha(f/'MANIFEST.json'),ppa_sha256=sha(f/'PPA_ESTIMATE.json'))
 # Paired clocks preserve the retained-state operator, changing only delay.
 for i in (4,6,8,10):
  a,b=rows[i],rows[i+1]
  assert b['TPOT_ms']>=a['TPOT_ms']-.000001
  assert abs(a['area_subtotal_mm2']-b['area_subtotal_mm2'])<1e-7
  ra=read(D/'results'/('case_'+str(i))/'RESULT_SUMMARY.json');rb=read(D/'results'/('case_'+str(i+1))/'RESULT_SUMMARY.json')
  assert ra['FFN_activity']==rb['FFN_activity']
  assert ra['attention_activity']==rb['attention_activity']
  assert a['DRAM_bytes']==b['DRAM_bytes'] and a['SRAM_bytes']==b['SRAM_bytes']
 old=D.parent/'ffn_local_pipeline_20261025/results/case_2/RESULT_SUMMARY.json'
 prior=read(old)
 prior['clock_gating']={'enabled':False,'resources':{k:{'clock_on_ns':prior['metrics']['elapsed_ns'],'busy_ns':v} for k,v in prior['resource_busy_ns'].items()}}
 prior['random_interface']={'calibrated_endpoint_two_state_energy_J':prior['energy_J']['RNG_endpoint_calibrated']}
 old_ppa=estimate(prior,usage_from_tlm(prior),anchors)
 old_ppa['scope']='Derived old100MHz/NL64 nongated anchor, same maximum B7-capable counter proxy; no new TLM run, RNG energy imported from original ledger, endpoint area absent from old summary.'
 old_ppa['summary_sha256']=sha(old)
 save(D/'OLD100_PPA_ESTIMATE.json',old_ppa)
 result=dict(scope='12 sealed CPU TLM runs, 36 layers, B1 decode2K; known PPA subtotal is NOT whole chip',old_anchor={'TPOT_ms':read(old)['metrics']['TPOT_ms'],'sha256':sha(old),'derived_priced_J':old_ppa['priced_subtotal_J'],'derived_priced_W':old_ppa['priced_subtotal_average_W'],'area_subtotal_mm2':old_ppa['known_area_subtotal_mm2']},rows=rows,inputs=inputs)
 save(D/'COMPARISON.json',result)
 print(json.dumps([dict(name=r['name'],ms=r['TPOT_ms'],W=r['priced_average_W'],mm2=r['area_subtotal_mm2']) for r in rows]))
if __name__=='__main__':main()

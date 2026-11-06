"""Full-shape one-layer mechanics on explicit synthetic sample timing/indices.
This is not the captured-trace/native result and must never inherit its TPOT.
"""
from pathlib import Path
import importlib.util,json,sys,time
PROJECT=Path('C:/Users/86134/Documents/a_P_BIT')
WD=Path(__file__).resolve().parents[4]
FOLDER=WD/'architecture_tlm/sram1216_20261106'
spec=importlib.util.spec_from_file_location('compact_boot',FOLDER/'bootstrap.py')
boot=importlib.util.module_from_spec(spec);spec.loader.exec_module(boot)
runtime=PROJECT/'project_archives/ffn_sram_batch204_20261106/runtime'
identity=boot.use_runtime(runtime,PROJECT/'project_archives/sram1216_225_20261106/dependencies')
from architecture_tlm.sram1216_20261106.model import make_model
from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
representative=json.loads((runtime/'base/representative.json').read_bytes())
samples={'samples':{}}
for g in range(8):
 for head in range(12):
  samples['samples']['ab_both/17/%d/%d'%(g,head)]=dict(indices=[(j*37+head*19+g)%128 for j in range(64)],hits=64,cycles=600,first=4)
rows=[]
for case in ('control1952','attention1440','compact1216'):
 start=time.time()
 h,m=make_model(AnalyticDRAM(latency_ns=30,bandwidth_GBs=136.4606),configuration=case,
     mode='ising',ffn='sc',samples=samples,layers=36,include_lm=False,seed=17,attention_input=representative)
 m.model['layers']=1
 result=m.run()
 assert not h.pending and not h.mem.queue
 rows.append(dict(case=case,time_ms=h.now*1e-6,wall_seconds=time.time()-start,actions=result['actions'],
     counts=dict(h.count),SRAM=h.mem.report(h.now),contract=result['sram1216_contract']))
 print(json.dumps(dict(case=case,time_ms=h.now*1e-6,wall_seconds=time.time()-start)),flush=True)
out=dict(scope='one full-shape layer; analytic DRAM and synthetic sampler cycles/indices; no PPL or native TPOT',rows=rows,identity=identity)
dest=PROJECT/'project_archives/sram1216_225_20261106'
(dest/'LOCAL_SYNTHETIC_SMOKE.json').write_bytes((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())
for row in rows[1:]:
 for key in ('digital_BF16_MAC','digital_FP32_reduce_ADD','attention_QK_MAC','PV_ADD','samples','SC_equivalent_MAC','crossK_updates'):
  assert row['actions'][key]==rows[0]['actions'][key],key
 for key in ('dram_read_bytes','dram_write_bytes'):
  assert row['counts'][key]==rows[0]['counts'][key],key
print('SYNTHETIC_INTEGRATION_PASS',flush=True)

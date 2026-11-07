"""Bind a sealed whole-token result to the standalone quick simulator."""
from pathlib import Path
from collections import defaultdict
import argparse,hashlib,json
p=argparse.ArgumentParser();p.add_argument('--result',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);p.add_argument('--bandwidth',type=float,default=136.4606)
a=p.parse_args();raw=a.result.read_bytes();x=json.loads(raw)
seal=a.result.with_name('SEAL.json');s=json.loads(seal.read_bytes())
assert hashlib.sha256(raw).hexdigest()==s['result_sha256']
assert x['status']=='completed' and x['scope']=='whole36+lm_head'
samples=x.get('sampling_latency_contract',{})
assert samples.get('GU_samples',64)==samples.get('NL_Wd_samples',64)==64,'calibration requiresT64/T64 reference'
phases=defaultdict(float)
for z in x['phases']:phases[z['stage']]+=z['duration_ns']*1e-6
assert abs(sum(phases.values())-x['simulated_ms'])<1e-7
assert phases['lm_head']>0
model=x.get('model',{});resources=x['executed_resources']
out=dict(configuration='native_'+a.result.parent.name,layers=x.get('layers',model.get('layers',36)),
    hidden=model.get('hidden',2560),ffn=model.get('ffn',9728),clock_MHz=100,
    cores=resources['physical_common_FFN_cores'],weight_slots=32,state_ports=2,
    reference_samples=64,bandwidth_GBs=a.bandwidth,tile_load_latency_ns=40,state_service_ns=60,
    including_lm_head_ms=x['simulated_ms'],lm_head_stage_ms=phases['lm_head'],phase_totals_ms=dict(phases),
    reference_completed_native=True,source_result=str(a.result),source_result_sha256=s['result_sha256'],
    source_seal_sha256=hashlib.sha256(seal.read_bytes()).hexdigest(),
    use_scope='sample-count delta for this physical configuration; do not mix with another SRAM/digital pool',
    lm_head_exclusion='subtract lm_head phase; final norm and overlapped prefetch retained')
a.out.write_bytes((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps(dict(profile=str(a.out),source_sha=s['result_sha256'])))

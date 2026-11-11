"""Small actual-head geometry probes for explicit long-vocabulary extrapolation."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,sys,time

def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_bytes((json.dumps(v,indent=2,allow_nan=False)+'\n').encode())

p=argparse.ArgumentParser();p.add_argument('--execution',type=Path,required=True)
p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True)
p.add_argument('--dependencies',type=Path,required=True);p.add_argument('--mhz',type=int,choices=(250,500),required=True)
p.add_argument('--rows',type=int,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
assert a.rows in (1024,1152,2048)
source_sha=sha(Path(__file__))
manifest=load(a.execution/'MANIFEST.json')
for name,digest in manifest['files_sha256'].items():assert sha(a.execution/name)==digest
sys.path.insert(0,str(a.execution.resolve()));from whole_model import build
spec=importlib.util.spec_from_file_location('head28load',a.snapshot/'glue/current_mainline.py')
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
host.environment(a.snapshot,a.runtime,a.dependencies,250)
from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
backend=AnalyticDRAM(latency_ns=30,bandwidth_GBs=136.4606)
binding=a.execution/(str(a.mhz)+'MHz')/'BINDINGS.json';macros=a.execution/(str(a.mhz)+'MHz')/'WHOLE_CONFIG.json'
a.out.mkdir(parents=True,exist_ok=False);started=time.time()
h,m,_,shape,identity=build(a.snapshot,a.runtime,a.dependencies,load(binding),sha(binding),backend,
    3 if a.mhz==250 else 2,1,load(macros),17,False)
# Previous FFN can prefetch these same two legal finite weight slots.
m.phase('head_weight_prefetch',[m.prefetch_matrix(0,'lm_head',a.rows,2560)],-1)
start=h.now
m.phase('lm_head',[m.digital_matrix(0,'lm_head',a.rows,2560)],-1)
assert not h.events and not h.mem.queue and not h.pending
memory=h.report();weights=memory['by_kind']['lm_head_weights']['issued_bytes']
assert weights==a.rows*2560*2
assert m.actions['digital_BF16_MAC']==a.rows*2560
assert not m.prefetched
result=dict(status='completed',clock_MHz=a.mhz,rows=a.rows,head_duration_ns=h.now-start,
 prefetch_duration_ns=start,MAC=m.actions['digital_BF16_MAC'],external_bytes=weights,
 SRAM=h.mem.report(h.now),ordinary_audit=m.ordinary_pool_audit,
 configuration='same256FMA/4contexts/finite8packets/2weight-slots aswhole28;activationresident',
 backend='analytic136.4606GBps,30ns',execution_manifest_sha256=sha(a.execution/'MANIFEST.json'),
 host_manifest_sha256=sha(a.snapshot/'SNAPSHOT_MANIFEST.json'),code_sha256=source_sha,
 actual_full151936_head_run=False,wall_seconds=time.time()-started)
assert sha(Path(__file__))==source_sha
save(a.out/'RESULT.json',result);save(a.out/'SEAL.json',dict(status='completed',files_sha256={'RESULT.json':sha(a.out/'RESULT.json')}))
print(json.dumps({k:result[k] for k in ('status','clock_MHz','rows','head_duration_ns','wall_seconds')}))

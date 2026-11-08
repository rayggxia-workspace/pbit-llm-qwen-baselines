from pathlib import Path
import ast,hashlib,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PROJECT=ROOT.parents[1]
sys.path.insert(0,str(ROOT/'architecture_tlm/model_scaling_20261106'))
from current_mainline import environment,rebuild,load,vector_decoder
snapshot=HERE/'revision2/snapshot';runtime=PROJECT/'project_archives/ffn_sram_batch204_20261106/runtime'
deps=PROJECT/'project_archives/sram1216_225_20261106/dependencies'
rows=[]
for model in ('qwen3_4b','llama32_3b','deepseek_7b'):
 factory,_=environment(snapshot,runtime,deps,100)
 from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
 h,m=factory(AnalyticDRAM(latency_ns=30,bandwidth_GBs=136.4606),layers=36,include_lm=True,seed=17,
   samples=load(snapshot/'inputs/SAMPLES.json'),attention_input=load(snapshot/'inputs/representative.json'))
 m.cross_clock=100;s=load(snapshot/'glue/CURRENT_WORKLOAD_PLAN.json')['models'][model]['shape'];rebuild(m,s,s['layers'],'SC_ising')
 h.execute([m.copy(m.vector,0,m.vector,131072,s['hidden']*2,'decoder_probe_residual')])
 h.execute([h.transfer(m.vector,65536,m.cross_meta,False,'decoder_probe_metadata')])
 assert not h.events and not h.mem.queue
 rows.append(dict(model=model,hidden=s['hidden'],meta=m.cross_meta,capacity=h.mem.capacity,
   physical_vector_bytes=m.vector.size,bindings=getattr(m,'cross_decoder_bindings',[]),events_drained=True))
# Same physical addresses for the old Qwen live objects, including all16Bwords.
namespace={};source=(snapshot/'host/architecture_tlm/sram1216_20261106/model.py').read_text()
node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='vector_address')
exec(compile(ast.Module(body=[node],type_ignores=[]),'old_vector_address','exec'),namespace)
old=namespace['vector_address'];new=vector_decoder(32768);count=0
for start,end in [(0,32768),(65536,98304),(131072,136192)]+[(196608+g*6144+5120,196608+(g+1)*6144) for g in range(8)]:
 for off in range(start,end,16):assert old(off,16)==new(off,16);count+=1
result=dict(status='PASS_REAL100_MEMORY_WRAPPER_PREFLIGHT',cases=rows,Qwen_old_new_words_equal=count,
 source_sha256=hashlib.sha256((ROOT/'architecture_tlm/model_scaling_20261106/current_mainline.py').read_bytes()).hexdigest(),
 new_full_TLM=False,capacity_changed=False,front_end_changed=False)
(HERE/'DECODER_PREFLIGHT.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps(result))

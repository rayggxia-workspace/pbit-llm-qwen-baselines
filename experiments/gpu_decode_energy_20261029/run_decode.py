"""Slurm RTX5090 BF16 decode timing, board energy, and isolated module replay."""
import argparse
import csv
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

import torch
import transformers
from transformers import AutoModelForCausalLM,AutoTokenizer
from transformers.cache_utils import DynamicCache

from meter import Nvml,summarize
from instrument import Instrument

EXPECTED_REVISION='1cfa9a7208912126459214e8b04321603b3df60c'

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()

def tensor_hash(tensor):
    return hashlib.sha256(tensor.detach().cpu().numpy().astype('<i8',copy=False).tobytes()).hexdigest()

def write(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')

def verify(prepared):
    p=json.loads(prepared.read_text())
    assert p['model']['id']=='Qwen/Qwen3-4B' and p['revision']==EXPECTED_REVISION
    root=Path(p['local_path']).resolve()
    for item in p['files']:
        file=(root/item['name']).resolve()
        assert root in file.parents
        assert file.stat().st_size==item['bytes'] and digest(file)==item['sha256'],file.name
    for data in p['data'].values():assert digest(Path(data['path']))==data['sha256']
    return p,root

def synchronize():torch.cuda.synchronize()

def warm(fn,seconds):
    end=time.perf_counter()+seconds;n=0
    while time.perf_counter()<end or not n:
        for _ in range(4):result=fn();n+=1
        synchronize()

def measure(fn,meter,seconds,repeats,idle_W):
    warm(fn,.3)
    start=time.perf_counter()
    for _ in range(4):result=fn()
    synchronize();per=(time.perf_counter()-start)/4
    iterations=max(1,min(100000,int(math.ceil(seconds/max(per,1e-6)))))
    rows=[]
    for repeat in range(repeats):
        warm(fn,.2)
        begin=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True)
        synchronize();state0=meter.state();t0=time.perf_counter();e0=meter.energy_mJ()
        begin.record()
        for _ in range(iterations):result=fn()
        end.record();synchronize();e1=meter.energy_mJ();t1=time.perf_counter()
        energy=(e1-e0)/1000.;duration=t1-t0
        assert energy>0,'nonpositive GPU energy counter delta'
        rows.append({'repeat':repeat,'iterations':iterations,'wall_s':duration,'gpu_ms':begin.elapsed_time(end),
            'energy_J':energy,'average_W':energy/duration,'energy_mJ_per_item':energy*1000/iterations,
            'wall_ms_per_item':duration*1000/iterations,'gpu_ms_per_item':begin.elapsed_time(end)/iterations,
            'incremental_energy_J_diagnostic_only':energy-idle_W*duration,'state_before':state0,'state_after':meter.state(),
            'energy_read_start_mJ':e0,'energy_read_end_mJ':e1})
        print(json.dumps({'event':'window','repeat':repeat,'iterations':iterations,'wall_s':duration,'average_W':energy/duration}),flush=True)
    return {'repeats':rows,'summary':summarize(rows),'method':'NVML total energy counter difference; CUDA event span; no per-module synchronization'}

def new_cache(legacy):
    return DynamicCache.from_legacy_cache(legacy)

def graph_callable(fn):
    """Capture a fixed-shape workload to avoid a Python-launch-bound baseline."""
    stream=torch.cuda.Stream()
    stream.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(stream):
        for _ in range(3):out=fn()
    stream.synchronize()
    graph=torch.cuda.CUDAGraph()
    with torch.cuda.graph(graph,stream=stream):out=fn()
    graph.replay();synchronize()
    return graph,out

def build_prefix(model,prompt):
    t0=time.perf_counter()
    result=model(input_ids=prompt,use_cache=True,return_dict=True,logits_to_keep=1)
    synchronize()
    return result.past_key_values.to_legacy_cache(),result.logits[:,-1].argmax(-1,keepdim=True),time.perf_counter()-t0

def native_decode(model,prompt,meter,steps,repeats):
    records=[]
    for repeat in range(repeats):
        legacy,next_id,prefill=build_prefix(model,prompt)
        cache=new_cache(legacy)
        # Prefill, cache construction, and output transfer are outside this window.
        synchronize();start=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True)
        e0=meter.energy_mJ();t0=time.perf_counter();start.record();generated=[]
        for _ in range(steps):
            out=model(input_ids=next_id,past_key_values=cache,use_cache=True,return_dict=True,logits_to_keep=1)
            cache=out.past_key_values;next_id=out.logits[:,-1].argmax(-1,keepdim=True);generated.append(next_id)
        end.record();synchronize();t1=time.perf_counter();e1=meter.energy_mJ()
        elapsed=t1-t0;energy=(e1-e0)/1000
        row={'repeat':repeat,'decode_steps':steps,'KV_total_length_first':prompt.shape[-1]+1,
            'KV_total_length_last':prompt.shape[-1]+steps,'wall_s':elapsed,'gpu_ms':start.elapsed_time(end),
            'energy_J':energy,'average_W':energy/elapsed,'energy_mJ_per_item':energy*1000/steps,
            'wall_ms_per_item':elapsed*1000/steps,'prefill_wall_s_excluded':prefill,
            'generated_ids_sha256':tensor_hash(torch.cat(generated,dim=-1)),
            'energy_window_suitable_for_primary_estimate':elapsed>=3.}
        records.append(row)
        print(json.dumps({'event':'native_decode','repeat':repeat,'context':prompt.shape[-1]+1,'TPOT_ms':row['wall_ms_per_item'],'average_W':row['average_W']}),flush=True)
        del cache,out,legacy,generated
    return {'repeats':records,'summary':summarize(records),'method':'unmodified graph, sequential greedy decode; context grows; prefill excluded'}

def one(model,legacy,token):
    return model(input_ids=token,past_key_values=new_cache(legacy),use_cache=True,return_dict=True,logits_to_keep=1)

def time_profile(model,legacy,token,baseline_logits,output,steps):
    with Instrument(model,annotations=True) as instrument:
        with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU,torch.profiler.ProfilerActivity.CUDA],record_shapes=True) as prof:
            for _ in range(steps):out=one(model,legacy,token)
            synchronize()
    assert torch.equal(out.logits,baseline_logits),'instrumented graph logits changed'
    prof.export_chrome_trace(str(output/'TRACE.json'))
    rows=[]
    for event in prof.key_averages():
        # Kineto also creates CUDA user-annotation ranges with the same key.
        # Their elapsed duration contains stream gaps; use CPU ranges' linked
        # kernel totals, rather than overwriting them with CUDA range duration.
        if event.key.startswith('gpu212::') and str(event.device_type).endswith('CPU'):
            total=getattr(event,'device_time_total',None)
            if total is None:total=event.cuda_time_total
            rows.append({'category':event.key.split('::',1)[1],'calls':event.count,'annotation_device_type':str(event.device_type),
                'GPU_kernel_ms_per_decode':total/1000/steps,'CPU_range_ms_per_decode':event.cpu_time_total/1000/steps})
    kernels=[e.name for e in prof.events() if str(e.device_type).endswith('CUDA')]
    if not kernels:raise RuntimeError('CUDA Profiler did not collect kernels')
    return {'rows':rows,'profile_decode_calls':steps,'CUDA_kernel_count':len(kernels),
        'CUDA_kernel_names':sorted(set(kernels)),'FlashAttention_observed':any('flash' in k.lower() for k in kernels),
        'instrumented_logits_bitwise_equal':True,
        'time_boundary':'sum of kernels attributed to nonoverlapping named ranges; not wall-clock accounting; other layout/control left unassigned'}

def exclusive(uuid):
    p=subprocess.run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    if p.returncode:raise RuntimeError('cannot verify allocated device compute-process ownership')
    foreign=[line for line in p.stdout.splitlines() if line.split(',')[0].strip()==uuid and line.split(',')[1].strip()!=str(os.getpid())]
    if foreign:raise RuntimeError('allocated GPU has a foreign compute process')

@torch.inference_mode()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepared',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--contexts',type=int,nargs='+',default=[2048,8192]);p.add_argument('--window-seconds',type=float,default=5.)
    p.add_argument('--repeats',type=int,default=3);p.add_argument('--native-steps',type=int,default=128)
    p.add_argument('--profile-steps',type=int,default=3);p.add_argument('--smoke',action='store_true')
    a=p.parse_args()
    assert 'SLURM_JOB_ID' in os.environ and torch.cuda.device_count()==1
    assert not a.output.exists(),'immutable output path required'
    a.output.mkdir(parents=True)
    prepared,model_path=verify(a.prepared)
    tokenizer=AutoTokenizer.from_pretrained(str(model_path),local_files_only=True)
    text=Path(prepared['data']['wiki.test.raw']['path']).read_text(encoding='utf-8')
    all_ids=tokenizer(text,add_special_tokens=False).input_ids
    ids=torch.tensor(all_ids,dtype=torch.long)
    assert len(all_ids)==prepared['test_corpus_tokens']
    assert tensor_hash(ids)==prepared['test_token_ids_sha256_le_int64']
    props=torch.cuda.get_device_properties(0);uuid=str(props.uuid)
    if not uuid.startswith('GPU-'):uuid='GPU-'+uuid
    meter=Nvml(uuid);meter.energy_mJ();exclusive(uuid)
    model=AutoModelForCausalLM.from_pretrained(str(model_path),torch_dtype=torch.bfloat16,
        attn_implementation='sdpa',local_files_only=True).eval().to('cuda')
    source={p.name:digest(p) for p in Path(__file__).parent.glob('*.py')}
    provenance={'kind':'real_GPU_measurement_not_ASIC_simulation','model_id':prepared['model']['id'],
        'revision':prepared['revision'],'model_manifest_sha256':digest(a.prepared),
        'model_files_sha256':{r['name']:r['sha256'] for r in prepared['files']},
        'test_raw_sha256':prepared['data']['wiki.test.raw']['sha256'],
        'test_token_ids_sha256':tensor_hash(ids),'tokenizer':prepared['tokenizer_class'],
        'source_sha256':source,'torch':torch.__version__,'transformers':transformers.__version__,
        'gpu_name':props.name,'gpu_memory_bytes':props.total_memory,'gpu_uuid_sha256':hashlib.sha256(uuid.encode()).hexdigest(),
        'Slurm_job_id':os.environ['SLURM_JOB_ID'],'dtype':'BF16 inputs/weights; native kernels retain their own accumulation rules',
        'batch':1,'chat_template':False,'prompt':'first context-1 tokens of frozen WT2 test; no BOS',
        'thinking':'not a chat-generation benchmark','EOS_early_stop':False,'greedy':True,'args':vars(a)|{'prepared':'verified existing manifest','output':'task result directory'}}
    provenance['args']={k:str(v) if isinstance(v,Path) else v for k,v in provenance['args'].items()}
    write(a.output/'PROVENANCE.json',provenance)
    for context in a.contexts:
        folder=a.output/('context_'+str(context));folder.mkdir()
        prompt=ids[:context-1].unsqueeze(0).to('cuda')
        assert prompt.shape[-1]==context-1
        print(json.dumps({'event':'context_start','context':context}),flush=True)
        legacy,token,prefill_s=build_prefix(model,prompt)
        fn=lambda:one(model,legacy,token)
        warm(fn,.5)
        time.sleep(1.5);e0=meter.energy_mJ();t0=time.perf_counter();time.sleep(2.);idle=(meter.energy_mJ()-e0)/1000/(time.perf_counter()-t0)
        baseline=fn();synchronize();baseline_logits=baseline.logits.clone()
        with Instrument(model,capture=True) as captured:instrumented=fn()
        synchronize()
        assert torch.equal(instrumented.logits,baseline_logits),'capture changed native logits'
        inventory=captured.inventory()
        assert inventory['QKV_projection']['calls_per_decode']==36*3
        assert inventory['FFN_gate_up']['calls_per_decode']==36*2
        assert inventory['Attention_core']['calls_per_decode']==36
        assert inventory['KV_append']['calls_per_decode']==36
        assert inventory['Residual_add']['calls_per_decode']==72
        write(folder/'INVENTORY.json',inventory)
        write(folder/'INSTALLED_FORWARD_SOURCE.json',captured.source)
        profile=time_profile(model,legacy,token,baseline_logits,folder,a.profile_steps)
        write(folder/'TIME_PROFILE.json',profile)
        whole=measure(fn,meter,a.window_seconds,a.repeats,idle)
        whole['scope']='one full decode-forward at fixed total KV length; cache rebuilt by sharing immutable prefix tensors; no prefill or host tensor copy in window; Python cache construction included in wall/energy'
        write(folder/'FIXED_CONTEXT_DECODE.json',whole)
        try:
            full_graph,graph_output=graph_callable(fn)
        except RuntimeError as error:
            graph_result={'status':'unsupported','error':str(error),'summary':None}
        else:
            assert torch.equal(graph_output.logits,baseline_logits),'CUDA Graph logits changed'
            graph_result=measure(full_graph.replay,meter,a.window_seconds,a.repeats,idle)
            graph_result.update(status='completed',logits_bitwise_equal=True,
                scope='fixed-context full forward via CUDA Graph; same native kernels and prefix; capture/warmup excluded; no autoregressive context growth')
            del full_graph,graph_output
        write(folder/'CUDA_GRAPH_FIXED_CONTEXT_DECODE.json',graph_result)
        modules={}
        categories=list(captured.calls)
        if a.smoke:categories=['QKV_projection','Attention_core','FFN_gate_up','FFN_SwiGLU','FFN_down','KV_append']
        for category in categories:
            print(json.dumps({'event':'module_start','context':context,'category':category}),flush=True)
            replay=lambda c=category:captured.replay(c)
            try:
                module_graph,module_output=graph_callable(replay)
            except RuntimeError as error:
                modules[category]=measure(replay,meter,a.window_seconds,a.repeats,idle)
                modules[category].update(execution='eager_fallback',graph_error=str(error))
            else:
                modules[category]=measure(module_graph.replay,meter,a.window_seconds,a.repeats,idle)
                modules[category]['execution']='cuda_graph_replay'
                del module_graph,module_output
            modules[category]['scope']='isolated replay of all captured occurrences per decode; changes cache/order/concurrency and is NOT independently sensed in-situ module power'
            write(folder/('REPLAY_'+category+'.json'),modules[category])
        del baseline,instrumented,captured,fn,legacy,baseline_logits
        gc.collect();torch.cuda.empty_cache()
        native=native_decode(model,prompt,meter,a.native_steps,a.repeats)
        write(folder/'NATIVE_CONTINUOUS_DECODE.json',native)
        summary={'status':'completed','context_total_KV_tokens':context,'fixed_context':whole['summary'],
            'cuda_graph_fixed_context':graph_result['summary'],'cuda_graph_status':graph_result['status'],
            'native_continuous':native['summary'],'modules':{k:v['summary'] for k,v in modules.items()},
            'module_time':profile['rows'],'idle_board_W_diagnostic_only':idle,'prefill_wall_s_excluded':prefill_s,
            'capture_logits_bitwise_equal':True,'FlashAttention_observed':profile['FlashAttention_observed'],
            'all_36_layers_covered':True,'not_additive_module_energy':True,
            'physical_scope':'GPU board plus associated memory circuitry reported by NVML; no host CPU/DRAM energy',
            'limitations':['NVML counter finite sensor cadence; no external meter calibration',
                'isolated replay is not in-situ per-module rail energy; do not force sum closure',
                'GPU caches and clocks differ between replay categories; working sets retained in inventory',
                'no heavy profiler in native/fixed energy windows; profiler timings are a separate run',
                'native context grows; fixed-context loop is the shape-matched TLM comparator']}
        write(folder/'SUMMARY.json',summary)
        print(json.dumps({'event':'context_completed','context':context,'TPOT_ms':whole['summary']['wall_ms_per_item']['mean'],
            'energy_mJ_per_token':whole['summary']['energy_mJ_per_item']['mean'],'average_W':whole['summary']['average_W']['mean']}),flush=True)
    manifest={str(f.relative_to(a.output)):{'sha256':digest(f),'bytes':f.stat().st_size} for f in a.output.rglob('*') if f.is_file()}
    write(a.output/'ARTIFACT_MANIFEST.json',manifest)
    write(a.output/'COMPLETED.json',{'status':'completed','contexts':a.contexts,'source_sha256':source,'artifacts_manifest_sha256':digest(a.output/'ARTIFACT_MANIFEST.json')})

if __name__=='__main__':main()

"""Short real-Qwen3 CUDA/NVTX and CUDA Graph capture; not an energy benchmark."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from transformers.cache_utils import DynamicCache

@torch.inference_mode()
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared',type=Path,required=True);parser.add_argument('--executed-code',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    assert 'SLURM_JOB_ID' in os.environ and torch.cuda.device_count()==1
    sys.path.insert(0,str(a.executed_code))
    from run_decode import verify,digest,tensor_hash,build_prefix,one,graph_callable,exclusive
    from instrument import Instrument
    p,model_path=verify(a.prepared)
    uuid=str(torch.cuda.get_device_properties(0).uuid)
    if not uuid.startswith('GPU-'):uuid='GPU-'+uuid
    exclusive(uuid)
    model=AutoModelForCausalLM.from_pretrained(str(model_path),torch_dtype=torch.bfloat16,attn_implementation='sdpa',local_files_only=True).eval().to('cuda')
    tokenizer=AutoTokenizer.from_pretrained(str(model_path),local_files_only=True)
    ids=torch.tensor(tokenizer(Path(p['data']['wiki.test.raw']['path']).read_text(encoding='utf-8'),add_special_tokens=False).input_ids,dtype=torch.long)
    assert tensor_hash(ids)==p['test_token_ids_sha256_le_int64']
    legacy,token,_=build_prefix(model,ids[:2047].unsqueeze(0).to('cuda'))
    work=lambda:one(model,legacy,token)
    for _ in range(5):baseline=work()
    torch.cuda.synchronize();reference=baseline.logits.clone()
    graph,out=graph_callable(work);assert torch.equal(out.logits,reference)
    class NVTXInstrument(Instrument):
        def call(self,category,name,fn,*args,**kwargs):
            with torch.cuda.nvtx.range('qwen3/'+category):return fn(*args,**kwargs)
    torch.cuda.cudart().cudaProfilerStart()
    for _ in range(4):
        with torch.cuda.nvtx.range('decode/eager_fixed'):out=work()
    with NVTXInstrument(model) as instrument:
        original=DynamicCache.update
        def update(cache,key,value,idx,cache_kwargs=None):
            if idx>=len(cache.key_cache):return original(cache,key,value,idx,cache_kwargs)
            with torch.cuda.nvtx.range('qwen3/KV_append'):return original(cache,key,value,idx,cache_kwargs)
        DynamicCache.update=update
        try:
            for _ in range(4):
                with torch.cuda.nvtx.range('decode/annotated_fixed'):out=work()
            torch.cuda.synchronize();assert torch.equal(out.logits,reference)
        finally:DynamicCache.update=original
    for _ in range(8):
        with torch.cuda.nvtx.range('decode/graph_fixed'):graph.replay()
    torch.cuda.synchronize();assert torch.equal(out.logits,reference)
    torch.cuda.cudart().cudaProfilerStop()
    result={'status':'completed','Slurm_job_id':os.environ['SLURM_JOB_ID'],'model_id':p['model']['id'],
      'revision':p['revision'],'prepared_sha256':digest(a.prepared),'source_sha256':digest(Path(__file__)),
      'executed_dependency_sha256':{f.name:digest(f) for f in a.executed_code.glob('*.py')},
      'GPU_name':torch.cuda.get_device_properties(0).name,'GPU_UUID_sha256':hashlib.sha256(uuid.encode()).hexdigest(),
      'context':2048,'batch':1,'dtype':'BF16/native internal precision','layers':len(model.model.layers),
      'captured_steps':{'eager_fixed':4,'annotated_fixed':4,'graph_fixed':8},'logits_bitwise_equal':True,
      'energy_measurement':False,'note':'tracing smoke only; profiler changes execution cost'}
    with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()

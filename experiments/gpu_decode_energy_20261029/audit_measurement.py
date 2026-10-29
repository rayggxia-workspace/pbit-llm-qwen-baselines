"""Long-window cross-check of NVML energy delta versus sampled power integral."""
import argparse,hashlib,json,os,statistics,sys,time
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer

def save(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=True,allow_nan=False);f.write('\n')

@torch.inference_mode()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepared',type=Path,required=True);p.add_argument('--executed-code',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=float,default=15)
    p.add_argument('--repeats',type=int,default=2);a=p.parse_args()
    assert 'SLURM_JOB_ID' in os.environ and torch.cuda.device_count()==1
    assert not a.output.exists();a.output.mkdir(parents=True)
    sys.path.insert(0,str(a.executed_code))
    from run_decode import verify,digest,tensor_hash,build_prefix,one,graph_callable,warm,exclusive
    from meter import Nvml,PowerSampler,integrate
    prepared,model_path=verify(a.prepared)
    expected={'meter.py':'a976d6482edaf5a78002f04d0a370011adf1f08555ef076cc963e166b1229777',
      'run_decode.py':'94e29b382be6ae7b1f478bdf7f67c68eca2112598be03f64af956ae3afc6bd43'}
    for name,sha in expected.items():assert digest(a.executed_code/name)==sha
    uuid=str(torch.cuda.get_device_properties(0).uuid)
    if not uuid.startswith('GPU-'):uuid='GPU-'+uuid
    meter=Nvml(uuid);exclusive(uuid)
    model=AutoModelForCausalLM.from_pretrained(str(model_path),torch_dtype=torch.bfloat16,
      attn_implementation='sdpa',local_files_only=True).eval().to('cuda')
    tokenizer=AutoTokenizer.from_pretrained(str(model_path),local_files_only=True)
    text=Path(prepared['data']['wiki.test.raw']['path']).read_text(encoding='utf-8')
    ids=torch.tensor(tokenizer(text,add_special_tokens=False).input_ids,dtype=torch.long)
    assert tensor_hash(ids)==prepared['test_token_ids_sha256_le_int64']
    legacy,token,_=build_prefix(model,ids[:2047].unsqueeze(0).to('cuda'))
    fn=lambda:one(model,legacy,token)
    reference=fn();graph,out=graph_callable(fn);assert torch.equal(out.logits,reference.logits)
    provenance={'Slurm_job_id':os.environ['SLURM_JOB_ID'],'model_id':prepared['model']['id'],
      'revision':prepared['revision'],'prepared_sha256':digest(a.prepared),'test_token_ids_sha256':tensor_hash(ids),
      'source_sha256':digest(Path(__file__)),'executed_dependency_sha256':expected,
      'context':2048,'batch':1,'seconds_target':a.seconds,'repeats':a.repeats,
      'GPU_name':torch.cuda.get_device_properties(0).name,'GPU_UUID_sha256':hashlib.sha256(uuid.encode()).hexdigest(),
      'graph_logits_bitwise_equal':True,'power_poll_interval_s':.02,
      'limits':['same NVML sensor family; not independent external calibration',
        'fixed shape forward excluding argmax/prefill; not new PPL or native generation',
        '15s steady windows and warmup reduce but do not quantify sensor systematic error']}
    save(a.output/'PROVENANCE.json',provenance)
    records=[]
    for label,work in [('resident_idle',lambda:time.sleep(.001)),('eager_fixed',fn),('graph_fixed',graph.replay)]:
        for repeat in range(a.repeats):
            sampler=PowerSampler(meter,.02).start();warm(work,4.)
            exclusive(uuid);torch.cuda.synchronize();state0=meter.state()
            t0=time.perf_counter();e0=meter.energy_mJ();n=0
            begin=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True);begin.record()
            while time.perf_counter()-t0<a.seconds:
                for _ in range(16):result=work();n+=1
                torch.cuda.synchronize()
            end.record();torch.cuda.synchronize();e1=meter.energy_mJ();t1=time.perf_counter()
            sampler.finish();assert not sampler.errors
            exclusive(uuid)
            counted=(e1-e0)/1000;power_energy=integrate(sampler.samples,t0,t1)
            row={'phase':label,'repeat':repeat,'iterations':n,'wall_s':t1-t0,'gpu_ms':begin.elapsed_time(end),
              'counter_energy_J':counted,'integrated_power_energy_J':power_energy,
              'counter_mean_W':counted/(t1-t0),'integrated_power_mean_W':power_energy/(t1-t0),
              'relative_difference_percent':100*(counted-power_energy)/power_energy,
              'counter_energy_J_per_forward':counted/n if label!='resident_idle' else None,
              'ms_per_forward':1000*(t1-t0)/n if label!='resident_idle' else None,
              'state_before':state0,'state_after':meter.state(),'power_sample_count':len(sampler.samples),
              'energy_read_start_mJ':e0,'energy_read_end_mJ':e1}
            save(a.output/(label+'_'+str(repeat)+'_POWER_SAMPLES.json'),{'start':t0,'end':t1,'samples':sampler.samples})
            records.append(row);save(a.output/(label+'_'+str(repeat)+'.json'),row)
            print(json.dumps(row),flush=True)
    summary={'status':'completed','records':records,'independent_external_validation':False,
      'counter_power_interface_agreement_only':True}
    save(a.output/'SUMMARY.json',summary)
    manifest={f.name:{'bytes':f.stat().st_size,'sha256':digest(f)} for f in a.output.iterdir() if f.is_file()}
    save(a.output/'ARTIFACT_MANIFEST.json',manifest)
    save(a.output/'COMPLETED.json',{'status':'completed','manifest_sha256':digest(a.output/'ARTIFACT_MANIFEST.json')})

if __name__=='__main__':main()

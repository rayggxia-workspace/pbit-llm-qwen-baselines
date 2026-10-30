"""Same-temperature-start whole-model repeats; independent Nsight trace mode.

Energy invocation runs without a profiler. --trace-only is a separate invocation
under nsys, never a source of primary joules or TPOT. Model math is unchanged.
"""
import argparse,gc,hashlib,json,os,sys,time
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepared',type=Path,required=True)
    p.add_argument('--executed-code',type=Path,required=True)
    p.add_argument('--controlled-code',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--trace-only',action='store_true')
    a=p.parse_args()
    expected='58d36200ed5fd4f8c3351f3ab39e8e590d3e452b6fc59296e0db139691ec6d07'
    assert hashlib.sha256((a.controlled_code/'controlled_remeasure.py').read_bytes()).hexdigest()==expected
    sys.path.insert(0,str(a.controlled_code))
    import controlled_remeasure as c
    c.load_dependencies(a.executed_code)
    torch=c.torch
    from transformers import AutoModelForCausalLM,AutoTokenizer
    assert 'SLURM_JOB_ID' in os.environ and torch.cuda.device_count()==1
    assert not a.output.exists();a.output.mkdir(parents=True)
    with torch.inference_mode():
        prepared,root=c.verify(a.prepared)
        tokenizer=AutoTokenizer.from_pretrained(str(root),local_files_only=True)
        ids=torch.tensor(tokenizer(Path(prepared['data']['wiki.test.raw']['path']).read_text(encoding='utf-8'),
            add_special_tokens=False).input_ids,dtype=torch.long)
        assert c.tensor_hash(ids)==prepared['test_token_ids_sha256_le_int64']
        uuid=str(torch.cuda.get_device_properties(0).uuid)
        if not uuid.startswith('GPU-'):uuid='GPU-'+uuid
        c.exclusive(uuid);meter=c.Nvml(uuid)
        model=AutoModelForCausalLM.from_pretrained(str(root),torch_dtype=torch.bfloat16,
            attn_implementation='sdpa',local_files_only=True).eval().to('cuda')
        c.save(a.output/'ENVIRONMENT.json',dict(job=os.environ['SLURM_JOB_ID'],source_sha256=c.digest(Path(__file__)),
            controlled_source_sha256=expected,prepared_sha256=c.digest(a.prepared),revision=prepared['revision'],
            token_ids_sha256=c.tensor_hash(ids),uuid_sha256=hashlib.sha256(uuid.encode()).hexdigest(),
            trace_only=a.trace_only,torch=torch.__version__,batch=1,model=prepared['model']['id'],dtype='BF16',
            target_start_temperature_C=40,tolerance_C=1,weight_change=False,
            protocol='interleaved three modes, three repeats; restore 40+/-1C before every window; no clock/power changes'))
        if a.trace_only:
            class NVTX(c.Instrument):
                def call(self,category,name,fn,*args,**kwargs):
                    with torch.cuda.nvtx.range('qwen3/'+str(self.context)+'/'+category):
                        return fn(*args,**kwargs)
            c.Instrument=NVTX
            inputs=[]
            for context in [2048,8192]:
                legacy,token,_=c.build_prefix(model,ids[:context-1].unsqueeze(0).to('cuda'))
                ref=c.one(model,legacy,token).logits.clone()
                static=c.StaticGQA(model,legacy,context)
                with static:
                    for _ in range(3):out=static.run(token)
                    assert torch.equal(out.logits,ref)
                inputs.append((context,static,token,ref))
            torch.cuda.synchronize();torch.cuda.cudart().cudaProfilerStart()
            for context,static,token,ref in inputs:
                with static:
                    with c.instrumented(model) as inst:
                        inst.context=context
                        for _ in range(4):out=static.run(token)
                    torch.cuda.synchronize();assert torch.equal(out.logits,ref)
            torch.cuda.cudart().cudaProfilerStop()
            c.save(a.output/'TRACE_COMPLETED.json',dict(status='completed',contexts=[2048,8192],steps_per_context=4,
                all_36_layers_annotated=True,logits_bitwise_equal=True,energy_measurement=False))
            return
        def reset_temperature(heater):
            start=time.perf_counter();states=[]
            torch.cuda.synchronize()
            while time.perf_counter()-start<120:
                state=meter.state();state['elapsed_s']=time.perf_counter()-start;states.append(state)
                if 39<=state['temperature_C']<=40:
                    time.sleep(.3)
                    final=meter.state()
                    if 39<=final['temperature_C']<=40:
                        return dict(states=states,seconds=time.perf_counter()-start,state_at_release=final,pass_target=True)
                elif state['temperature_C']<39:
                    until=time.perf_counter()+.25
                    while time.perf_counter()<until:
                        for _ in range(8):heater()
                        torch.cuda.synchronize()
                else:time.sleep(.5)
            raise RuntimeError('could not restore target start temperature; do not silently accept drift')
        for context in [2048,8192]:
            folder=a.output/str(context);folder.mkdir()
            legacy,token,_=c.build_prefix(model,ids[:context-1].unsqueeze(0).to('cuda'))
            original=lambda:c.one(model,legacy,token)
            ref=original().logits.clone()
            og,oo=c.graph_callable(original);assert torch.equal(oo.logits,ref)
            static=c.StaticGQA(model,legacy,context)
            with static:
                static_work=lambda:static.run(token)
                sg,so=c.graph_callable(static_work);assert torch.equal(so.logits,ref)
            results={mode:[] for mode in ['original_eager','original_graph','static_KV_graph']}
            # Latin-square order distributes slow ambient drift over modes.
            orders=[['original_eager','original_graph','static_KV_graph'],
                    ['original_graph','static_KV_graph','original_eager'],
                    ['static_KV_graph','original_eager','original_graph']]
            for repeat,order in enumerate(orders):
                for mode in order:
                    c.exclusive(uuid)
                    thermal=reset_temperature(og.replay)
                    fn={'original_eager':original,'original_graph':og.replay,'static_KV_graph':sg.replay}[mode]
                    row=c.measure_window(fn,meter,10.,repeat,telemetry=True)
                    row.update(thermal_reset=thermal,mode=mode)
                    assert 39<=row['state_before']['temperature_C']<=41
                    results[mode].append(row)
                    c.save(folder/(mode+'_'+str(repeat)+'.json'),row)
                    c.emit(dict(event='paired',context=context,mode=mode,repeat=repeat,
                        ms=row['wall_ms_per_item'],J=row['energy_mJ_per_item']/1000,
                        start_C=row['state_before']['temperature_C'],end_C=row['state_after']['temperature_C']))
            c.save(folder/'SUMMARY.json',{mode:c.summarize(rows) for mode,rows in results.items()})
            del og,oo,sg,so,static,legacy,token,ref,original,static_work,fn
            gc.collect();torch.cuda.empty_cache()
        c.exclusive(uuid)
        manifest={str(f.relative_to(a.output)):dict(sha256=c.digest(f),bytes=f.stat().st_size)
                  for f in a.output.rglob('*') if f.is_file()}
        c.save(a.output/'ARTIFACT_MANIFEST.json',manifest)
        c.save(a.output/'COMPLETED.json',dict(status='completed',job=os.environ['SLURM_JOB_ID'],contexts=[2048,8192],
           manifest_sha256=c.digest(a.output/'ARTIFACT_MANIFEST.json'),source_sha256=c.digest(Path(__file__))))


if __name__=='__main__':main()

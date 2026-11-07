"""Matched cached PPL; every scored target actually uses sampled Attention."""
from pathlib import Path
import argparse,gc,hashlib,json,math,os,sys,time

HERE=Path(__file__).resolve().parent
CASE=dict(id='strat32_coarse_sig',input_law='stratified_T',T_x=32,and_law='joint_grid',grid_g_sig_u=[4,2,4],T_and=32)

def save(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes((json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())

def score(model,context,tokens,mode,seed,out,decode=128,examples=8,batch=8,protocol='suffix',capture=False):
    import numpy as np
    import torch
    from torch.nn import functional as F
    from transformers import DynamicCache
    from experiments.sparq_ising_20261028.vendor.plans import suffix_plan,full_window_plan,plan_batches,plan_metadata
    from joint_attention import AttentionPatch
    plan=suffix_plan(len(tokens),2048,decode,examples) if protocol=='suffix' else full_window_plan(len(tokens),2048,1024)
    records=[];coverage=[0]*36;prefill=[0]*36;digest=hashlib.sha256();calls=0
    model.eval();start=time.monotonic();context.seed=seed
    with AttentionPatch(mode=='joint') as patch:
        ctl=patch.controller(model,seed)
        def forward(ids,cache,phase):
            nonlocal calls
            context.begin(0,calls,domain='joint242-cached');calls+=1
            output=model(ids,past_key_values=cache,use_cache=True,logits_to_keep=1)
            if len(context.coverage)!=36:raise AssertionError('FFN layer missing')
            expected=ids.numel()
            for layer,info in context.coverage.items():
                if info['calls']!=1 or info['tokens']!=expected:raise AssertionError('FFN coverage')
                (coverage if phase=='decode' else prefill)[layer]+=expected
            return output
        try:
            with torch.no_grad():
                for rows in plan_batches(plan,batch):
                    prefix,steps=rows[0]['prefill_tokens'],rows[0]['scored_tokens']
                    caches=[];ctl.prefix=True
                    # Prefill one sequence at a time to preserve the measured
                    # 20.4 GiB FFN peak; batch only single-token scoring.
                    if prefix:
                        for row in rows:
                            ids=torch.as_tensor(np.asarray(tokens[row['begin']:row['begin']+prefix],dtype=np.int64),device='cuda')[None]
                            result=forward(ids,None,'prefill')
                            caches.append(result.past_key_values)
                            del result,ids
                        legacy=tuple((torch.cat([c.key_cache[i] for c in caches]),
                                      torch.cat([c.value_cache[i] for c in caches])) for i in range(36))
                        cache=DynamicCache.from_legacy_cache(legacy);del legacy,caches
                    else:cache=None
                    ctl.prefix=False
                    losses=torch.zeros(len(rows),device='cuda',dtype=torch.float64)
                    for step in range(steps):
                        pos=prefix+step
                        ids=torch.tensor([[int(tokens[r['begin']+pos])] for r in rows],device='cuda')
                        target=torch.tensor([int(tokens[r['begin']+pos+1]) for r in rows],device='cuda')
                        result=forward(ids,cache,'decode');cache=result.past_key_values
                        logits=result.logits[:,-1].float()
                        if not torch.isfinite(logits).all():raise RuntimeError('nonfinite logits')
                        losses+=F.cross_entropy(logits,target,reduction='none').double()
                        if capture:digest.update(logits.cpu().contiguous().numpy().tobytes())
                    for row,nll in zip(rows,losses.tolist()):records.append(dict(row,nll_sum=nll))
                    save(out/'PROGRESS.json',dict(records=records,seconds=time.monotonic()-start,mode=mode,seed=seed))
                    del cache,result,logits,ids,target,losses
            total=sum(x['scored_tokens'] for x in records)
            if coverage!=[total]*36:raise AssertionError('scored FFN coverage')
            audit=ctl.report()
            if any(v['decode_queries']!=total for v in ctl.state.values()):raise AssertionError('attention coverage')
            if mode=='joint' and any(v['sampled_head_rows']!=total*32 for v in ctl.state.values()):raise AssertionError('sampler bypass')
            nll=sum(x['nll_sum'] for x in records)
            value=dict(status='completed',mode=mode,seed=seed,nll_sum=nll,targets=total,ppl=math.exp(nll/total),
                records=records,plan=plan_metadata(plan,len(tokens),protocol),protocol=protocol,
                scored_tokens_per_layer=coverage,prefill_tokens_per_layer=prefill,attention=audit,
                quantization=patch.gap.report(),seconds=time.monotonic()-start,
                logits_sha256=digest.hexdigest() if capture else None,
                ffn='original BF16' if mode=='bf16' else CASE,
                prefill_attention='exact BF16 SDPA; all scored targets single-token replaced',
                peak_allocated_GiB=torch.cuda.max_memory_allocated()/2**30)
            save(out/'RESULT.json',value);return value
        finally:ctl.close()

def cpu(out):
    import torch,unittest
    from experiments.attention_gap_accuracy_20261102.methods import gap_probability,load_table
    z=torch.tensor([[12.,10.,6.,-200.],[100.,98.,94.,-112.]])
    p,address,threshold,metrics=gap_probability(z,'ising64_gap_s12_p8',load_table())
    assert address.tolist()==[[0,32,96,255],[0,32,96,255]]
    assert threshold.tolist()==[[128,30,0,0],[128,30,0,0]]
    assert load_table().tolist()==[int(256/(1+math.exp(i/16))) for i in range(256)]
    # This table produces exact R8 threshold probabilities; never sigmoid(z/scale)
    # on an independently rescaled g/u or an absolute signed8 score.
    x=torch.arange(256)
    assert all(int((x<int(t)).sum())==int(t) for t in load_table())
    from sampling import joint_counts,shared_input_counts
    generator=torch.Generator().manual_seed(101)
    code=torch.tensor([[0,128,256]+[128]*61])
    assert shared_input_counts(code,32,generator)[0,:3].tolist()==[0,16,32]
    assert joint_counts([torch.full((64,),256)]*3,32,(4,2,4),generator).tolist()==[32]*64
    save(out/'CPU.json',dict(status='PASS',checks=6,quantization='S12/F4 -> max difference -> U8/F4 saturation -> floor-P8',
        no_cuda=not torch.cuda.is_initialized(),grid=[4,2,4]))

def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['cpu','gate','evaluate'],required=True)
    p.add_argument('--mode',choices=['bf16','ffn_only','joint'],default='joint');p.add_argument('--seed',type=int,default=101)
    p.add_argument('--inputs',type=Path,default=HERE/'INPUTS.json');p.add_argument('--runtime',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--protocol',choices=['suffix','full'],default='suffix')
    p.add_argument('--decode',type=int,default=128);p.add_argument('--examples',type=int,default=8);p.add_argument('--batch',type=int,default=8)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    if a.phase=='cpu':cpu(a.out);return
    import numpy as np,torch
    sys.path.insert(0,str(a.runtime))
    from run_wt2 import prepare,load_model
    from adapter import SamplingOverride
    inputs,tokens,ledger,protocol=prepare(a.inputs,a.runtime,a.out)
    model,context,modules,identity=load_model(inputs,native=a.mode=='bf16')
    immutable=[(x,x.data_ptr(),x._version) for x in model.parameters()]
    immutable += [(x,x.data_ptr(),x._version) for m in modules for x in m.buffers()]
    patch=SamplingOverride(CASE)
    if modules:patch.configure(modules)
    save(a.out/'IDENTITY.json',dict(identity=identity,protocol=protocol,args=vars(a)|{'inputs':str(a.inputs),'runtime':str(a.runtime),'out':str(a.out)},
        job=os.environ.get('SLURM_JOB_ID'),versions=dict(torch=torch.__version__),ffn_case=CASE,no_training=True))
    with patch:
        if a.phase=='gate':
            from joint_attention import AttentionPatch
            from experiments.sparq_ising_20261028 import core
            from experiments.sparq_ising_20261028.vendor import kernels
            # Literal byte-frame replay checks the parallel bits, uniform active
            # rank and hold/empty behavior, independently of model PPL.
            with AttentionPatch(True) as ap:
                z=torch.tensor([[12.,11.,10.,9.],[0.,0.,0.,0.]],device='cuda')
                pp=ap.gap.probabilities(z,'winner')[:,0]
                gen=torch.Generator(device='cuda').manual_seed(73)
                u=torch.randint(256,(2,8,4),device='cuda',generator=gen).float()/256
                raw=torch.full((2,8),2147483647,device='cuda',dtype=torch.int64)
                coins=torch.zeros((2,8),device='cuda')
                indices,stats=kernels.sample(z,8,'winner',burn=0,seed=73,replay=(u,raw,coins))
                bits=u<pp[:,None,:]
                ranks=raw%bits.sum(-1).clamp_min(1)
                oracle=core.torch_winner_replay(bits,ranks,torch.zeros(2,device='cuda',dtype=torch.long),0)
                assert torch.equal(indices,oracle),'P8 winner state replay'
            # Exact same FFN RNG keys and call shapes: wrapper cfg=None must
            # reproduce the unwrapped model logits before sampled evaluation.
            ids=torch.as_tensor(tokens[:32].astype(np.int64),device='cuda')[None]
            context.seed=101;context.begin(0,0,domain='joint242-gate')
            with torch.no_grad():ref=model(ids,use_cache=False).logits
            with AttentionPatch(False) as ap:
                ctl=ap.controller(model,101);ctl.prefix=True
                context.begin(0,0,domain='joint242-gate')
                with torch.no_grad():got=model(ids,use_cache=False).logits
                ctl.close()
            assert torch.equal(ref,got),'no-op wrapper changed logits'
            del ref,got,ids
            torch.cuda.reset_peak_memory_stats()
            result=score(model,context,tokens,'joint',101,a.out/'pilot',decode=8,examples=2,batch=2)
            assert all((m.last_arithmetic['T_x'],m.last_arithmetic['T_AND'])==(32,32) for m in modules)
            save(a.out/'GATE.json',dict(status='PASS',wrapper_bitwise=True,p8_byte_replay=True,pilot=result,
                 weights_unchanged=all(x.data_ptr()==ptr and x._version==ver for x,ptr,ver in immutable)))
        else:
            torch.cuda.reset_peak_memory_stats()
            score(model,context,tokens,a.mode,a.seed,a.out,decode=a.decode,examples=a.examples,batch=a.batch,protocol=a.protocol)
    assert all(x.data_ptr()==ptr and x._version==ver for x,ptr,ver in immutable),'model changed'
    from run_wt2 import sha
    files={str(x.relative_to(a.out)):sha(x) for x in a.out.rglob('*') if x.is_file()}
    save(a.out/'COMPLETE.json',dict(status='completed',documents=files,no_training=True))

if __name__=='__main__':main()

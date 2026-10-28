"""Bounded 256-target all-layer suffix PPL; not full WT2 acceptance."""
import torch,math
from .quantize import signed,gap,thresholds
from experiments.sparq_ising_20261028.core import Config
from experiments.sparq_ising_20261028.scoring import score
from experiments.sparq_ising_20261028.vendor import kernels

def run_quality(model,ids,out,save):
    original=kernels.probabilities
    variant=['ideal'];calls=[0];clipped=[0];entries=[0]
    def wrapped(logits,method):
        assert method=='winner'
        if variant[0]=='ideal':return original(logits,method)
        bits,frac=(8,1) if variant[0]=='i8_f1' else (11,4)
        q,c=signed(logits.float(),bits,frac)
        calls[0]+=1;clipped[0]+=int(c.sum());entries[0]+=c.numel()
        table=original(q,method)
        if variant[0]!='i8_f1':
            g,_=gap(q,8,4);pb=12 if variant[0].endswith('p12') else 16
            p,_,_,_,valid=thresholds(g,pb);assert valid.all()
            # The winner kernel reads plane 0 only; retain q argmax marker.
            table[:,0,:]=p
        return table
    # Independent 256-entry Python LUT versus tensor implementation.
    for b in (12,16):
        addr=torch.arange(256,device=model.device,dtype=torch.float32)
        p,*_=thresholds((-addr/16)[None,:],b)
        golden=torch.tensor([round((2**b)/(1+math.exp(a/16)))/(2**b) for a in range(256)],device=model.device)
        assert torch.equal(p[0],golden)
    kernels.probabilities=wrapped
    params=[(p,p._version,p.data_ptr()) for p in model.parameters()]
    results=[]
    try:
        gate=dict(context=256,decode=4,examples=2,batch=2,capture=True)
        native=score(model,ids,None,native=True,**gate);control=score(model,ids,None,**gate)
        assert native['logits_sha256']==control['logits_sha256'] and native['nll_sum']==control['nll_sum']
        save(out/'PPL_GATE.json',dict(native_wrapper_byte_equal=True,native=native,wrapper=control,lut_entries_verified=512))
        options=dict(context=2048,decode=64,examples=4,batch=4)
        cases=[('bf16',None,0,'ideal'),('sparq_exact',Config(mode='exact'),0,'ideal')]
        for name in ('ideal','i8_f1','i11_gap_p12','i11_gap_p16'):
            for seed in (0,1,2):cases.append((name,Config(),seed,name))
        for name,cfg,seed,kind in cases:
            variant[0]=kind;calls[0]=clipped[0]=entries[0]=0
            print('PPL_START',name,seed,flush=True)
            result=score(model,ids,cfg,seed=seed,**options)
            assert result['tokens_per_layer']==[256]*36
            assert all(p._version==version and p.data_ptr()==ptr for p,version,ptr in params)
            result.update(case=name,seed=seed,score_quantization=kind,quantized_calls=calls[0],saturated_score_entries=clipped[0],score_entries=entries[0])
            if kind!='ideal':
                assert calls[0]==36*64
                result['audit']['ideal_sigmoid_source']=kind=='i8_f1'
                result['audit']['finite_threshold_bits']=12 if kind.endswith('p12') else (16 if kind.endswith('p16') else None)
            result['audit']['rng_pairing']='same cfg, seed, layer and call keys across quantization variants; hidden states and candidates may differ'
            results.append(result)
            save(out/f'PPL_{name}_seed{seed}.json',result)
            print('PPL_DONE',name,seed,result['perplexity'],flush=True)
        assert all(r['plan']==results[0]['plan'] and r['token_ids_sha256']==results[0]['token_ids_sha256'] for r in results)
        save(out/'PPL_COMPLETE.json',dict(cases=len(results),targets_per_case=256,protocol='4 evenly spaced WT2 windows, context2048, suffix64; dense native prefill; all36layers on every scored token',
            variants={n:[r['perplexity'] for r in results if r['case']==n] for n in {r['case'] for r in results}},
            limits=['not full WT2 PPL; 256 targets only','S128 burn32; independent Philox, no physical RNG/RTL','no train fitting of score step or threshold on PPL suffix','Q/K multiplication, original FFN and all other model parts unchanged']))
    finally:kernels.probabilities=original

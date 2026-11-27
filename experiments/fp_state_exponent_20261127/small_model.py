"""Independent stochastic-FFN replay on real 0.5B Instruct activations; BF16 model stays unchanged."""
from pathlib import Path
import argparse,hashlib,json,math,os,sys

def quantize_numpy(x):
    import numpy as np
    x=np.asarray(x,dtype=np.float32);no,ni=x.shape
    assert no%64==0 and ni%64==0 and np.isfinite(x).all()
    peak=np.abs(x).reshape(no//64,64,ni//64,64).max((1,3));m,e=np.frexp(peak/np.float32(127))
    exp=np.where(peak==0,-24,e-(m==.5)).astype(np.int64);scale=np.ldexp(np.ones_like(peak),exp)
    expanded=scale.repeat(64,0).repeat(64,1);q=np.rint(x/expanded).clip(-127,127).astype(np.int8)
    assert np.all(np.abs(x)<=expanded*127)
    return q,scale

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--model',type=Path,required=True)
    ap.add_argument('--original',type=Path,required=True);ap.add_argument('--dependency',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and not a.output.exists()
    raw=(a.model/'MODEL_MANIFEST.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==(a.model/'MODEL_MANIFEST.sha256').read_text().strip()
    model_id=json.loads(raw);assert model_id['model']=='Qwen/Qwen2.5-0.5B-Instruct'
    assert model_id['revision']=='7ae557604adf67be50417f59c2c2f167def9a775'
    for x in model_id['files']:assert hashlib.sha256((a.model/x['name']).read_bytes()).hexdigest()==x['sha256']
    settings=json.loads((a.original/'SETTINGS.json').read_bytes())
    source=a.original/'source'
    mf=json.loads((source/'EXECUTION_MANIFEST.json').read_bytes())
    for n,h in mf['files'].items():assert hashlib.sha256((source/n).read_bytes()).hexdigest()==h,n
    sys.path.insert(0,settings['runtime'])
    sys.path.insert(0,str(source/'experiments/t64_dynamic_scale_20261125'))
    sys.path.insert(0,str(source/'experiments/t64_group64_onebit_20261126'))
    sys.path.insert(0,str(source/'experiments/t64_onebit_half_20261126'))
    sys.path.insert(0,str(a.dependency))
    import torch,numpy as np
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from torch.nn import functional as F
    import seven_forward as sf,wide_wd
    from half import encode
    from sampling import shared_input_counts,joint_counts
    from qwen3.training.sc_qat.evaluate import spans,TEXT_SHA
    from evaluate_trace import evaluate,summarize as numeric_summary
    from audit import analyze,summarize as range_summary
    from score_reference import save
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.use_deterministic_algorithms(True)
    inp=json.loads(Path(settings['inputs']).read_bytes());text_path=Path(inp['text'])
    assert hashlib.sha256(text_path.read_bytes()).hexdigest()==TEXT_SHA
    tokenizer=AutoTokenizer.from_pretrained(a.model,local_files_only=True,trust_remote_code=False)
    tokens=np.asarray(tokenizer.encode(text_path.read_text(encoding='utf-8'),add_special_tokens=False),dtype='<u4')
    ledger=list(spans(len(tokens)));a.output.mkdir(parents=True);(a.output/'trace').mkdir()
    model=AutoModelForCausalLM.from_pretrained(a.model,torch_dtype=torch.bfloat16,attn_implementation='sdpa',local_files_only=True).cuda().eval()
    cfg=model.config;assert (cfg.num_hidden_layers,cfg.hidden_size,cfg.intermediate_size)==(24,896,4864) and cfg.eos_token_id==151645
    layers=model.model.layers;baseline=[]
    with torch.no_grad():
        for wi,(start,end,first) in enumerate(ledger):
            ids=torch.as_tensor(tokens[start:end].astype('int64'),device='cuda')[None]
            logits=model(ids,use_cache=False).logits[0];nll=logits.new_zeros((),dtype=torch.float32)
            for lo in range(first-start-1,end-start-1,128):
                hi=min(end-start-1,lo+128);nll+=F.cross_entropy(logits[lo:hi].float(),ids[0,lo+1:hi+1],reduction='sum')
            baseline.append(dict(window=wi,start=start,end=end,first_scored=first,targets=end-first,nll_sum=float(nll),
             target_token_sha256=hashlib.sha256(tokens[first:end].tobytes()).hexdigest()))
            del logits,ids,nll
    total=sum(x['targets'] for x in baseline);loss=sum(x['nll_sum'] for x in baseline)
    save(a.output/'BF16_WINDOWS.json',baseline)
    save(a.output/'BF16_BASELINE.json',dict(status='completed',windows=len(baseline),targets=total,nll_sum=loss,ppl=math.exp(loss/total)))
    cache={};weight_meta=[];numeric=[];ranges=[];traces=[];probe=[]
    lut=torch.tensor([math.floor(256/(1+math.exp(-i/8))+.5) for i in range(-128,128)],device='cuda',dtype=torch.int64)
    def quant(w):
        x=w.detach().float().cpu().numpy();q,scale=quantize_numpy(x)
        meta=dict(shape=list(x.shape),codes_sha256=hashlib.sha256(q.tobytes()).hexdigest(),scales_sha256=hashlib.sha256(scale.tobytes()).hexdigest())
        return torch.from_numpy(q).cuda().contiguous(),torch.from_numpy(scale).cuda().contiguous(),meta
    def record(role,layer,fragment,c,s,h,w,cf,ex,T,R,ref,positions):
        n=w.shape[0]
        if role=='GU':
            half=n//128;gs=[0,half//2,half-1];blocks=gs+[x+half for x in gs]
        else:blocks=[0,1,n//64-2,n//64-1]
        cols=torch.cat([torch.arange(x*64,(x+1)*64,device='cuda') for x in blocks])
        cs=c.cpu().numpy().astype(np.int64);ss=s.cpu().numpy().astype(np.int64);hs=h.cpu().numpy().astype(np.int64)
        ws=w[cols].cpu().numpy().astype(np.int64);G=c.shape[-1]//64;hi=hs.reshape(4,G,64).max(-1);lo=hs.reshape(4,G,64).min(-1)
        assert (hi-lo).max()<=2
        parts=[]
        for k in range(G):
            local=(cs[:,64*k:64*(k+1)]<<(hi[:,k,None]-hs[:,64*k:64*(k+1)]))*ss[:,64*k:64*(k+1)]
            parts.append(local@ws[:,64*k:64*(k+1)].T)
        rr=ref[:,cols].contiguous();ee=ex[blocks].contiguous()
        z=dict(parts=np.stack(parts),hi=hi,minimum_shift=lo,coeff=cf[blocks].cpu().numpy(),ex=ee.cpu().numpy(),
          reference=rr.cpu().numpy(),samples=np.array(T),R=np.array(R),role=np.array(role),layer=np.array(layer),fragment=np.array(fragment),
          rows=np.array(positions),columns=cols.cpu().numpy(),g_cap=np.array(256.),u_cap=np.array(256.))
        if role=='GU':z['reference_fp32']=sf.finish_fp32(rr,ee,T,R).cpu().numpy()
        else:z['reference_bf16']=sf.finish_bf16(rr,ee-R,T).view(torch.int16).cpu().numpy().view(np.uint16)
        p=a.output/'trace'/('%d_%02d_%s.npz'%(fragment,layer,role));np.savez_compressed(p,**z)
        nr=evaluate(z);nr.update(layer=layer,fragment=fragment);numeric.append(nr)
        ar=analyze(z);ar.update(layer=layer,fragment=fragment);ranges.append(ar)
        traces.append(dict(name=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    def hook(layer,fragment,positions):
        def run(module,args):
            x=args[0].reshape(-1,896)[positions].float()
            if layer not in cache:
                assert module.gate_proj.bias is None and module.up_proj.bias is None and module.down_proj.bias is None
                wg,sg,mg=quant(module.gate_proj.weight);wu,su,mu=quant(module.up_proj.weight);wd,sd,md=quant(module.down_proj.weight)
                cache[layer]=(torch.cat((wg,wu),0).contiguous(),torch.cat((sg,su),0).contiguous(),wd,sd)
                weight_meta.append(dict(layer=layer,g=mg,u=mu,d=md))
            gu,gl,wd,dl=cache[layer];xc=encode(x,512.,True,1)
            gen=torch.Generator(device='cuda').manual_seed(101+fragment*10000+layer*100+1)
            c=shared_input_counts(xc['q'],16,gen);cf,ex=sf.exact_coefficients(gl,gl.new_full((14,),512.),gl.new_ones(14))
            R=int(xc['shift'].max());ref=wide_wd.shifted_output(c.contiguous(),xc['sign'].contiguous(),xc['shift'].contiguous(),gu,cf,16,R)
            record('GU',layer,fragment,c,xc['sign'],xc['shift'],gu,cf,ex,16,R,ref,positions)
            g,u=sf.finish_fp32(ref,ex,16,R).chunk(2,-1);gc=encode(g,256.,True,1);uc=encode(u,256.,True,1)
            field=sf.sigmoid_field(gc['q'],gc['sign'],gc['exponent']);hq=lut[field+128]
            gen=torch.Generator(device='cuda').manual_seed(101+fragment*10000+layer*100+2)
            c=joint_counts((gc['q'],hq,uc['q']),32,(4,2,4),gen);s=gc['sign']*uc['sign'];h=gc['shift']+uc['shift'];R=int(h.max())
            cf,ex=sf.exact_coefficients(dl,dl.new_full((76,),256.),dl.new_full((76,),256.))
            ref=wide_wd.shifted_output(c.contiguous(),s.contiguous(),h.contiguous(),wd,cf,32,R)
            record('Wd',layer,fragment,c,s,h,wd,cf,ex,32,R,ref,positions)
            save(a.output/'PROGRESS.json',dict(status='running',projections=len(numeric),range_summary=range_summary(ranges)))
        return run
    with torch.no_grad():
        for fragment,wi in enumerate([0,len(ledger)//2,len(ledger)-1]):
            start,end,_=ledger[wi];ids=torch.as_tensor(tokens[start:end].astype('int64'),device='cuda')[None]
            before=model(ids,use_cache=False).logits.detach();positions=[0,1,(end-start)//2,end-start-1]
            handles=[m.mlp.register_forward_pre_hook(hook(i,fragment,positions)) for i,m in enumerate(layers)]
            try:after=model(ids,use_cache=False).logits.detach()
            finally:
                for handle in handles:handle.remove()
            assert torch.equal(before,after),'diagnostic hook changed native model'
            probe.append(dict(fragment=fragment,window=wi,tokens=end-start,positions=positions,native_logits_bitwise=True,
             input_ids_sha256=hashlib.sha256(tokens[start:end].tobytes()).hexdigest()))
            del before,after,ids
    assert len(numeric)==144 and len(traces)==144
    save(a.output/'RESULT.json',dict(status='completed',model=model_id,config=dict(layers=24,hidden=896,intermediate=4864),
       scope='native BF16 layer inputs; independent stochastic W8 FFN replay; no stochastic model PPL',seed=101,GU=16,Wd=32,
       baseline=dict(windows=len(baseline),targets=total,ppl=math.exp(loss/total)),text_sha256=TEXT_SHA,token_sha256=hashlib.sha256(tokens.tobytes()).hexdigest(),
       probes=probe,weight_quantization=weight_meta,numerical_summary=numeric_summary(numeric),range_summary=range_summary(ranges),
       cases=numeric,range_cases=ranges,traces=traces,no_training=True,no_PPA=True,job=os.environ['SLURM_JOB_ID']))

if __name__=='__main__':main()

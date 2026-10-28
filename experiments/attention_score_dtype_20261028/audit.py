"""Native Qwen3 SDPA dispatch and isolated BF16 score rounding, not PPL."""
import argparse,hashlib,inspect,json,math,os,time,importlib.metadata
from pathlib import Path
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM,AutoTokenizer
from experiments.sparq_ising_20261028.vendor.support import sha256,verify_files,check_config
from experiments.sparq_ising_20261028.vendor.plans import ids_sha256
from experiments.sparq_ising_20261028.core import select,Config

def digest(x):return hashlib.sha256(x.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()
def save(p,x):
    assert not p.exists(),p
    p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())
def diffs(x,y):
    x,y=x.double(),y.double();e=x-y
    return dict(max_abs=e.abs().max().item(),rms=e.square().mean().sqrt().item(),
        relative_rms=(e.square().mean().sqrt()/y.square().mean().sqrt().clamp_min(1e-30)).item(),equal=bool(torch.equal(x,y)))
def probability(p,ref):
    tv=(p-ref).abs().sum(-1)/2
    return dict(tv_mean=tv.mean().item(),tv_max=tv.max().item(),tv_per_head=tv.flatten().tolist(),
        max_abs=(p-ref).abs().max().item(),argmax_changes=int((p.argmax(-1)!=ref.argmax(-1)).sum()))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args()
    root=Path(a.root).resolve();assert root.parent==Path('/home/Hongjie_Zeng/projects/attention-sparq-ising-issue198-20261028')
    assert root.stat().st_uid==os.getuid() and os.environ.get('SLURM_JOB_ID') and torch.cuda.device_count()==1
    src=Path(__file__).resolve().parents[2];manifest=json.loads((src/'execution.json').read_bytes())
    for name,h in manifest['files_sha256'].items():assert sha256(src/name)==h,name
    cfg=json.loads((src/'experiments/sparq_ising_20261028/config.json').read_bytes())
    prep=json.loads(Path(cfg['prepared']).read_bytes());assert prep['model']==cfg['model'];verify_files(prep)
    for name,h in cfg['data_sha256'].items():assert sha256(Path(cfg['data_root'])/name)==h
    assert importlib.metadata.version('transformers')=='4.51.3'
    torch.set_num_threads(4);torch.manual_seed(0)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    tok=AutoTokenizer.from_pretrained(prep['local_path'],local_files_only=True,trust_remote_code=False)
    ids=tok((Path(cfg['data_root'])/'wiki.test.raw').read_bytes().decode('utf-8'),return_tensors='pt',add_special_tokens=False).input_ids[0]
    assert ids_sha256(ids.tolist())==prep['test_token_ids_sha256_le_int64']
    model=AutoModelForCausalLM.from_pretrained(prep['local_path'],local_files_only=True,trust_remote_code=False,torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval()
    check_config(model.config,cfg['model']);original=F.scaled_dot_product_attention
    import transformers.models.qwen3.modeling_qwen3 as native
    import transformers.integrations.sdpa_attention as sdpa
    out=root/'results';out.mkdir(exist_ok=False)
    save(out/'provenance.json',dict(source=manifest,model=cfg['model'],model_files=prep['files'],data_sha256=cfg['data_sha256'],token_ids_sha256=ids_sha256(ids.tolist()),
        versions={n:importlib.metadata.version(n) for n in ['torch','transformers','triton']},gpu=torch.cuda.get_device_name(),job=os.environ['SLURM_JOB_ID'],seed=0,
        native_source_sha256={m.__name__:sha256(Path(inspect.getfile(m))) for m in [native,sdpa]},tf32=False,
        scope='native trajectories, four text windows, selected layers/all heads; isolated local arithmetic, not modified-model PPL; no stochastic draws'))
    state=dict(layer=-1,capture=False,case=None);rows=[];profiles=[];baseline=[];hooks=[]
    for i,layer in enumerate(model.model.layers):
        def mark(module,args,index=i):state['layer']=index
        hooks.append(layer.self_attn.register_forward_pre_hook(mark))
    def profiled(q,k,v,**kw):
        with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU]) as prof:
            y=original(q,k,v,**kw);torch.cuda.synchronize()
        keys=sorted({e.key for e in prof.key_averages() if any(s in e.key.lower() for s in ['attention','softmax','bmm'])})
        return y,keys
    def analyze(q,k,v,base,scope,kw):
        assert q.dtype==k.dtype==v.dtype==torch.bfloat16
        z=torch.matmul(q.float(),k.float().transpose(-1,-2))*kw['scale']
        zb=z.bfloat16();p=z.softmax(-1);pb=F.softmax(zb,dim=-1,dtype=torch.float32)
        ref=p@v.float();rounded=pb@v.float()
        # Also execute actual eager-style BF16 matmul output, scaling, FP32
        # softmax, BF16 probabilities and BF16 PV as a separate full path.
        ze=(q@k.transpose(-1,-2))*kw['scale']
        pe=F.softmax(ze,dim=-1,dtype=torch.float32).to(q.dtype);eager=pe@v
        assert ze.dtype==zb.dtype==torch.bfloat16 and torch.isfinite(eager).all()
        row=dict(case=state['case'],layer=state['layer'],scope=scope,q_shape=list(q.shape),k_shape=list(k.shape),input_dtype=str(q.dtype),
            score_only_dtype=str(zb.dtype),eager_score_dtype=str(ze.dtype),native_output_dtype=str(base.dtype),
            q_sha256=digest(q),k_sha256=digest(k),v_sha256=digest(v),score_fp32_sha256=digest(z),score_bf16_sha256=digest(zb),native_sha256=digest(base),
            score_rounding=diffs(zb,z),probability=probability(pb,p),output_rounding_only=diffs(rounded,ref),
            output_rounding_only_cast_bf16=diffs(rounded.bfloat16(),ref.bfloat16()),native_vs_fp32_reference=diffs(base,ref),
            eager_vs_native=diffs(eager,base),score_min=z.min().item(),score_max=z.max().item())
        rows.append(row)
    def wrapped(q,k,v,*args,**kw):
        assert not args
        if not state['capture'] or state['layer'] not in [0,12,23,35]:return original(q,k,v,**kw)
        assert q.shape[-2]==1 and kw.get('attn_mask') is None and not kw.get('is_causal',False) and kw['dropout_p']==0
        base,keys=profiled(q,k,v,**kw)
        profiles.append(dict(case=state['case'],layer=state['layer'],scope='native_full',q_shape=list(q.shape),k_shape=list(k.shape),operators=keys))
        analyze(q,k,v,base,'full_kv',kw)
        b,h,_,d=q.shape;n=k.shape[-2]
        assert h==32 and torch.equal(k[:,0],k[:,3]) and torch.equal(k[:,4],k[:,7])
        indices,zero=select(q.float().reshape(b,8,4,d),k[:,::4].float(),Config())
        assert not zero.any()
        index=indices[:,:,None,:].expand(b,8,4,128).reshape(b,32,128)
        gather=index[:,:,:,None].expand(b,32,128,d)
        ck,cv=k.gather(2,gather),v.gather(2,gather)
        candidate,keys=profiled(q,ck,cv,**kw)
        profiles.append(dict(case=state['case'],layer=state['layer'],scope='fixed_sparq128',q_shape=list(q.shape),k_shape=list(ck.shape),operators=keys,candidate_ids_sha256=digest(index)))
        analyze(q,ck,cv,candidate,'fixed_sparq128',kw)
        return base
    F.scaled_dot_product_attention=wrapped
    started=time.time()
    try:
        with torch.inference_mode():
            for n in [512,2048]:
                for start in [0,4096]:
                    state['case']=f'N{n}_start{start}';tokens=ids[start:start+n].unsqueeze(0).cuda();pred=[]
                    for repeat in [0,1]:
                        state['capture']=False
                        cache=model.model(tokens[:,:-1],use_cache=True).past_key_values
                        state['capture']=repeat==0
                        result=model.model(tokens[:,-1:],past_key_values=cache,use_cache=True)
                        pred.append(model.lm_head(result.last_hidden_state[:,-1]).detach().clone())
                        del result,cache
                    assert torch.equal(pred[0],pred[1]),'native baseline changed by diagnostic hook'
                    baseline.append(dict(case=state['case'],native_repeats_equal=True,logits_sha256=digest(pred[0]),token_slice_sha256=ids_sha256(tokens[0].cpu().tolist())))
                    print('DONE',state['case'],flush=True)
        assert len(rows)==32 and len(profiles)==32 and len(baseline)==4
    finally:
        F.scaled_dot_product_attention=original
        for h in hooks:h.remove()
    save(out/'RESULTS.json',dict(rows=rows,profiles=profiles,native_baseline=baseline,seconds=time.time()-started,
        limits=['32 local comparisons, 16 native query-layer inputs, 512 native head rows plus same 512 restricted to 128 candidates','single deterministic numerical run; seed0, no Monte Carlo','not all-layer modified PPL or proof of universal BF16 tolerance','CPU operator profiler identifies dispatch, not every internal register dtype','BF16 score-only case isolates one rounding boundary; FP32 PV prevents other rounding from confounding']))
    save(out/'COMPLETE.json',dict(status='completed',files={p.name:dict(sha256=sha256(p),bytes=p.stat().st_size) for p in out.glob('*.json')}))
    print('COMPLETE',flush=True)
if __name__=='__main__':main()

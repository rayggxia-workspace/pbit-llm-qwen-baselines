"""All-layer native-trajectory score/LUT audit; never substitute model output."""
import argparse,hashlib,json,os,time,importlib.metadata,math
from pathlib import Path
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM,AutoTokenizer
from experiments.sparq_ising_20261028.vendor.support import sha256,verify_files,check_config,verify_source
from experiments.sparq_ising_20261028.vendor.plans import ids_sha256
from experiments.sparq_ising_20261028.core import select,Config
from experiments.sparq_ising_20261028.vendor.kernels import _sample
from .quantize import designs,thresholds,selftest

def save(p,x):
    assert not p.exists(),p
    p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())

def digest(x):return hashlib.sha256(x.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()

def finite(p,v,initial,seed):
    h,n=p.shape;cap=160
    table=p[:,None,:].expand(h,26,n).clone()
    table[:,25,:]=torch.zeros_like(p).scatter_(1,initial[:,None],1.)
    out=torch.full((h,128),-1,device=p.device,dtype=torch.int64)
    stats=torch.empty((h,6),device=p.device,dtype=torch.int64)
    _sample[(h,)](table,out,stats,table,table,table,SEED=seed,N=n,S=128,CAP=cap,WINNER=True,BURN=32,REPLAY=False,BLOCK=n,num_warps=4)
    assert ((out>=0)&(out<n)).all() and (stats[:,1]==128).all()
    hist=torch.zeros_like(p).scatter_add_(1,out,torch.ones_like(out,dtype=p.dtype))/128
    return hist,(hist[:,None,:]@v.float()).squeeze(1)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args()
    root=Path(a.root).resolve();assert root.parent==Path('/home/Hongjie_Zeng/projects/attention-sparq-ising-issue198-20261028')
    assert root.stat().st_uid==os.getuid() and os.environ.get('SLURM_JOB_ID') and torch.cuda.device_count()==1
    src=Path(__file__).resolve().parents[2];manifest=verify_source(src);selftest()
    cfg=json.loads((src/'experiments/sparq_ising_20261028/config.json').read_bytes())
    prep=json.loads(Path(cfg['prepared']).read_bytes());assert prep['model']==cfg['model'];verify_files(prep)
    for name,h in cfg['data_sha256'].items():assert sha256(Path(cfg['data_root'])/name)==h
    assert importlib.metadata.version('transformers')=='4.51.3'
    torch.set_num_threads(4);torch.manual_seed(0)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    tok=AutoTokenizer.from_pretrained(prep['local_path'],local_files_only=True,trust_remote_code=False)
    ids={s:tok((Path(cfg['data_root'])/f'wiki.{s}.raw').read_bytes().decode(),return_tensors='pt',add_special_tokens=False).input_ids[0] for s in ('train','test')}
    assert ids_sha256(ids['test'].tolist())==prep['test_token_ids_sha256_le_int64']
    model=AutoModelForCausalLM.from_pretrained(prep['local_path'],local_files_only=True,trust_remote_code=False,torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval()
    check_config(model.config,cfg['model']);original=F.scaled_dot_product_attention
    out=root/'results';out.mkdir(exist_ok=False)
    save(out/'provenance.json',dict(source=manifest,model=cfg['model'],model_files=prep['files'],data_sha256=cfg['data_sha256'],token_sha256={s:ids_sha256(x.tolist()) for s,x in ids.items()},
        versions={n:importlib.metadata.version(n) for n in ('torch','transformers','triton')},gpu=torch.cuda.get_device_name(),job=os.environ['SLURM_JOB_ID'],tf32=False,
        seeds=[0,1,2],context=2048,train_starts=[0,8192,16384,24576],test_starts=list(range(0,32768,4096)),scope='native trajectory; fixed SparQ128; no modified-model PPL'))
    state=dict(layer=-1,capture=False,split=None,case=None);hooks=[];rows=[];samples=[];baseline=[];inputs=[]
    calabs=torch.zeros((36,32,1),device='cuda');calmax=torch.full_like(calabs,-torch.inf)
    for i,layer in enumerate(model.model.layers):
        def mark(module,args,index=i):state['layer']=index
        hooks.append(layer.self_attn.register_forward_pre_hook(mark))
    def analyze(z,v,index):
        li=state['layer'];case=state['case'];ref=z.softmax(-1);rv=(ref[:,None,:]@v.float()).squeeze(1)
        def record(name,p,clip=None,zero=None,one=None,valid=None):
            if valid is None:valid=torch.ones(32,device=z.device,dtype=torch.bool)
            tv=(p-ref).abs().sum(-1)/2;pv=(p[:,None,:]@v.float()).squeeze(1)
            err=(pv-rv)[valid];target=rv[valid]
            rows.append(dict(case=case,layer=li,name=name,valid_heads=int(valid.sum()),invalid_heads=int((~valid).sum()),
                tv_mean=tv[valid].mean().item() if valid.any() else None,tv_max=tv[valid].max().item() if valid.any() else None,
                output_relative_rms=(err.norm()/target.norm().clamp_min(1e-30)).item() if valid.any() else None,error_ss=err.square().sum().item(),ref_ss=target.square().sum().item(),
                argmax_changes=int(((p.argmax(-1)!=ref.argmax(-1))&valid).sum()),clip_fraction=clip.float().mean().item() if clip is not None else 0.,
                clipped_ref_mass=(ref*clip).sum(-1).mean().item() if clip is not None else 0.,
                zero_ref_mass=(ref*zero).sum(-1).mean().item() if zero is not None else 0.,endpoint_one_count=int(one.sum()) if one is not None else 0))
        candidates={}
        for name,q,clip in designs(z,calabs[li]):
            record(name,q.softmax(-1),clip);candidates[name]=(q,clip)
        # Rounded sigmoid LUT then exact stationary odds isolates threshold loss.
        lut={}
        for name in ('gap_u8_f4','i10_f4_gap_u8','i12_f6_gap_u10','fp32_i11_f4_gap_u8','bf16_i11_f4_gap_u8'):
            q,clip=candidates[name]
            for bits in (8,10,12,16):
                p,pi,zero,one,valid=thresholds(q,bits);label=f'{name}_p{bits}'
                record(label,pi,clip,zero,one,valid);lut[label]=p
        # Fixed train-only reference avoids online maximum; same score step,
        # but needs a sufficiently wide signed difference address (not the
        # 8-bit nonnegative max-gap table) and can have positive logits.
        q,clip=candidates['i10_f4'];c=torch.ceil((calmax[li]+2)*16)/16
        for bits in (8,12,16):
            p,pi,zero,one,valid=thresholds(q-c,bits);label=f'i10_f4_trainref_p{bits}'
            record(label,pi,clip,zero,one,valid);lut[label]=p
        # Baseline and candidates use the SAME Philox draws per case/layer/seed.
        ps={'ideal_fp32':(z-z.amax(-1,keepdim=True)).sigmoid()}
        for name in ('i8_f2','i10_f4','i11_f4'):
            q,_=candidates[name];ps[name]=(q-q.amax(-1,keepdim=True)).sigmoid()
        for name in ('i10_f4_gap_u8_p8','i10_f4_gap_u8_p12','i10_f4_gap_u8_p16','i10_f4_trainref_p16',
                     'fp32_i11_f4_gap_u8_p12','fp32_i11_f4_gap_u8_p16'):
            ps[name]=lut[name]
        for name,p in ps.items():
            # Candidate argmax init follows quantized scores, including ties.
            initial=z.argmax(-1) if name=='ideal_fp32' else candidates['i11_f4' if 'i11' in name else ('i8_f2' if name=='i8_f2' else 'i10_f4')][0].argmax(-1)
            for seed in (0,1,2):
                key=seed+1009*li+100003*state['start']
                hist,pv=finite(p,v,initial,key)
                samples.append(dict(case=case,layer=li,name=name,seed=seed,dead_heads=int((p.sum(-1)==0).sum()),tv_mean=((hist-ref).abs().sum(-1)/2).mean().item(),
                    output_relative_rms=((pv-rv).norm()/rv.norm().clamp_min(1e-30)).item(),error_ss=(pv-rv).square().sum().item(),ref_ss=rv.square().sum().item()))
        inputs.append(dict(case=case,layer=li,z_sha256=digest(z),v_sha256=digest(v),candidate_sha256=digest(index),score_min=z.min().item(),score_max=z.max().item()))
    def wrapped(q,k,v,*args,**kw):
        base=original(q,k,v,*args,**kw)
        if not state['capture']:return base
        assert not args and q.shape==(1,32,1,128) and kw.get('attn_mask') is None and not kw.get('is_causal',False)
        idx,zero=select(q.float().reshape(1,8,4,128),k[:,::4].float(),Config());assert not zero.any()
        index=idx[:,:,None,:].expand(1,8,4,128).reshape(1,32,128)
        gather=index[:,:,:,None].expand(1,32,128,128);ck,cv=k.gather(2,gather),v.gather(2,gather)
        z=((q.float()@ck.float().transpose(-1,-2))*kw['scale']).reshape(32,128)
        li=state['layer']
        if state['split']=='train':
            calabs[li]=torch.maximum(calabs[li],z.abs().amax(-1,keepdim=True));calmax[li]=torch.maximum(calmax[li],z.amax(-1,keepdim=True))
        else:analyze(z,cv[0],index)
        return base
    F.scaled_dot_product_attention=wrapped;t=time.time()
    try:
        with torch.inference_mode():
            for split,starts in [('train',[0,8192,16384,24576]),('test',list(range(0,32768,4096)))]:
                state['split']=split
                for start in starts:
                    state['start']=start;state['case']=f'{split}_2048_{start}';tokens=ids[split][start:start+2048].unsqueeze(0).cuda();pred=[]
                    for repeat in (0,1):
                        state['capture']=False;cache=model.model(tokens[:,:-1],use_cache=True).past_key_values
                        state['capture']=repeat==0
                        result=model.model(tokens[:,-1:],past_key_values=cache,use_cache=True)
                        pred.append(model.lm_head(result.last_hidden_state[:,-1]).detach().clone());del result,cache
                    assert torch.equal(pred[0],pred[1]),'diagnostic changed native trajectory'
                    baseline.append(dict(case=state['case'],equal=True,logits_sha256=digest(pred[0]),tokens_sha256=ids_sha256(tokens[0].cpu().tolist())))
                    print('DONE',state['case'],flush=True)
                if split=='train':
                    assert (calabs>0).all()
                    save(out/'CALIBRATION.json',dict(absmax=calabs.cpu().tolist(),max=calmax.cpu().tolist(),scope='4 train windows only; 36 layers x32 heads; not fitted to test'))
        assert len(inputs)==288 and len(baseline)==12
    finally:
        F.scaled_dot_product_attention=original
        for h in hooks:h.remove()
    save(out/'RESULTS.json',dict(rows=rows,samples=samples,inputs=inputs,native_baseline=baseline,seconds=time.time()-t,
        limits=['8 test queries x36 layers x32 heads=9216 head rows; fixed native trajectory and fixed FP32 SparQ128 candidates',
        'not full PPL, not recurrent error propagation, not quantized Q/K multiplication','FP32 PV isolates score/threshold error; sigmoid is offline mathematical LUT generation',
        'three finite S128/burn32 seeds are paired per case/layer; independent bits are ideal Philox, not physical RNG','fixed-reference uses train-only per-head max+2; generalization unproven']))
    from .quality import run_quality
    run_quality(model,ids['test'],out,save)
    save(out/'COMPLETE.json',dict(status='completed',files={p.name:dict(sha256=sha256(p),bytes=p.stat().st_size) for p in out.glob('*.json')}))
    print('COMPLETE',flush=True)
if __name__=='__main__':main()

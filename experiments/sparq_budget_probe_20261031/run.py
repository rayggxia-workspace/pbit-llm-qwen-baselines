"""Slurm-only bounded all-layer suffix-PPL probe; no training or PPA."""
import argparse,hashlib,importlib.metadata,json,math,os
from pathlib import Path
import sys,time
import torch

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def seal(p,v):
    p=Path(p)
    if p.exists():raise FileExistsError(p)
    p.parent.mkdir(parents=True,exist_ok=True)
    data=(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    p.write_bytes(data);p.with_suffix(p.suffix+'.sha256').write_text(hashlib.sha256(data).hexdigest()+'\n')
def read(p):
    p=Path(p)
    if not p.exists():return None
    assert sha(p)==p.with_suffix(p.suffix+'.sha256').read_text().strip()
    return json.loads(p.read_bytes())

def retained_probe(model,ids,score,core,Config,out):
    from transformers.integrations import sdpa_attention as sdpa
    old=sdpa.sdpa_attention_forward
    values={k:dict(mass=[],relative_error=[]) for k in (64,128,256)}
    def hook(module,q,k,v,*args,**kwargs):
        result=old(module,q,k,v,*args,**kwargs)
        if q.shape[2]==1 and k.shape[2]>=256:
            b,hq,_,d=q.shape;h=k.shape[1];g=hq//h;n=k.shape[2]
            Q=q.float().reshape(b,h,g,d);K=k.float();V=v.float()
            P=((Q/math.sqrt(d))@K.transpose(-1,-2)).softmax(-1)
            exact=P@V
            for budget in (64,128,256):
                selected,zero=core.select(Q,K,Config(k=budget,mode='exact'))
                assert not zero.any()
                kept=P.gather(-1,selected[:,:,None,:].expand(b,h,g,budget))
                mass=kept.sum(-1)
                vv=V.gather(2,selected[:,:,:,None].expand(b,h,budget,d))
                approx=(kept/mass[:,:,:,None])@vv
                rel=((approx-exact).square().sum(-1)/exact.square().sum(-1).clamp_min(1e-30)).sqrt()
                values[budget]['mass'].extend(mass.flatten().cpu().tolist())
                values[budget]['relative_error'].extend(rel.flatten().cpu().tolist())
        return result
    opt=dict(context=2048,decode=1,examples=8,batch=8,capture=True)
    reference=score(model,ids,None,**opt)
    sdpa.sdpa_attention_forward=hook
    try:observed=score(model,ids,None,**opt)
    finally:sdpa.sdpa_attention_forward=old
    assert reference['logits_sha256']==observed['logits_sha256']
    summary={}
    for budget,rows in values.items():
        mass=torch.tensor(rows['mass'],dtype=torch.float64);err=torch.tensor(rows['relative_error'],dtype=torch.float64)
        assert mass.numel()==8*36*32
        summary[str(budget)]=dict(head_rows=mass.numel(),mean_retained_mass=float(mass.mean()),p05_retained_mass=float(torch.quantile(mass,.05)),
            min_retained_mass=float(mass.min()),mean_head_relative_RMS=float(err.mean()),p95_head_relative_RMS=float(torch.quantile(err,.95)))
    seal(out/'RETENTION.json',dict(status='completed',diagnostic_does_not_change_logits=True,
        scope='8 native-BF16 trajectory queries, all36 layers/32 heads; not PPL or hardware memory traffic',by_k=summary,
        raw=values,token_ids_sha256=reference['token_ids_sha256']))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--phase',choices=['preflight','short'],required=True);ap.add_argument('--seed',type=int,default=0)
    a=ap.parse_args();root=Path(a.root).resolve(strict=True)
    assert root.parent==Path.home()/'projects' and root.stat().st_uid==os.getuid()
    assert os.environ.get('SLURM_JOB_ID') and torch.cuda.device_count()==1
    source=Path(__file__).resolve().parents[2];manifest=json.loads((source/'execution.json').read_bytes())
    for rel,digest in manifest['files_sha256'].items():assert sha(source/rel)==digest,rel
    cfg=json.loads((root/'runtime.json').read_bytes());dep=Path(cfg['dependency_source'])
    oldmanifest=json.loads((dep/'execution.json').read_bytes())
    assert oldmanifest['commit']=='a7108f8cba2c72ad319114af34557f4cec2b793d'
    for rel,digest in oldmanifest['files_sha256'].items():assert sha(dep/rel)==digest,rel
    sys.path.insert(0,str(dep))
    from experiments.sparq_ising_20261028 import core
    from experiments.sparq_ising_20261028.core import Config
    from experiments.sparq_ising_20261028.vendor import kernels
    from experiments.sparq_ising_20261028.scoring import score
    from experiments.sparq_ising_20261028.vendor.support import verify_files,check_config
    from experiments.sparq_ising_20261028.vendor.plans import ids_sha256
    from .core import Patch,selftest
    assert importlib.metadata.version('transformers')=='4.51.3'
    torch.set_num_threads(4);torch.manual_seed(0);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    prep_path=Path(cfg['prepared']);prep=json.loads(prep_path.read_bytes());verify_files(prep)
    assert prep['model']==cfg['model']
    for name,expected in cfg['data_sha256'].items():assert sha(Path(cfg['data_root'])/name)==expected
    from transformers import AutoTokenizer,AutoModelForCausalLM
    tokenizer=AutoTokenizer.from_pretrained(prep['local_path'],local_files_only=True,trust_remote_code=False)
    ids=tokenizer((Path(cfg['data_root'])/'wiki.test.raw').read_bytes().decode(),return_tensors='pt',add_special_tokens=False).input_ids[0]
    assert ids_sha256(ids.tolist())==prep['test_token_ids_sha256_le_int64']
    out=root/'results'/manifest['source_id']/a.phase/f'seed{a.seed}';out.mkdir(parents=True,exist_ok=True)
    provenance=dict(status='prepared',source=manifest,dependency_commit=oldmanifest['commit'],dependency_manifest_sha256=sha(dep/'execution.json'),
        prepared_sha256=sha(prep_path),model=cfg['model'],data_sha256=cfg['data_sha256'],token_sha256=ids_sha256(ids.tolist()),
        model_files=prep['files'],runtime_config_sha256=sha(root/'runtime.json'),environment={n:importlib.metadata.version(n) for n in ['torch','transformers','triton','tokenizers']},
        gpu=torch.cuda.get_device_name(),job=os.environ['SLURM_JOB_ID'],seed=a.seed,protocol='8 WT2 windows, 2048 prefill-context, 64 target suffix each, all36 layers; not full WT2',
        numeric='signed12/F4 scores -> saturating U8/F4 relative gap -> frozen P8 LUT -> dyadic R8-equivalent compare; independent Philox simulator, not GF hardware')
    if not (out/'provenance.json').exists():seal(out/'provenance.json',provenance)
    model=AutoModelForCausalLM.from_pretrained(prep['local_path'],local_files_only=True,trust_remote_code=False,torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval()
    check_config(model.config,cfg['model']);immutable=[(p,p._version,p.data_ptr()) for p in model.parameters()]
    table=torch.tensor(json.loads((Path(__file__).parent/'NUMERIC_TABLES.json').read_bytes())['sigmoid_lut'],device='cuda',dtype=torch.int64)
    def evaluate(name,case,kind='winner',**options):
        dest=out/(name+'.json');saved=read(dest)
        if saved is not None:return saved
        print('START',name,flush=True);torch.cuda.reset_peak_memory_stats()
        with Patch(core,kernels,table) as patch:
            patch.kind=kind
            result=score(model,ids,case,seed=a.seed,**options)
            result['p8_metrics']=patch.report()
        assert all(p._version==version and p.data_ptr()==ptr for p,version,ptr in immutable)
        result.update(status='completed',case=name,seed=a.seed,config=case.__dict__ if case else None,
            sampler_kind=kind,peak_memory_bytes=torch.cuda.max_memory_allocated(),provenance_sha256=sha(out/'provenance.json'))
        result['audit']['ideal_sigmoid_source']=False if case and case.mode!='exact' or kind=='mean' else None
        result['audit']['numeric_contract']='S12F4_U8F4_P8' if result['p8_metrics']['quantized_calls'] else 'exact digital reference'
        result['audit']['hardware_ppa']=None
        seal(dest,result);print('DONE',name,result['perplexity'],result['seconds'],flush=True);return result
    if a.phase=='preflight':
        gate=selftest('cuda',core,kernels,table)
        opt=dict(context=256,decode=4,examples=2,batch=2,capture=True)
        native=score(model,ids,None,native=True,**opt);dense=score(model,ids,None,**opt)
        assert native['logits_sha256']==dense['logits_sha256'] and native['nll_sum']==dense['nll_sum']
        for s in (8,32,128):evaluate('P8_S'+str(s),Config(samples=s),**opt)
        evaluate('P8_mean',Config(mode='exact'),kind='mean',**opt)
        evaluate('P8_iid',Config(mode='iid',samples=32),kind='iid_p8',**opt)
        evaluate('production_memory',Config(samples=32),context=2048,decode=2,examples=8,batch=8)
        seal(out/'GATE.json',dict(status='completed',passed=True,checks=gate,native_wrapper_bitwise=True))
    else:
        assert read(root/'results'/manifest['source_id']/'preflight/seed0/GATE.json')['passed']
        options=dict(context=2048,decode=64,examples=8,batch=8)
        evaluate('BF16',None,**options)
        if a.seed==0:
            for k in (64,128,256):evaluate('K'+str(k)+'_exact',Config(k=k,mode='exact'),**options)
            evaluate('K128_P8_mean',Config(mode='exact'),kind='mean',**options)
            if not (out/'RETENTION.json').exists():retained_probe(model,ids,score,core,Config,out)
        for s in (8,16,32,64,128):evaluate('K128_P8_WH_S'+str(s),Config(samples=s),**options)
        evaluate('K128_P8_IID_S32',Config(mode='iid',samples=32),kind='iid_p8',**options)
    seal(out/'complete.json',dict(status='completed',phase=a.phase,seed=a.seed,
        files={p.name:sha(p) for p in out.glob('*.json') if p.name!='complete.json'}))

if __name__=='__main__':main()

"""Slurm CPU Qwen forward PPL pilot; no PPL inferred from sampler error.

All 24 scored decode Attention layers are replaced; prefill and FFN stay original.
Uses the unchanged upstream scoring/controller and CTMC reference. Fixed suffix
targets are an exploratory pilot, NOT full WT2. No model/data are copied.
"""
import argparse,hashlib,json,os,sys,time,platform
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
sys.path.insert(0,str(REPO))
from sampler import sample_indices,SamplingLimitError


def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def write(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(obj,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')


def cases():
    specs=[('ctmc64',None,None,1.),('sync_k12',12.,0,1.),
           ('block64_k12',12.,64,1.),('block16_k12',12.,16,1.),
           ('lazy64_k12',12.,64,.125),('block16_k16',16.,16,1.)]
    return [dict(name=f'{name}_s{seed}',backend=name,seed=seed,kappa=k,block=b,enable=q)
            for name,k,b,q in specs for seed in (0,1,2)]


def identity(a):
    # This independent prior fingerprint is read-only, not regenerated from files.
    prior=Path('/home/Hongjie_Zeng/projects/pbit-qwen-joint-ffn-attention-20261019-issue50/outputs/d61b2861edc91e00495268d39a738edb3599f87f/identity.json')
    old=json.loads(prior.read_text())
    checked={}
    for key,item in old['files'].items():
        p=Path(item['path']).resolve(strict=True)
        try:p.relative_to(Path('/home/Hongjie_Zeng'))
        except ValueError:raise ValueError('input escapes personal root')
        if p.stat().st_size!=item['bytes'] or digest(p)!=item['sha256']:raise ValueError('input hash mismatch '+key)
        checked[key]=item
    if old['model_revision']!='060db6499f32faf8b98477b0a26969ef7d8b9987':raise ValueError('revision mismatch')
    cal=Path('/home/Hongjie_Zeng/projects/pbit-qwen-joint-ffn-attention-20261019-issue50/assets/moment.pt')
    if digest(cal)!='fefbb90c4f38c5f7a6d51a672550bd684ffe3a1415d36dc115a8ca5e05c5db0b':raise ValueError('calibration hash mismatch')
    return dict(model_revision=old['model_revision'],files=checked,prior_identity=str(prior),
        prior_identity_sha256=digest(prior),calibration=str(cal),calibration_sha256=digest(cal))


def load(a,ident):
    import torch,transformers
    from transformers import AutoModelForCausalLM,AutoTokenizer
    import transformers.models.qwen2.modeling_qwen2 as q
    from experiments.attention_e01.capture import TRANSFORMERS_VERSION,QWEN_SOURCE_SHA256,TEST_IDS_SHA256,TEST_IDS_TOKENS
    from experiments.qwen_joint_stratified_attention_20261019.upstream_attention.scoring import ids_sha256
    if transformers.__version__!=TRANSFORMERS_VERSION or digest(q.__file__)!=QWEN_SOURCE_SHA256:raise ValueError('pinned source mismatch')
    torch.set_num_threads(a.threads);torch.set_num_interop_threads(1)
    root=Path(ident['files']['model/config.json']['path']).parent
    tok=AutoTokenizer.from_pretrained(root,local_files_only=True,trust_remote_code=False)
    ids=tok(Path(ident['files']['data/wiki.test.raw']['path']).read_text(encoding='utf-8'),
        add_special_tokens=False,return_tensors='pt').input_ids[0]
    if len(ids)!=TEST_IDS_TOKENS or ids_sha256(ids.tolist())!=TEST_IDS_SHA256:raise ValueError('test token IDs mismatch')
    model=AutoModelForCausalLM.from_pretrained(root,local_files_only=True,trust_remote_code=False,
        torch_dtype=torch.bfloat16,attn_implementation='sdpa').eval()
    outer=torch.load(ident['calibration'],map_location='cpu',weights_only=True)
    cal=outer if 'parameter' in outer else outer['2048_0.3_max4']
    return model,ids,cal,dict(torch=torch.__version__,transformers=transformers.__version__,
        device='CPU BF16',platform=platform.platform(),threads=a.threads,
        Slurm_job_id=os.environ['SLURM_JOB_ID'],Slurm_array_task_id=os.environ.get('SLURM_ARRAY_TASK_ID'))


def case_args(a,mode,seed=0):
    return dict(mode=mode,samples=64,burn=16.,spacing=4.,seed=seed,context=2048,
        decode=a.decode,examples=a.examples,batch=a.batch,selection='fixed',
        budget_blocks=8,target_fraction=.30,protocol='suffix',stride=1024)


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','worker'])
    p.add_argument('--project',required=True);p.add_argument('--commit',required=True)
    p.add_argument('--index',type=int,default=0);p.add_argument('--threads',type=int,default=4)
    p.add_argument('--examples',type=int,default=8);p.add_argument('--decode',type=int,default=16)
    p.add_argument('--batch',type=int,default=8);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('model evaluation requires Slurm')
    if Path(a.project).resolve().parent!=Path('/home/Hongjie_Zeng/projects'):raise ValueError('personal project required')
    out=Path(a.project)/'outputs'/a.commit
    out.mkdir(parents=True,exist_ok=True)
    ident=identity(a)
    model,ids,cal,env=load(a,ident)
    from experiments.qwen_joint_stratified_attention_20261019.upstream_attention.evaluate import evaluate_case
    from experiments.qwen_joint_stratified_attention_20261019.upstream_attention.attention import JointAttentionController
    if a.action=='prepare':
        reference=evaluate_case(model,ids,case_args(a,'sdpa'),cal)
        reference.update(source_commit=a.commit,environment=env,input_provenance=ident)
        write(out/'bf16_reference.json',reference)
        # The same exact SDPA dispatch through the controller must agree.
        wrapped=evaluate_case(model,ids,case_args(a,'digital_sdpa'),cal)
        if abs(reference['nll_sum']-wrapped['nll_sum'])>1e-8:raise ValueError('SDPA wrapper mismatch')
        write(out/'wrapper_reference.json',wrapped)
        write(out/'suite.json',dict(cases=cases(),args=vars(a),identity=ident,environment=env))
        write(out/'READY.json',dict(source_commit=a.commit,bf16_sha256=digest(out/'bf16_reference.json'),
            suite_sha256=digest(out/'suite.json'),wrapper_equal=True))
        print('READY',reference['perplexity'],reference['scored_tokens'],flush=True)
        return
    ready=json.loads((out/'READY.json').read_text());suite=json.loads((out/'suite.json').read_text())
    if digest(out/'suite.json')!=ready['suite_sha256'] or digest(out/'bf16_reference.json')!=ready['bf16_sha256']:raise ValueError('gate changed')
    if suite['identity']!=ident:raise ValueError('input identity changed')
    for k in ['examples','decode','batch','threads']:
        if suite['args'][k]!=getattr(a,k):raise ValueError('scoring protocol differs '+k)
    c=cases()[a.index];destination=out/'ppl'/(c['name']+'.json')
    if destination.exists():raise FileExistsError(destination)
    all_stats=[];capture={};rngs={};observers={}
    original=JointAttentionController._sample_indices
    def replace(ctrl,logits,layer):
        if c['backend']=='ctmc64':
            if c['seed']==0 and layer not in capture:capture[layer]=logits.detach().float().cpu().numpy()
            return original(ctrl,logits,layer)
        import torch
        if layer not in rngs:
            rngs[layer]=np.random.default_rng(c['seed']*10000+layer+5100)
            observers[layer]=np.random.default_rng(c['seed']*10000+layer+95100)
        try:
            indices,st=sample_indices(logits.detach().float().cpu().numpy(),64,kappa=c['kappa'],
                block=c['block'],enable=c['enable'],rng=rngs[layer],observation_rng=observers[layer],
                burn=16,spacing=4,max_slots=256,observation='jitter')
        except SamplingLimitError as exc:
            exc.stats['layer']=layer;raise
        all_stats.append(dict(layer=layer,**st))
        return torch.as_tensor(indices,device=logits.device,dtype=torch.long),st
    JointAttentionController._sample_indices=replace
    before=time.time()
    try:
        result=evaluate_case(model,ids,case_args(a,'screen_ising',c['seed']),cal)
        result.update(status='completed',configuration=c)
    except SamplingLimitError as exc:
        result=dict(status='sampler_cap_failed',perplexity=None,configuration=c,failure_stats=exc.stats,
            elapsed_seconds=time.time()-before,reason='No IID fallback; no partial PPL reported')
    finally:JointAttentionController._sample_indices=original
    result.update(source_commit=a.commit,environment=env,input_provenance=ident,
        bf16_reference_sha256=ready['bf16_sha256'],network_call_stats=all_stats,
        scope='CPU BF16 full-model forward on fixed suffixes; original FFN; exact prefix; NOT full WT2')
    if capture:
        path=out/'ctmc_input_logits_private.npz'
        with path.open('xb') as f:np.savez_compressed(f,**{f'layer_{k}':v for k,v in capture.items()})
        result['private_logit_capture']=dict(path=str(path),sha256=digest(path),bytes=path.stat().st_size,
            scope='first sampled query batch per layer, real Qwen logits; do not upload corpus-derived arrays')
    write(destination,result)
    print(json.dumps({k:result.get(k) for k in ['status','configuration','perplexity','elapsed_seconds']}),flush=True)


if __name__=='__main__':main()

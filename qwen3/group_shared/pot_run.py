"""Clarified contract: static W8 PoT/64x64 and shared activation PoT/64.

All finite cases retain GU64, NL128 and accurate SDPA. Conditional nonlinear
mean and exact-SiLU W8-only cases are diagnostics, not proposed circuits.
"""
import argparse,gc,json,os,pathlib,sys
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from qwen3.baselines.support import check_config,check_data,sha256,verify_files,verify_source
from qwen3.stochastic.vendor.scoring import ids_sha256
from qwen3.fixed_scale.run import score,configure,sealed
from .pot_weight import PoTWeightFFN

VARIANTS=('lane','x_max','gu_max','all_max')

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--shard',type=int,required=True);a=p.parse_args()
    root=pathlib.Path(a.root);assert str(root)=='/home/Hongjie_Zeng/projects/pbit-qwen3-group64-scale-20261028-issue206'
    assert os.environ.get('SLURM_JOB_ID') and a.shard in range(4)
    here=pathlib.Path(__file__).parent;c=json.loads((here/'config.json').read_bytes());src=verify_source(here.parents[1])
    prep_path=pathlib.Path(c['prepared']);prep=json.loads(prep_path.read_bytes());verify_files(prep);assert prep['model']==c['model'];data=check_data(c)
    for k in ('fixed_xz_calibration','fixed_gu_calibration'):assert sha256(pathlib.Path(c[k]))==c[k+'_sha256']
    xz=json.loads(pathlib.Path(c['fixed_xz_calibration']).read_bytes())['tables'];gu=json.loads(pathlib.Path(c['fixed_gu_calibration']).read_bytes())['tables']
    torch.set_num_threads(4);torch.manual_seed(0);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    tok=AutoTokenizer.from_pretrained(prep['local_path'],local_files_only=True)
    ids=tok(pathlib.Path(data['wiki.test.raw']['path']).read_bytes().decode('utf-8'),return_tensors='pt',add_special_tokens=False).input_ids[0]
    assert ids_sha256(ids.tolist())==prep['test_token_ids_sha256_le_int64']
    variant=VARIANTS[a.shard];out=root/'results'/src['commit'][:12]/'pot_weight'/('shard'+str(a.shard));out.mkdir(parents=True,exist_ok=False)
    provenance=dict(source=src,config_sha256=sha256(here/'config.json'),effective_config=c,model=prep['model'],prepared_sha256=sha256(prep_path),data=data,
        slurm=os.environ['SLURM_JOB_ID'],shard=a.shard,command=sys.argv,torch=torch.__version__,gpu=torch.cuda.get_device_name(),variant=variant,
        weights='Wg/Wu/Wd offline signedW8[-127,127];one PoT LSB per64x64;ceilPow2(maxabs/127);RNE;Wd exact shift coefficients',
        activations='frozen four PoT choices;selected per64 contiguous channels on x/g/u as variant;g/u separate',
        controls='exact SiLU W8-only and conditional nonlinear mean are diagnostics,not finite hardware candidates',
        numerical_boundary='GU restoration remains FP32 numerical oracle;not fullchain bittrue',
        scoring='1024 suffix targets,not full WT2;teacher forcing,no chat template;accurateSDPA')
    sealed(out/'provenance.json',provenance)
    def load():
        m=AutoModelForCausalLM.from_pretrained(prep['local_path'],local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval();check_config(m.config,c['model']);return m
    def install(model,policy):
        for i,l in enumerate(model.model.layers):
            l.mlp=PoTWeightFFN(l.mlp,i,policy).eval()
            for s in ('g','u'):setattr(l.mlp,s+'_top',torch.tensor(gu[str(i)][s],device='cuda',dtype=torch.float32))
            l.mlp.freeze_down();l.mlp.weight_only=True
        gc.collect();torch.cuda.empty_cache()
    def save_score(model,name,**fields):
        print('START',name,flush=True);r=score(model,ids,c);r.update(case=name,provenance_sha256=sha256(out/'provenance.json'),**fields)
        if name!='bf16':r['diagnostics']={str(i):l.mlp.shared_report() for i,l in enumerate(model.model.layers)}
        sealed(out/(name+'.json'),r);print('COMPLETE',name,r['perplexity'],r['seconds'],flush=True);return r
    model=load();r=save_score(model,'bf16');assert r['perplexity']==13.566049199388152
    if a.shard==0:
        install(model,'legacy');save_score(model,'legacy_W8_only',weight_policy='legacy',control_only=True)
        del model;gc.collect();torch.cuda.empty_cache();model=load()
    install(model,'pot64');save_score(model,'pot_W8_only',weight_policy='pot64',control_only=True)
    immutable=[(getattr(l.mlp,n),getattr(l.mlp,n)._version,getattr(l.mlp,n).data_ptr()) for l in model.model.layers for n in ('gu_codes','gu_decoded','gu_tile_lsb','down_codes','down_tile_lsb','coeff','output_exp','g_top','u_top')]
    for mean in (False,True):
        for seed in (0,1,2):
            configure(model,'sampled',64,seed,xz,True,True)
            for l in model.model.layers:
                m=l.mlp;m.weight_only=False;m.nonlinear_mean=mean;m.set_spec(8,8,8);m.reset_short('lower_half','joint32',128,seed);m.reset_gu('fixed',64,seed);m.reset_shared(variant)
            name=('meanNL_' if mean else 'finiteNL_')+variant+'_s'+str(seed)
            save_score(model,name,weight_policy='pot64',variant=variant,seed=seed,GU_samples=64,NL_samples=None if mean else 128,control_only=mean)
            assert all(x._version==v and x.data_ptr()==ptr for x,v,ptr in immutable)
            assert all(l.mlp.calls==c['examples'] and l.mlp.gu_sample_calls==0 for l in model.model.layers)
    sealed(out/'complete.json',dict(status='completed',cases=9 if a.shard==0 else 8,shard=a.shard,
        documents={p.name:sha256(p) for p in sorted(out.glob('*.json')) if not p.name.endswith('.sha256.json')}))

if __name__=='__main__':main()

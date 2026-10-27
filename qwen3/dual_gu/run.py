"""Issue201 immutable GU-only quality scan; server jobs must use Slurm."""
import argparse,gc,json,os,pathlib,platform,sys,time
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from qwen3.baselines.support import check_config,check_data,sha256,verify_files,verify_source
from qwen3.stochastic.vendor.scoring import ids_sha256
from qwen3.fixed_scale.run import score,configure,sealed
from .core import DualGUFFN,GRIDS

HERE=pathlib.Path(__file__).parent


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--shard',type=int,required=True);p.add_argument('--pilot',action='store_true');a=p.parse_args()
    root=pathlib.Path(a.root);assert str(root)=='/home/Hongjie_Zeng/projects/pbit-qwen3-dual-gu-20261027-issue201'
    assert os.environ.get('SLURM_JOB_ID') and a.shard in range(4)
    c=json.loads((HERE/'config.json').read_bytes());src=verify_source(HERE.parents[1]);t=(32,64,128,256)[a.shard]
    prep_path=pathlib.Path(c['prepared']);prep=json.loads(prep_path.read_bytes());verify_files(prep);assert prep['model']==c['model'];data=check_data(c)
    for key in ('fixed_xz_calibration','fixed_gu_calibration'):assert sha256(pathlib.Path(c[key]))==c[key+'_sha256']
    xz=json.loads(pathlib.Path(c['fixed_xz_calibration']).read_bytes())['tables'];gu=json.loads(pathlib.Path(c['fixed_gu_calibration']).read_bytes())['tables']
    if a.pilot:c.update(context=256,decode=32,examples=1)
    torch.set_num_threads(4);torch.manual_seed(0);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    tok=AutoTokenizer.from_pretrained(prep['local_path'],local_files_only=True)
    ids=tok(pathlib.Path(data['wiki.test.raw']['path']).read_bytes().decode('utf-8'),return_tensors='pt',add_special_tokens=False).input_ids[0]
    assert ids_sha256(ids.tolist())==prep['test_token_ids_sha256_le_int64']
    out=root/'results'/src['commit'][:12]/('pilot' if a.pilot else 'main')/('shard'+str(a.shard));out.mkdir(parents=True,exist_ok=False)
    provenance=dict(source=src,config_sha256=sha256(HERE/'config.json'),effective_config=c,model=prep['model'],prepared_sha256=sha256(prep_path),data=data,
        fixed_xz_sha256=c['fixed_xz_calibration_sha256'],fixed_gu_sha256=c['fixed_gu_calibration_sha256'],slurm=os.environ['SLURM_JOB_ID'],shard=a.shard,
        torch=torch.__version__,gpu=torch.cuda.get_device_name(),command=sys.argv,
        unchanged='Wd fixedW8,lower_half g/u four bins, joint32 nonlinear128 samples, accurateSDPA; all36layers/full prefixes',
        numerical_boundary='GU finite integer comparators/AND-count law; scale restoration FP32 upstream oracle, no fullchain bittrue/PPA',
        weight_encoding='P8 threshold2*abs(W8),probabilityabs(W8)/128,separate sign; same original tileLSB*128, no weight requantization')
    sealed(out/'provenance.json',provenance)
    model=AutoModelForCausalLM.from_pretrained(prep['local_path'],local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval();check_config(model.config,c['model'])
    r=score(model,ids,c);r.update(case='bf16',provenance_sha256=sha256(out/'provenance.json'));sealed(out/'bf16.json',r);print('BF16',r['perplexity'],flush=True)
    for i,l in enumerate(model.model.layers):
        l.mlp=DualGUFFN(l.mlp,i).eval()
        for signal in ('g','u'):setattr(l.mlp,signal+'_top',torch.tensor(gu[str(i)][signal],device='cuda',dtype=torch.float32))
        l.mlp.freeze_down()
    gc.collect();torch.cuda.empty_cache()
    immutable=[(getattr(l.mlp,n),getattr(l.mlp,n)._version,getattr(l.mlp,n).data_ptr()) for l in model.model.layers for n in ('gu_codes','gu_decoded','down_codes','coeff','output_exp','g_top','u_top')]
    seeds=(0,) if a.pilot else (0,1,2)
    cases=[(law,seed) for law in ('fixed','iid','joint') for seed in seeds]
    for law,seed in cases:
        configure(model,'sampled',64,seed,xz,True,True)
        for l in model.model.layers:
            l.mlp.set_spec(8,8,8);l.mlp.reset_short('lower_half','joint32',128,seed);l.mlp.reset_gu(law,t,seed)
        name=f'{law}_T{t}_s{seed}';print('START',name,flush=True)
        r=score(model,ids,c)
        assert all(x._version==v and x.data_ptr()==ptr for x,v,ptr in immutable)
        assert all(l.mlp.calls==c['examples'] and l.mlp.gu_sample_calls==(0 if law=='fixed' else c['examples']) for l in model.model.layers)
        r.update(case=name,gu_law=law,gu_samples=t,seed=seed,provenance_sha256=sha256(out/'provenance.json'),
            input_strata=min(64,t) if law in ('fixed','iid') else GRIDS[t][0],weight_strata=None if law=='fixed' else 1 if law=='iid' else GRIDS[t][1],
            diagnostics={str(i):l.mlp.short_report() for i,l in enumerate(model.model.layers)})
        from .kernel import TABLE_METADATA
        r['binomial_cdf_metadata']=TABLE_METADATA
        sealed(out/(name+'.json'),r);print('COMPLETE',name,r['perplexity'],r['seconds'],flush=True)
    sealed(out/'complete.json',dict(status='completed',cases=len(cases)+1,shard=a.shard,documents={p.name:sha256(p) for p in sorted(out.glob('*.json')) if not p.name.endswith('.sha256.json')}))


if __name__=='__main__':main()

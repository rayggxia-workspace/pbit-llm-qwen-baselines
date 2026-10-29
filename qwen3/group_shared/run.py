"""Issue206 group64 shared-scale PPL scan, immutable Slurm execution."""
import argparse,gc,json,os,pathlib,sys
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from qwen3.baselines.support import check_config,check_data,sha256,verify_files,verify_source
from qwen3.stochastic.vendor.scoring import ids_sha256
from qwen3.fixed_scale.run import score,configure,sealed
from .core import Group64FFN,VARIANTS

HERE=pathlib.Path(__file__).parent
SHARDS={0:('fixed',tuple(VARIANTS)),1:('joint',('lane','x_max')),
        2:('joint',('gu_max','all_max')),3:('joint',('all_trim1','all_trim4'))}


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--shard',type=int,required=True);p.add_argument('--pilot',action='store_true');a=p.parse_args()
    root=pathlib.Path(a.root);assert str(root)=='/home/Hongjie_Zeng/projects/pbit-qwen3-group64-scale-20261028-issue206'
    assert os.environ.get('SLURM_JOB_ID') and a.shard in SHARDS
    c=json.loads((HERE/'config.json').read_bytes());src=verify_source(HERE.parents[1])
    prep_path=pathlib.Path(c['prepared']);prep=json.loads(prep_path.read_bytes());verify_files(prep);assert prep['model']==c['model'];data=check_data(c)
    for k in ('fixed_xz_calibration','fixed_gu_calibration'):assert sha256(pathlib.Path(c[k]))==c[k+'_sha256']
    xz=json.loads(pathlib.Path(c['fixed_xz_calibration']).read_bytes())['tables'];gu=json.loads(pathlib.Path(c['fixed_gu_calibration']).read_bytes())['tables']
    if a.pilot:c.update(context=256,decode=32,examples=1)
    torch.set_num_threads(4);torch.manual_seed(0);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    tok=AutoTokenizer.from_pretrained(prep['local_path'],local_files_only=True)
    ids=tok(pathlib.Path(data['wiki.test.raw']['path']).read_bytes().decode('utf-8'),return_tensors='pt',add_special_tokens=False).input_ids[0]
    assert ids_sha256(ids.tolist())==prep['test_token_ids_sha256_le_int64']
    out=root/'results'/src['commit'][:12]/('pilot' if a.pilot else 'main')/('shard'+str(a.shard));out.mkdir(parents=True,exist_ok=False)
    law,variants=SHARDS[a.shard]
    cases=[(law,v,s) for v in variants for s in (0,1,2)]
    if a.pilot:cases=[('fixed','lane',0),('fixed','all_max',0),('joint','lane',0),('joint','all_max',0)]
    provenance=dict(source=src,config_sha256=sha256(HERE/'config.json'),effective_config=c,
        model=prep['model'],prepared_sha256=sha256(prep_path),data=data,
        fixed_xz_sha256=c['fixed_xz_calibration_sha256'],fixed_gu_sha256=c['fixed_gu_calibration_sha256'],
        slurm=os.environ['SLURM_JOB_ID'],shard=a.shard,torch=torch.__version__,gpu=torch.cuda.get_device_name(),command=sys.argv,
        cases=[dict(GU=l,variant=v,seed=s) for l,v,s in cases],
        unchanged='W8,NLP8/real sigmoid,joint32NL128,direct fixedW8Wd,accurateSDPA,all36layers/fullprefixes',
        numerical_boundary='GU FP32 restoration oracle; integerP8/threshold/shift/output readout retained;not fullchain bittrue',
        selector='Per token contiguous64 channels; smallest TRAIN-frozen PoT scale with exceedance<=0/1/4; no new range or sorting')
    sealed(out/'provenance.json',provenance)
    model=AutoModelForCausalLM.from_pretrained(prep['local_path'],local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval();check_config(model.config,c['model'])
    r=score(model,ids,c);r.update(case='bf16',provenance_sha256=sha256(out/'provenance.json'));sealed(out/'bf16.json',r);print('BF16',r['perplexity'],flush=True)
    assert r['perplexity']==(27.312114874936853 if a.pilot else 13.566049199388152)
    for i,l in enumerate(model.model.layers):
        l.mlp=Group64FFN(l.mlp,i).eval()
        for s in ('g','u'):setattr(l.mlp,s+'_top',torch.tensor(gu[str(i)][s],device='cuda',dtype=torch.float32))
        for table in (l.mlp.g_top,l.mlp.u_top):
            assert bool((table>0).all()) and bool((torch.frexp(table)[0]==.5).all())
        l.mlp.freeze_down()
    gc.collect();torch.cuda.empty_cache()
    immutable=[(getattr(l.mlp,n),getattr(l.mlp,n)._version,getattr(l.mlp,n).data_ptr()) for l in model.model.layers for n in ('gu_codes','gu_decoded','down_codes','coeff','output_exp','g_top','u_top')]
    expected_fixed=[15.551864566282788,15.467966690474148,15.074231519987723]
    expected_joint=[15.865387583944637,16.093814459554842,15.72621827278319]
    for law,variant,seed in cases:
        configure(model,'sampled',64,seed,xz,True,True)
        for l in model.model.layers:
            m=l.mlp;m.set_spec(8,8,8);m.reset_short('lower_half','joint32',128,seed)
            m.reset_gu(law,64 if law=='fixed' else 256,seed);m.reset_shared(variant)
        name=f'{law}_{variant}_s{seed}';print('START',name,flush=True);r=score(model,ids,c)
        assert all(x._version==v and x.data_ptr()==ptr for x,v,ptr in immutable)
        assert all(l.mlp.calls==c['examples'] and l.mlp.gu_sample_calls==(0 if law=='fixed' else c['examples']) for l in model.model.layers)
        if variant=='lane' and (not a.pilot or law=='joint'):
            expected=46.739837101314336 if a.pilot else (expected_fixed if law=='fixed' else expected_joint)[seed]
            assert r['perplexity']==expected,('unchanged control mismatch',name,r['perplexity'],expected)
        r.update(case=name,GU=law,GU_samples=64 if law=='fixed' else 256,variant=variant,seed=seed,
            provenance_sha256=sha256(out/'provenance.json'),diagnostics={str(i):l.mlp.shared_report() for i,l in enumerate(model.model.layers)})
        sealed(out/(name+'.json'),r);print('COMPLETE',name,r['perplexity'],r['seconds'],flush=True)
    sealed(out/'complete.json',dict(status='completed',cases=len(cases)+1,shard=a.shard,
        documents={p.name:sha256(p) for p in sorted(out.glob('*.json')) if not p.name.endswith('.sha256.json')}))


if __name__=='__main__':main()

"""Frozen catalog size/group-size sweep,after CPU then GPU Slurm preflight."""
import argparse,gc,json,os,pathlib,sys
import torch
from qwen3.group_shared.recal_run import context,load
from qwen3.group_shared.group_sweep_core import GroupSweepFFN
from qwen3.fixed_scale.run import configure,score,sealed
from qwen3.baselines.support import sha256

OLD_SHA='9a26ddde7c2ed935e652cefbadd5bf63b9f5b4f23a269775f47d38f0963987f7'
SCHEMES=((64,4),(32,4),(16,4),(64,8),(32,8),(16,8))
OLD_PPL=(18.20000779048508,17.89494970067286,17.669679075660085)


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--phase',choices=('gate','eval'),required=True);p.add_argument('--shard',type=int,default=0);args=p.parse_args()
    root=pathlib.Path(args.root)
    assert str(root)=='/home/Hongjie_Zeng/projects/pbit-qwen3-group64-scale-20261028-issue206' and os.environ.get('SLURM_JOB_ID')
    torch.set_num_threads(4);torch.manual_seed(0);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    here,c,source,pp,prep,data,tok,test=context()
    out=root/'results'/source['commit'][:12]/'group_size_levels'/('gate' if args.phase=='gate' else 'shard'+str(args.shard))
    out.mkdir(parents=True,exist_ok=False)
    old=root/'results/e8888a26dace/recalibration/calibration/tables.json';assert sha256(old)==OLD_SHA
    done=json.loads((old.parent/'complete.json').read_bytes());assert done['status']=='completed' and done['documents']['tables.json']==OLD_SHA
    tables=json.loads(old.read_bytes())['tables']['risk4']
    prov=dict(source=source,config_sha256=sha256(here/'config.json'),model=c['model'],prepared_sha256=sha256(pp),data=data,
        slurm=os.environ['SLURM_JOB_ID'],command=sys.argv,phase=args.phase,torch=torch.__version__,gpu=torch.cuda.get_device_name(),
        old_calibration_sha256=OLD_SHA,schemes=SCHEMES,
        scope='x64/frozen4 unchanged;WgWuWd PoT W8 tiles64x64 unchanged;GU64/K64,NLjoint32T128;normalg signed8/P8;accurateSDPA',
        catalogs='smaller NL groups inherit parent64 risk4 catalog;B8 fills contiguous exponents[max-7,max],contains all old4;no ceiling increase/no refit/no TEST selection',
        numeric_boundary='GU FP32 restoration oracle,not fullchain bittrue;NL comparator codes and Wd counts integer;no newPPA/TLM/training')
    sealed(out/'provenance.json',prov)
    model=load(prep,c);r=score(model,test,c);assert r['perplexity']==13.566049199388152
    r.update(case='bf16',provenance_sha256=sha256(out/'provenance.json'));sealed(out/'bf16.json',r);print('BF16',r['perplexity'],flush=True)
    xz=json.loads(pathlib.Path(c['fixed_xz_calibration']).read_bytes())['tables']
    for i,layer in enumerate(model.model.layers):
        layer.mlp=GroupSweepFFN(layer.mlp,i).eval();e=tables[str(i)];layer.mlp.install_sweep(e['g'],e['u'],64,4)
    gc.collect();torch.cuda.empty_cache()
    def reset(seed,mean=False):
        configure(model,'sampled',64,seed,xz,True,True)
        for l in model.model.layers:
            m=l.mlp;m.set_spec(8,8,8);m.reset_short('lower_half','joint32',128,seed);m.reset_gu('fixed',64,seed);m.reset_gate('max');m.reset_sweep_stats();m.nonlinear_mean=mean
    def install(group,count):
        for i,l in enumerate(model.model.layers):
            e=tables[str(i)];l.mlp.install_sweep(e['g'],e['u'],group,count)
    seed=args.shard%3;reset(seed);r=score(model,test,c);assert r['perplexity']==OLD_PPL[seed],('oldrisk4 replay',r['perplexity'],OLD_PPL[seed])
    name='old_risk4_s'+str(seed);r.update(case=name,seed=seed,old_calibration_sha256=OLD_SHA,provenance_sha256=sha256(out/'provenance.json'))
    sealed(out/(name+'.json'),r);print('OLD_CONTROL',seed,r['perplexity'],r['seconds'],flush=True)
    if args.phase=='gate':
        install(16,8);reset(0)
        pilot={**c,'examples':2,'decode':4};r=score(model,test,pilot)
        assert r['scored_tokens']==8 and all(l.mlp.calls==2 for l in model.model.layers)
        assert all(l.mlp.shared_report()['stages']['g']['mixed_scale_groups']==0 for l in model.model.layers)
        r.update(case='pilot_g16_b8',protocol='8-target pilot ONLY;not main1024 suffix PPL',provenance_sha256=sha256(out/'provenance.json'))
        sealed(out/'pilot_g16_b8.json',r);print('GPU_GATE_PASS',r['perplexity'],flush=True)
    else:
        assert args.shard in range(len(SCHEMES));group,count=SCHEMES[args.shard];install(group,count)
        weights=[(getattr(l.mlp,n),getattr(l.mlp,n)._version,getattr(l.mlp,n).data_ptr()) for l in model.model.layers for n in ('gu_codes','gu_decoded','down_codes','down_decoded','g_levels','u_levels','coeff','output_exp','x_scales') if n!='x_scales']
        for mean,seeds in ((False,(0,1,2)),(True,(0,))):
            for seed in seeds:
                reset(seed,mean);case=('meanNL_' if mean else 'finiteNL_')+f'g{group}_b{count}_s{seed}';print('START',case,flush=True)
                r=score(model,test,c)
                assert all(t._version==v and t.data_ptr()==ptr for t,v,ptr in weights)
                assert all(l.mlp.calls==8 for l in model.model.layers)
                if group==64 and count==4 and not mean:assert r['perplexity']==OLD_PPL[seed]
                r.update(case=case,scheme=f'g{group}_b{count}',seed=seed,control_only=mean,GU_samples=64,NL_samples=None if mean else 128,
                    nonlinear_group_size=group,nonlinear_scale_count=count,input_group_size=64,old_calibration_sha256=OLD_SHA,
                    provenance_sha256=sha256(out/'provenance.json'),diagnostics={str(i):l.mlp.shared_report() for i,l in enumerate(model.model.layers)})
                sealed(out/(case+'.json'),r);print('COMPLETE',case,r['perplexity'],r['seconds'],flush=True)
    sealed(out/'complete.json',dict(status='completed',cases=3 if args.phase=='gate' else 6,shard=args.shard,
        documents={p.name:sha256(p) for p in sorted(out.glob('*.json')) if not p.name.endswith('.sha256.json')}))


if __name__=='__main__':main()

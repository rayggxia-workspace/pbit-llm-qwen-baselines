"""Slurm-only matched1024-target suffix test; not complete WT2 or PPA."""
import argparse
import gc
import json
import os
import pathlib
import sys
import torch
from .core import UnifiedGUFFN
from qwen3.group_shared.recal_run import context,load
from qwen3.group_shared.group_sweep_run import OLD_SHA,OLD_PPL
from qwen3.group_shared.full_wt2_run import reset
from qwen3.fixed_scale.run import score,sealed
from qwen3.baselines.support import sha256

ROOT = '/home/Hongjie_Zeng/projects/pbit-gu-unified-code-20261030-issue204'
DEP = '/home/Hongjie_Zeng/projects/pbit-qwen3-group64-scale-20261028-issue206'
DEP_COMMIT = '5d49ea97502d2c11bf0745d50689b4c558c384d1'
RUN_MODES = ('independent9','raw9','raw8')


def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=('gate','eval'),required=True)
    p.add_argument('--seed',type=int,choices=(0,1,2),default=0);args=p.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    source=pathlib.Path(__file__).resolve().parents[1]
    manifest=json.loads((source/'execution.json').read_bytes())
    for name,h in manifest['files_sha256'].items():assert sha256(source/name)==h,name
    root=pathlib.Path(ROOT);assert root in source.parents
    torch.set_num_threads(4);torch.manual_seed(0)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    here,c,dep,pp,prep,data,tok,test=context()
    lock=json.loads((source/'gu_unified_codec_20261030/dependency.json').read_bytes())
    assert dep['commit']==DEP_COMMIT and dep['files_sha256']==lock['files_sha256']
    assert c['model']['id']=='Qwen/Qwen3-4B'
    assert c['model']['revision']=='1cfa9a7208912126459214e8b04321603b3df60c'
    assert len(test)==299078 and c['examples']==8 and c['decode']==128
    cal=pathlib.Path(DEP)/'results/e8888a26dace/recalibration/calibration/tables.json'
    assert sha256(cal)==OLD_SHA
    done=json.loads((cal.parent/'complete.json').read_bytes())
    assert done['status']=='completed' and done['documents']['tables.json']==OLD_SHA
    tables=json.loads(cal.read_bytes())['tables']['risk4']
    xz=json.loads(pathlib.Path(c['fixed_xz_calibration']).read_bytes())['tables']
    out=root/'results'/manifest['source_commit'][:12]/('gate' if args.phase=='gate' else 'seed'+str(args.seed))
    out.mkdir(parents=True,exist_ok=False)
    prov=dict(source=manifest,dependency_source=dep,dependency_path=str(here.parents[1]),
        config=c,config_sha256=sha256(here/'config.json'),prepared_sha256=sha256(pp),
        model_manifest=prep,data=data,calibration_sha256=OLD_SHA,
        slurm=os.environ['SLURM_JOB_ID'],command=sys.argv,torch=torch.__version__,
        gpu=torch.cuda.get_device_name(),cuda=torch.version.cuda,seed=args.seed,phase=args.phase,
        scope='posttrainedQwen3-4B;1024-target suffix/context2048;all36 FFNs/allprefix;accurateSDPA',
        unchanged='x64/frozen4;PoTW8/64x64;GU64/K64;g/u separate frozen risk4/shared64;NLjoint32T128;directWd',
        changed='independent9 vs raw signed g9(step1/16)/u sign+mag8 vs raw signed g8(step1/8)/u sign+mag7;one g code drives both branches',
        RNG='same initial seeds and existing binomial sampler;probability-dependent consumption means no claim of draw-by-draw full-model pairing',
        boundary='GU FP32 restoration oracle,not fullchain bittrue;no training/refit/fullWT2/PPA/TLM/default change')
    sealed(out/'provenance.json',prov);psha=sha256(out/'provenance.json')
    model=load(prep,c)
    r=score(model,test,c);assert r['perplexity']==13.566049199388152
    assert r['scored_tokens']==1024 and len(r['all_layer_calls'])==36
    sealed(out/'bf16.json',dict(r,case='bf16',provenance_sha256=psha))
    print('BF16',r['perplexity'],r['seconds'],flush=True)
    for i,l in enumerate(model.model.layers):
        l.mlp=UnifiedGUFFN(l.mlp,i).eval();e=tables[str(i)]
        l.mlp.install_sweep(e['g'],e['u'],64,4)
    gc.collect();torch.cuda.empty_cache()
    tensors=[(getattr(l.mlp,n),getattr(l.mlp,n)._version,getattr(l.mlp,n).data_ptr())
             for l in model.model.layers
             for n in ('gu_codes','gu_decoded','down_codes','down_decoded','g_levels','u_levels','coeff','output_exp')]
    cases=[(mode,False) for mode in RUN_MODES]
    if args.phase=='eval' and args.seed==0:cases += [(mode,True) for mode in RUN_MODES]
    for mode,mean in cases:
        reset(model,args.seed,xz)
        for l in model.model.layers:l.mlp.set_codec(mode);l.mlp.nonlinear_mean=mean
        config=c if args.phase=='eval' or mode=='independent9' else dict(c,examples=2,decode=4)
        case=('mean_' if mean else 'finite_')+mode
        print('START',case,flush=True)
        torch.cuda.reset_peak_memory_stats();r=score(model,test,config)
        if mode=='independent9' and not mean:assert r['perplexity']==OLD_PPL[args.seed],(r['perplexity'],OLD_PPL[args.seed])
        assert all(t._version==v and t.data_ptr()==ptr for t,v,ptr in tensors)
        assert r['all_layer_calls']==[config['examples']]*36
        assert all(l.mlp.calls==config['examples'] for l in model.model.layers)
        r.update(case=case,seed=args.seed,conditional_NL_mean_only=mean,GU_samples=64,
            NL_samples=None if mean else 128,provenance_sha256=psha,
            storage_bits_per_g_or_u=8 if mode.endswith('8') else 9,
            sigmoid_from_stored_code=mode!='independent9',
            diagnostics={str(i):dict(codec=l.mlp.codec_report(),
                amplitude=l.mlp.shared_report()['stages']) for i,l in enumerate(model.model.layers)},
            peak_allocated_bytes=torch.cuda.max_memory_allocated())
        sealed(out/(case+'.json'),r);print('COMPLETE',case,r['perplexity'],r['seconds'],flush=True)
    sealed(out/'complete.json',dict(status='completed',phase=args.phase,seed=args.seed,
        documents={q.name:sha256(q) for q in sorted(out.glob('*.json')) if not q.name.endswith('.sha256.json')}))


if __name__=='__main__':main()

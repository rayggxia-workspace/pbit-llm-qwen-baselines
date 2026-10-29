"""Complete vectorized WT2 sliding-window evaluation, original G64/B4 catalog."""
import argparse,gc,json,math,os,pathlib,sys,time
import torch
from torch.nn import functional as F
from qwen3.group_shared.recal_run import context,load
from qwen3.group_shared.group_sweep_core import GroupSweepFFN
from qwen3.group_shared.group_sweep_run import OLD_SHA,OLD_PPL
from qwen3.group_shared.full_plan import full_window_plan,split_plan,verify_rows,window_seed
from qwen3.fixed_scale.run import configure,score,sealed
from qwen3.baselines.support import sha256
from qwen3.stochastic.vendor.scoring import ids_sha256,target_positions


def reset(model,seed,xz):
    configure(model,'sampled',64,seed,xz,True,True)
    for l in model.model.layers:
        m=l.mlp;m.set_spec(8,8,8);m.reset_short('lower_half','joint32',128,seed)
        m.reset_gu('fixed',64,seed);m.reset_gate('max');m.reset_sweep_stats();m.nonlinear_mean=False


def seed_window(model,seed,segment):
    key=window_seed(seed,segment)
    for i,l in enumerate(model.model.layers):
        m=l.mlp
        m.rng_input.manual_seed(700001+key*1000+i*7)
        m.rng_product.manual_seed(700002+key*1000+i*7)
        m.rng_and.manual_seed(810003+key*1000+i*13)
        m.rng_weight.manual_seed(910003+key*1009+i*13)


def score_plan(model,ids,plan,seed=None,chunk=256,log=False):
    """No cache: every prefix/window token runs the selected FFN; score each target once."""
    if not plan or chunk<1:raise ValueError('empty plan/bad chunk')
    layers=model.model.layers;nlayer=len(layers);calls=[0]*nlayer;tokens=[0]*nlayer;seen=[];handles=[]
    for i,l in enumerate(layers):
        def hook(module,args,i=i):
            seen.append(i);calls[i]+=1;tokens[i]+=args[0].shape[0]*args[0].shape[1]
        handles.append(l.mlp.register_forward_pre_hook(hook))
    start=time.monotonic();rows=[]
    try:
        with torch.inference_mode():
            for row in plan:
                seen.clear()
                if seed is not None:seed_window(model,seed,row['segment_id'])
                values=ids[row['begin']:row['end']].unsqueeze(0).to(next(model.parameters()).device)
                h=model.model(input_ids=values[:,:-1],use_cache=False).last_hidden_state
                first=row['first_target']-row['begin'];last=row['last_target_exclusive']-row['begin']
                losses=[]
                for p in range(first,last,chunk):
                    stop=min(p+chunk,last);logits=model.lm_head(h[:,p-1:stop-1]).float();target=values[:,p:stop]
                    loss=F.cross_entropy(logits.reshape(-1,logits.shape[-1]),target.reshape(-1),reduction='none')
                    losses.append(loss.double().sum().item());del logits,target,loss
                nll=math.fsum(losses)
                assert seen==list(range(nlayer)) and math.isfinite(nll)
                rows.append(dict(row,nll_sum=nll,**({} if seed is None else {'window_rng_key':window_seed(seed,row['segment_id'])})))
                del h,values
                if log and (len(rows)%4==0 or len(rows)==len(plan)):
                    print('WINDOWS',len(rows),'/',len(plan),'seconds',round(time.monotonic()-start,3),flush=True)
    finally:
        for h in handles:h.remove()
    assert calls==[len(plan)]*nlayer
    assert tokens==[sum(r['end']-r['begin']-1 for r in plan)]*nlayer
    return dict(status='completed',protocol='fullWT2-vectorized-v1;context2048/stride1024;no BOS/chat/cache;all36 FFNs/allprefix replaced in sampled case',
        **verify_rows(rows,plan),rows=rows,all_layer_calls=calls,all_layer_input_tokens=tokens,
        seconds=time.monotonic()-start,lm_head_chunk=chunk,RNG='per-seed+global-window SHA256 key;independent of shard allocation;no repeated identical per-window seed')


def main():
    a=argparse.ArgumentParser();a.add_argument('--root',required=True);a.add_argument('--phase',choices=('gate','eval'),required=True);a.add_argument('--task',type=int,default=0);args=a.parse_args()
    root=pathlib.Path(args.root);assert str(root)=='/home/Hongjie_Zeng/projects/pbit-qwen3-group64-scale-20261028-issue206' and os.environ.get('SLURM_JOB_ID')
    torch.set_num_threads(4);torch.manual_seed(0);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    here,c,source,pp,prep,data,tok,test=context();fc=here/'full_wt2_config.json';f=json.loads(fc.read_bytes())
    plan=full_window_plan(len(test),f['context'],f['stride']);assert len(test)==299078 and sum(r['scored_tokens'] for r in plan)==299077
    seed,part=divmod(args.task,f['shards_per_seed']);assert seed in f['seeds']
    selected=split_plan(plan,part,f['shards_per_seed']) if args.phase=='eval' else [plan[0],plan[-1]]
    out=root/'results'/source['commit'][:12]/'full_wt2'/('gate' if args.phase=='gate' else f'task{args.task:02d}')
    out.mkdir(parents=True,exist_ok=False)
    old=root/'results/e8888a26dace/recalibration/calibration/tables.json';assert sha256(old)==OLD_SHA
    done=json.loads((old.parent/'complete.json').read_bytes());assert done['status']=='completed' and done['documents']['tables.json']==OLD_SHA
    tables=json.loads(old.read_bytes())['tables']['risk4'];xz=json.loads(pathlib.Path(c['fixed_xz_calibration']).read_bytes())['tables']
    prov=dict(source=source,config_sha256=sha256(here/'config.json'),full_config_sha256=sha256(fc),model=c['model'],prepared_sha256=sha256(pp),data=data,
        slurm=os.environ['SLURM_JOB_ID'],command=sys.argv,torch=torch.__version__,gpu=torch.cuda.get_device_name(),cuda=torch.version.cuda,
        test_tokens=len(test),test_tokens_sha256=ids_sha256(test.tolist()),old_calibration_sha256=OLD_SHA,
        seed=seed,part=part,shards_per_seed=f['shards_per_seed'],plan=plan,
        full_target_positions_sha256=ids_sha256(range(1,len(test))),phase=args.phase,
        scope='posttrainedQwen3-4B;all36FFNs/allprefix;G64B4/x64/frozenTRAINrisk4;fixedPoTW8tiles64x64;GU64/K64;NLjoint32T128;originalg signed8/P8;accurateSDPA',
        numeric_boundary='GU FP32 restoration oracle,not fullchain bittrue;NL comparator codes and Wd counts integer;no newPPA/TLM/training')
    sealed(out/'provenance.json',prov);psha=sha256(out/'provenance.json');model=load(prep,c)
    if args.phase=='gate':
        r=score(model,test,c);assert r['perplexity']==13.566049199388152
        sealed(out/'suffix_bf16.json',dict(r,case='suffix_control_only',provenance_sha256=psha))
    r=score_plan(model,test,selected,log=True);sealed(out/'bf16.json',dict(r,case='bf16',provenance_sha256=psha));print('BF16',r['perplexity'],r['seconds'],flush=True)
    for i,l in enumerate(model.model.layers):
        l.mlp=GroupSweepFFN(l.mlp,i).eval();e=tables[str(i)];l.mlp.install_sweep(e['g'],e['u'],64,4)
    gc.collect();torch.cuda.empty_cache();reset(model,seed,xz)
    if args.phase=='gate':
        r=score(model,test,c);assert r['perplexity']==OLD_PPL[seed]
        sealed(out/'suffix_g64b4.json',dict(r,case='suffix_control_only',seed=seed,provenance_sha256=psha))
        reset(model,seed,xz)
    tensors=[(getattr(l.mlp,n),getattr(l.mlp,n)._version,getattr(l.mlp,n).data_ptr()) for l in model.model.layers for n in ('gu_codes','gu_decoded','down_codes','down_decoded','g_levels','u_levels','coeff','output_exp')]
    torch.cuda.reset_peak_memory_stats();r=score_plan(model,test,selected,seed=seed,log=True)
    assert all(t._version==v and t.data_ptr()==p for t,v,p in tensors)
    assert all(l.mlp.calls==len(selected) for l in model.model.layers)
    diag={str(i):dict(nl_stats=l.mlp.nl_stats.tolist(),nl_hist=l.mlp.nl_hist.tolist(),calls=l.mlp.calls,group=64,levels=4,accumulator_bits=l.mlp.catalog_accumulator_bound_bits) for i,l in enumerate(model.model.layers)}
    assert all(d['nl_stats'][j][8]==0 for d in diag.values() for j in (0,1))
    r.update(case='g64b4',seed=seed,diagnostics=diag,provenance_sha256=psha,peak_allocated_bytes=torch.cuda.max_memory_allocated())
    sealed(out/'g64b4.json',r);print('G64B4',seed,r['perplexity'],r['seconds'],flush=True)
    sealed(out/'complete.json',dict(status='completed',phase=args.phase,task=args.task,seed=seed,part=part,
        documents={p.name:sha256(p) for p in sorted(out.glob('*.json')) if not p.name.endswith('.sha256.json')}))


if __name__=='__main__':main()

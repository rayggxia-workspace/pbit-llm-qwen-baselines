"""Four-level refinement:larger TRAIN rows,within-group Gram and switch shifts."""
import argparse,gc,hashlib,json,os,pathlib,sys
import torch
from qwen3.fixed_scale.run import score,configure,sealed
from qwen3.stochastic.vendor.scoring import ids_sha256
from qwen3.stochastic.vendor.stratified_core import project_encoded
from .recal_run import context,load
from .core import encode_x
from .pot_weight import quantize_pot64,exact_pow2
from .independent_gate import original_g_field
from qwen3.nonlinear_width.core import make_lut
from .tune_core import TunedFFN,CANDIDATE_OFFSETS,ceil_exp,risk_components,fit_policies,encode_threshold,pack_carriers

SCHEMES={'large_diag4':('diag',False,1.),'large_gram4':('gram',False,1.),'large_gram4_threshold':('gram',True,1.),'large_gram4_threshold_bias':('gram',True,.5)}
OLD_SHA='9a26ddde7c2ed935e652cefbadd5bf63b9f5b4f23a269775f47d38f0963987f7'

def local_tune(g,u,norm,gram,fit_tokens):
    h=make_lut(8,8).to(g.device)[original_g_field(g)+128].long();gm=g.abs().amax(-1);um=u.abs().amax(-1)
    bg=ceil_exp(gm[:fit_tokens].amax(0));bu=ceil_exp(um[:fit_tokens].amax(0));offsets=CANDIDATE_OFFSETS.to(g.device)
    eg=bg[:,None]+offsets;eu=bu[:,None]+offsets
    reqg=torch.where(gm>0,ceil_exp(gm)-bg+8,-100);requ=torch.where(um>0,ceil_exp(um)-bu+8,-100)
    shape=(g.shape[0],g.shape[1],10,10);diag=torch.empty(shape,device=g.device,dtype=torch.float64);within=torch.empty_like(diag);variance=torch.empty_like(diag)
    for a in range(10):
        sg=exact_pow2(eg[:,a]).float()[None,:,None]
        for b in range(10):
            d,w,v=risk_components(g,u,h,sg,exact_pow2(eu[:,b]).float()[None,:,None],norm,gram)
            diag[:,:,a,b]=d;within[:,:,a,b]=w;variance[:,:,a,b]=v
    result={};t=torch.arange(g.shape[0],device=g.device)[:,None];j=torch.arange(g.shape[1],device=g.device)[None,:]
    def metrics(a,b,kind,weight):
        d=diag[t,j,a,b];w=within[t,j,a,b];v=variance[t,j,a,b];z=(d if kind=='diag' else w)+weight*v
        return dict(fit=float(z[:fit_tokens].sum()),validation=float(z[fit_tokens:].sum()),
            fit_gram_total=float((w+v)[:fit_tokens].sum()),validation_gram_total=float((w+v)[fit_tokens:].sum()),
            fit_diagonal_total=float((d+v)[:fit_tokens].sum()),validation_diagonal_total=float((d+v)[fit_tokens:].sum()))
    for name,(kind,tune,weight) in SCHEMES.items():
        cost=(diag if kind=='diag' else within)+weight*variance
        cg,cu,dg,du=fit_policies(cost,reqg,requ,fit_tokens,tune)
        lg=bg[:,None]+offsets[cg];lu=bu[:,None]+offsets[cu]
        def select(required,combos,delta):
            chosen=combos[:,-1][None,:].expand_as(required).clone()
            for k in (2,1,0):chosen=torch.where(required<=combos[:,k][None,:]+delta[None,:],combos[:,k][None,:],chosen)
            return chosen
        ig=select(reqg,cg,dg);iu=select(requ,cu,du)
        result[name]=dict(g=lg.cpu().tolist(),u=lu.cpu().tolist(),g_delta=dg.cpu().tolist(),u_delta=du.cpu().tolist(),active=False,
            objective=kind,variance_weight=weight,thresholds_tuned=tune,risk=metrics(ig,iu,kind,weight))
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--phase',choices=('calibrate','eval'),required=True);p.add_argument('--shard',type=int,default=0);args=p.parse_args()
    root=pathlib.Path(args.root);assert str(root)=='/home/Hongjie_Zeng/projects/pbit-qwen3-group64-scale-20261028-issue206' and os.environ.get('SLURM_JOB_ID')
    torch.set_num_threads(4);torch.manual_seed(0);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    here,c,src,pp,prep,data,tok,test=context();base=root/'results'/src['commit'][:12]/'tune4';out=base/('calibration' if args.phase=='calibrate' else 'shard'+str(args.shard));out.mkdir(parents=True,exist_ok=False)
    from qwen3.baselines.support import sha256
    old_path=root/'results/e8888a26dace/recalibration/calibration/tables.json';assert sha256(old_path)==OLD_SHA;old_tables=json.loads(old_path.read_bytes())['tables']['risk4']
    prov=dict(source=src,config_sha256=sha256(here/'config.json'),model=c['model'],prepared_sha256=sha256(pp),data=data,slurm=os.environ['SLURM_JOB_ID'],command=sys.argv,phase=args.phase,torch=torch.__version__,gpu=torch.cuda.get_device_name(),
        old_calibration_sha256=OLD_SHA,schemes=SCHEMES,calibration='teacherBF16 inputs -> actual PoTW8/sharedx/GU64;32 TRAIN windows2048,last1024 select32 rows/window;24 fit/8 validation windows;test never selects',
        objectives='diagonal vs within64 Gram squared bias+exact joint32NL128 variance;cross-group bias terms omitted;variance_weight0.5 is heuristic',
        thresholds='four scales only;three thresholds shifted by per-group static delta in{-1,0,1};no additional runtime multiplication',numerical_boundary='GU FP32 oracle;not fullchain bittrue;normalg signed8/P8 sigmoid;no newPPA/TLM')
    sealed(out/'provenance.json',prov);model=load(prep,c);r=score(model,test,c);assert r['perplexity']==13.566049199388152;r.update(case='bf16',provenance_sha256=sha256(out/'provenance.json'));sealed(out/'bf16.json',r);print('BF16',r['perplexity'],flush=True)
    xz=json.loads(pathlib.Path(c['fixed_xz_calibration']).read_bytes())['tables']
    if args.phase=='calibrate':
        train=tok(pathlib.Path(data['wiki.train.raw']['path']).read_bytes().decode(),return_tensors='pt',add_special_tokens=False).input_ids[0]
        length=2048;starts=[round((len(train)-length)*i/31) for i in range(32)];rows=torch.linspace(1024,2047,32).round().long().cuda();captures={i:[] for i in range(36)};norms={};grams={};lsbs={};cache={};hooks=[];rngs={i:torch.Generator(device='cuda').manual_seed(700001+917000+i*7) for i in range(36)}
        for i,l in enumerate(model.model.layers):
            _,decoded,_=quantize_pot64(torch.cat((l.mlp.gate_proj.weight.detach(),l.mlp.up_proj.weight.detach()),0));cache[i]=decoded
            _,wd,step=quantize_pot64(l.mlp.down_proj.weight.detach());blocks=wd.reshape(wd.shape[0],-1,64).permute(1,2,0).double();gram=torch.bmm(blocks,blocks.transpose(1,2));grams[i]=gram.cpu();norms[i]=gram.diagonal(dim1=-2,dim2=-1).cpu();lsbs[i]=ceil_exp(step).cpu();del wd,blocks,gram
            def observe(module,args,i=i):
                x=args[0].float();table=torch.tensor(xz[str(i)]['x'],device='cuda',dtype=torch.float32);enc=encode_x(x,table,True,0)
                gu=project_encoded(enc,cache[i],'sampled',64,rngs[i],64);g,u=gu[0].index_select(0,rows).chunk(2,-1);captures[i].append((g.cpu(),u.cpu()))
            hooks.append(l.mlp.register_forward_pre_hook(observe))
        with torch.inference_mode():
            for k,start in enumerate(starts):model.model(input_ids=train[start:start+length].unsqueeze(0).cuda(),use_cache=False);print('CAPTURE',k+1,flush=True)
        for hook in hooks:hook.remove()
        del model,cache;gc.collect();torch.cuda.empty_cache();tables={n:{} for n in SCHEMES};capture_sha={}
        for i in range(36):
            assert len(captures[i])==32;g=torch.cat([v[0] for v in captures[i]],0);u=torch.cat([v[1] for v in captures[i]],0)
            capture_sha[str(i)]={n:hashlib.sha256(v.contiguous().numpy().tobytes()).hexdigest() for n,v in (('g',g),('u',u))}
            g=g.cuda().reshape(1024,-1,64);u=u.cuda().reshape_as(g);entries=local_tune(g,u,norms[i].cuda(),grams[i].cuda(),768)
            for name,entry in entries.items():
                coeff,output_exp,carrier_g,carrier_u,limit=pack_carriers(exact_pow2(lsbs[i]).float(),torch.tensor(entry['g']),torch.tensor(entry['u']))
                bound=9728*128*127*int(coeff.max())*(1<<limit);assert bound<1<<63,('signed64 guard',i,name,bound.bit_length()+1)
                entry.update(accumulator_bound_bits=bound.bit_length()+1,coefficient_span=int(coeff.max()).bit_length()-1,carrier_limit=limit);tables[name][str(i)]=entry
            captures[i].clear();del g,u;print('FITTED_LAYER',i,flush=True)
        sealed(out/'tables.json',dict(status='completed',tables=tables,train_starts=starts,window_length=2048,selected_rows=rows.cpu().tolist(),fit_rows=768,validation_rows=256,train_token_sha256=ids_sha256(train.tolist()),capture_sha256=capture_sha,fit_seed=917,provenance_sha256=sha256(out/'provenance.json')))
        sealed(out/'complete.json',dict(status='completed',cases=1,documents={p.name:sha256(p) for p in sorted(out.glob('*.json')) if not p.name.endswith('.sha256.json')}));return
    assert args.shard in range(4);name=list(SCHEMES)[args.shard];cal=base/'calibration/tables.json';table=json.loads(cal.read_bytes());done=json.loads((cal.parent/'complete.json').read_bytes());assert done['documents']['tables.json']==sha256(cal)
    for i,l in enumerate(model.model.layers):
        l.mlp=TunedFFN(l.mlp,i).eval();entry=old_tables[str(i)];l.mlp.install_catalog(entry['g'],entry['u'],False)
    gc.collect();torch.cuda.empty_cache()
    def config(seed):
        configure(model,'sampled',64,seed,xz,True,True)
        for l in model.model.layers:
            m=l.mlp;m.set_spec(8,8,8);m.reset_short('lower_half','joint32',128,seed);m.reset_gu('fixed',64,seed);m.reset_gate('max')
    seed=args.shard%3;config(seed);r=score(model,test,c);assert r['perplexity']==[18.20000779048508,17.89494970067286,17.669679075660085][seed]
    r.update(case='old_risk4_s'+str(seed),seed=seed,old_calibration_sha256=OLD_SHA,provenance_sha256=sha256(out/'provenance.json'));sealed(out/(r['case']+'.json'),r)
    for i,l in enumerate(model.model.layers):
        a=table['tables'][name][str(i)];l.mlp.install_tuned(a['g'],a['u'],a['g_delta'],a['u_delta'])
    immutable=[(getattr(l.mlp,n),getattr(l.mlp,n)._version,getattr(l.mlp,n).data_ptr()) for l in model.model.layers for n in ('gu_codes','gu_decoded','down_codes','down_decoded','g_levels','u_levels','g_threshold_delta','u_threshold_delta','coeff','output_exp')]
    for mean in (False,True):
        for seed in (0,1,2):
            config(seed)
            for l in model.model.layers:l.mlp.nonlinear_mean=mean
            case=('meanNL_' if mean else 'finiteNL_')+name+'_s'+str(seed);print('START',case,flush=True);r=score(model,test,c)
            assert all(t._version==v and t.data_ptr()==ptr for t,v,ptr in immutable) and all(l.mlp.calls==8 for l in model.model.layers)
            r.update(case=case,scheme=name,seed=seed,control_only=mean,GU_samples=64,NL_samples=None if mean else 128,calibration_sha256=sha256(cal),provenance_sha256=sha256(out/'provenance.json'),diagnostics={str(i):l.mlp.shared_report() for i,l in enumerate(model.model.layers)})
            sealed(out/(case+'.json'),r);print('COMPLETE',case,r['perplexity'],r['seconds'],flush=True)
    sealed(out/'complete.json',dict(status='completed',cases=8,shard=args.shard,documents={p.name:sha256(p) for p in sorted(out.glob('*.json')) if not p.name.endswith('.sha256.json')}))

if __name__=='__main__':main()

"""TRAIN-only calibration then held-out suffix evaluation;Slurm immutable."""
import argparse,gc,hashlib,json,os,pathlib,sys
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from qwen3.baselines.support import check_config,check_data,sha256,verify_files,verify_source
from qwen3.stochastic.vendor.scoring import ids_sha256
from qwen3.fixed_scale.run import score,configure,sealed
from qwen3.stochastic.vendor.stratified_core import project_encoded
from .core import encode_x
from .pot_weight import quantize_pot64,exact_pow2
from .independent_gate import original_g_field
from qwen3.nonlinear_width.core import make_lut
from .recal_core import RecalibratedFFN,ceil_exp,output_risk,fit_catalogs,OFFSETS,encode_catalog

SCHEMES=('dense2','risk4','risk4_active')

def local_calibrate(g,u,norm,fit_tokens,active):
    # Arrays[T,groups,64] collected after actual PoT W GU64 with frozen sharedx.
    h=make_lut(8,8).to(g.device)[original_g_field(g)+128].long();mask=h>0 if active else torch.ones_like(h,dtype=torch.bool)
    gm=torch.where(mask,g.abs(),torch.zeros_like(g)).amax(-1);um=torch.where(mask,u.abs(),torch.zeros_like(u)).amax(-1)
    bg=ceil_exp(gm[:fit_tokens].amax(0));bu=ceil_exp(um[:fit_tokens].amax(0))
    bg=torch.where(gm[:fit_tokens].amax(0)>0,bg,ceil_exp(g[:fit_tokens].abs().amax((0,2))))
    bu=torch.where(um[:fit_tokens].amax(0)>0,bu,ceil_exp(u[:fit_tokens].abs().amax((0,2))))
    offsets=OFFSETS.to(g.device);eg=bg[:,None]+offsets;eu=bu[:,None]+offsets
    reqg=torch.where(gm>0,ceil_exp(gm)-bg+6,-100);requ=torch.where(um>0,ceil_exp(um)-bu+6,-100)
    cost=torch.empty(g.shape[0],g.shape[1],8,8,device=g.device,dtype=torch.float64)
    for a in range(8):
        sg=exact_pow2(eg[:,a]).float()[None,:,None]
        for b in range(8):cost[:,:,a,b]=output_risk(g,u,h,sg,exact_pow2(eu[:,b]).float()[None,:,None],norm)
    cg,cu=fit_catalogs(cost,reqg,requ,fit_tokens)
    levels_g=bg[:,None]+offsets[cg];levels_u=bu[:,None]+offsets[cu]
    denseg=bg[:,None]+torch.tensor([-3,-2,-1,0],device=g.device);denseu=bu[:,None]+torch.tensor([-3,-2,-1,0],device=g.device)
    def risk(lg,lu):
        gc,gs,ge,_,_=encode_catalog(g.flatten(1),lg,mask.flatten(1) if active else None)
        uc,us,ue,_,_=encode_catalog(u.flatten(1),lu,mask.flatten(1) if active else None)
        sg=exact_pow2(ge).float().reshape_as(g);su=exact_pow2(ue).float().reshape_as(u)
        v=output_risk(g,u,h,sg,su,norm)
        return dict(fit=float(v[:fit_tokens].sum().cpu()),validation=float(v[fit_tokens:].sum().cpu()))
    dense_risk=risk(denseg,denseu);fitted_risk=risk(levels_g,levels_u)
    assert fitted_risk['fit']<=dense_risk['fit']*(1+1e-10)+1e-15
    return dict(g=levels_g.cpu().tolist(),u=levels_u.cpu().tolist(),active=active,risk=fitted_risk),dict(g=denseg.cpu().tolist(),u=denseu.cpu().tolist(),active=active,risk=dense_risk)

def context():
    here=pathlib.Path(__file__).parent;c=json.loads((here/'config.json').read_bytes());src=verify_source(here.parents[1]);prep_path=pathlib.Path(c['prepared']);prep=json.loads(prep_path.read_bytes());verify_files(prep);assert prep['model']==c['model'];data=check_data(c)
    for k in ('fixed_xz_calibration','fixed_gu_calibration'):assert sha256(pathlib.Path(c[k]))==c[k+'_sha256']
    tok=AutoTokenizer.from_pretrained(prep['local_path'],local_files_only=True)
    test=tok(pathlib.Path(data['wiki.test.raw']['path']).read_bytes().decode(),return_tensors='pt',add_special_tokens=False).input_ids[0];assert ids_sha256(test.tolist())==prep['test_token_ids_sha256_le_int64']
    return here,c,src,prep_path,prep,data,tok,test

def load(prep,c):
    m=AutoModelForCausalLM.from_pretrained(prep['local_path'],local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval();check_config(m.config,c['model']);return m

def main():
    a=argparse.ArgumentParser();a.add_argument('--root',required=True);a.add_argument('--phase',choices=('calibrate','eval'),required=True);a.add_argument('--shard',type=int,default=0);args=a.parse_args()
    root=pathlib.Path(args.root);assert str(root)=='/home/Hongjie_Zeng/projects/pbit-qwen3-group64-scale-20261028-issue206' and os.environ.get('SLURM_JOB_ID')
    torch.set_num_threads(4);torch.manual_seed(0);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    here,c,src,pp,prep,data,tok,test=context();base=root/'results'/src['commit'][:12]/'recalibration';out=base/('calibration' if args.phase=='calibrate' else 'shard'+str(args.shard));out.mkdir(parents=True,exist_ok=False)
    prov=dict(source=src,config_sha256=sha256(here/'config.json'),model=c['model'],prepared_sha256=sha256(pp),data=data,slurm=os.environ['SLURM_JOB_ID'],command=sys.argv,phase=args.phase,torch=torch.__version__,gpu=torch.cuda.get_device_name(),
        numeric_boundary='GU FP32 restoration oracle;not fullchain bittrue;sigmoid originalg signed8/P8 LUT',
        calibration='teacher BF16 layer inputs -> actual PoT W8/sharedx/GU64;16 train windows512,16 rows/window;first12 fit,last4 validation;no test selection',
        objective='diagonal Wd column-norm weighted squared bias+exact joint32NL128 variance;ignores cross-channel/group bias covariance')
    sealed(out/'provenance.json',prov);model=load(prep,c);r=score(model,test,c);assert r['perplexity']==13.566049199388152;r.update(case='bf16',provenance_sha256=sha256(out/'provenance.json'));sealed(out/'bf16.json',r);print('BF16',r['perplexity'],flush=True)
    xz=json.loads(pathlib.Path(c['fixed_xz_calibration']).read_bytes())['tables'];oldgu=json.loads(pathlib.Path(c['fixed_gu_calibration']).read_bytes())['tables']
    if args.phase=='calibrate':
        train=tok(pathlib.Path(data['wiki.train.raw']['path']).read_bytes().decode(),return_tensors='pt',add_special_tokens=False).input_ids[0]
        length=512;starts=[round((len(train)-length)*i/15) for i in range(16)];rows=torch.linspace(0,511,16).round().long().cuda();captures={i:[] for i in range(36)};norms={};lsbs={};cache={};hooks=[];rngs={i:torch.Generator(device='cuda').manual_seed(700001+917000+i*7) for i in range(36)}
        for i,l in enumerate(model.model.layers):
            _,decoded,_=quantize_pot64(torch.cat((l.mlp.gate_proj.weight.detach(),l.mlp.up_proj.weight.detach()),0));cache[i]=decoded
            _,wd,lsb=quantize_pot64(l.mlp.down_proj.weight.detach());norms[i]=wd.double().square().sum(0).cpu().reshape(-1,64);lsbs[i]=ceil_exp(lsb).cpu();del wd
            def observe(module,args,i=i):
                x=args[0].float();tab=torch.tensor(xz[str(i)]['x'],device='cuda',dtype=torch.float32)
                enc=encode_x(x,tab,True,0);gu=project_encoded(enc,cache[i],'sampled',64,rngs[i],64)
                g,u=gu[0].index_select(0,rows).chunk(2,-1);captures[i].append((g.cpu(),u.cpu()))
            hooks.append(l.mlp.register_forward_pre_hook(observe))
        with torch.inference_mode():
            for k,start in enumerate(starts):model.model(input_ids=train[start:start+length].unsqueeze(0).cuda(),use_cache=False);print('CAPTURE',k+1,flush=True)
        for h in hooks:h.remove()
        del model,cache;gc.collect();torch.cuda.empty_cache()
        tables={s:{} for s in SCHEMES};capture_sha={};stats={}
        for i in range(36):
            assert len(captures[i])==16
            g=torch.cat([p[0] for p in captures[i]],0);u=torch.cat([p[1] for p in captures[i]],0)
            capture_sha[str(i)]={n:hashlib.sha256(v.contiguous().numpy().tobytes()).hexdigest() for n,v in (('g',g),('u',u))}
            g=g.cuda().reshape(256,-1,64);u=u.cuda().reshape_as(g);norm=norms[i].cuda()
            fitted,dense=local_calibrate(g,u,norm,192,False);active,_=local_calibrate(g,u,norm,192,True)
            for name,entry in (('dense2',dense),('risk4',fitted),('risk4_active',active)):
                e=lsbs[i]+torch.tensor(entry['g'])[:,-1][None,:]+torch.tensor(entry['u'])[:,-1][None,:]
                span=int((e.amax(-1)-e.amin(-1)).max());entry['Wd_coefficient_span']=span;assert span<=15,('coefficient guard',i,name,span)
                tables[name][str(i)]=entry
            stats[str(i)]={n:dict(risk=tables[n][str(i)]['risk'],Wd_span=tables[n][str(i)]['Wd_coefficient_span']) for n in SCHEMES}
            del g,u,norm;captures[i].clear();print('FITTED_LAYER',i,flush=True)
        sealed(out/'tables.json',dict(status='completed',tables=tables,train_starts=starts,train_window_length=512,selected_rows=rows.cpu().tolist(),fit_rows=192,validation_rows=64,train_token_sha256=ids_sha256(train.tolist()),capture_sha256=capture_sha,statistics=stats,fit_seed=917,provenance_sha256=sha256(out/'provenance.json')))
        sealed(out/'complete.json',dict(status='completed',cases=1,documents={p.name:sha256(p) for p in sorted(out.glob('*.json')) if not p.name.endswith('.sha256.json')}));return
    assert args.shard in range(3);cal=base/'calibration/tables.json';table=json.loads(cal.read_bytes());done=json.loads((cal.parent/'complete.json').read_bytes());assert done['status']=='completed' and done['documents']['tables.json']==sha256(cal)
    for i,l in enumerate(model.model.layers):
        l.mlp=RecalibratedFFN(l.mlp,i).eval()
        for s in ('g','u'):setattr(l.mlp,s+'_top',torch.tensor(oldgu[str(i)][s],device='cuda',dtype=torch.float32))
        l.mlp.freeze_down()
    gc.collect();torch.cuda.empty_cache()
    def config(seed):
        configure(model,'sampled',64,seed,xz,True,True)
        for l in model.model.layers:
            m=l.mlp;m.set_spec(8,8,8);m.reset_short('lower_half','joint32',128,seed);m.reset_gu('fixed',64,seed);m.reset_gate('max')
    expected=[73.30699083927549,58.943168399133974,62.01589453860189];config(args.shard)
    r=score(model,test,c);assert r['perplexity']==expected[args.shard];r.update(case='old_table_s'+str(args.shard),seed=args.shard,provenance_sha256=sha256(out/'provenance.json'));sealed(out/(r['case']+'.json'),r)
    scheme=SCHEMES[args.shard]
    for i,l in enumerate(model.model.layers):
        entry=table['tables'][scheme][str(i)];l.mlp.install_catalog(entry['g'],entry['u'],entry['active'])
    immutable=[(getattr(l.mlp,n),getattr(l.mlp,n)._version,getattr(l.mlp,n).data_ptr()) for l in model.model.layers for n in ('gu_codes','gu_decoded','down_codes','down_decoded','coeff','output_exp','g_top','u_top','g_levels','u_levels')]
    for mean in (False,True):
        for seed in (0,1,2):
            config(seed)
            for l in model.model.layers:l.mlp.nonlinear_mean=mean
            name=('meanNL_' if mean else 'finiteNL_')+scheme+'_s'+str(seed);print('START',name,flush=True);r=score(model,test,c)
            assert all(t._version==v and t.data_ptr()==ptr for t,v,ptr in immutable) and all(l.mlp.calls==8 for l in model.model.layers)
            r.update(case=name,scheme=scheme,seed=seed,control_only=mean,GU_samples=64,NL_samples=None if mean else 128,calibration_sha256=sha256(cal),provenance_sha256=sha256(out/'provenance.json'),diagnostics={str(i):l.mlp.shared_report() for i,l in enumerate(model.model.layers)})
            sealed(out/(name+'.json'),r);print('COMPLETE',name,r['perplexity'],r['seconds'],flush=True)
    sealed(out/'complete.json',dict(status='completed',cases=8,shard=args.shard,documents={p.name:sha256(p) for p in sorted(out.glob('*.json')) if not p.name.endswith('.sha256.json')}))

if __name__=='__main__':main()

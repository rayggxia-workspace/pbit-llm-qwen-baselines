"""Same128 samples, finer Cartesian NL strata; not an increased-sample run."""
import argparse,gc,json,math,os,pathlib,sys
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from qwen3.baselines.support import check_config,check_data,sha256,verify_files,verify_source
from qwen3.stochastic.vendor.scoring import ids_sha256
from qwen3.fixed_scale.run import score,configure,sealed
from qwen3.group_shared.core import Group64FFN,encode_nl
from qwen3.and_direct.multiscale_core import sigmoid_field,shifted_output
from qwen3.and_direct.core import finish_bf16

GRIDS=((8,2,8),(4,2,16),(16,2,4))

def components(codes,grid,samples=128):
    if len(grid)!=3 or any(d<1 or 256%d for d in grid) or samples%math.prod(grid):raise ValueError('invalid Cartesian grid/T')
    full=[q//(256//d) for q,d in zip(codes,grid)];frac=[(q%(256//d)).double()/(256//d) for q,d in zip(codes,grid)]
    repeats=samples//math.prod(grid);base=full[0]*full[1]*full[2]*repeats;terms=[]
    for mask in range(1,8):
        n=torch.full_like(codes[0],repeats);p=torch.ones_like(frac[0])
        for j in range(3):
            if mask&(1<<j):n=n*(full[j]<grid[j]).long();p=p*frac[j]
            else:n=n*full[j]
        terms.append((n,p))
    return base,terms

def counts_grid(codes,grid,samples,generator):
    z,terms=components(codes,grid,samples)
    for n,p in terms:z=z+torch.binomial(n.double(),p,generator=generator).long()
    return z,(codes[0]*codes[1]*codes[2]).double()/256**3

class GridGroupFFN(Group64FFN):
    def forward(self,x):
        self.calls+=1
        g,u=self._stage(x.float(),'x','gu',self.rng_input).chunk(2,-1)
        gc,gs,ge,gshift=encode_nl(g,self.g_top,self.offsets,self.shared_gu,self.allow)
        uc,us,ue,ushift=encode_nl(u,self.u_top,self.offsets,self.shared_gu,self.allow)
        for i,v,c,s,e,h in ((1,g,gc,gs,ge,gshift),(2,u,uc,us,ue,ushift)):
            scale=torch.ldexp(torch.ones_like(v),e);bins=torch.zeros_like(h)
            for k,off in enumerate(self.offsets):bins=torch.where(h==off,k,bins)
            self._record(i,v,scale,c.double()/256,torch.ldexp(c.float()*s/256,e),bins,self.shared_gu)
        hc=self.lut[sigmoid_field(gc,gs,ge)+128].long()
        counts,p=counts_grid((gc,hc,uc),self.grid,self.and_samples,self.rng_and)
        self.event_stats[0]+=p.numel();self.event_stats[1]+=p.sum();self.event_stats[2]+=(counts==0).sum()
        shift=gshift+ushift;limit=2*max(self.offsets)
        acc=shifted_output(counts,gs*us,shift,self.down_codes,self.coeff,self.and_samples,limit)
        return finish_bf16(acc,self.output_exp-limit,self.and_samples).to(x.dtype)

    def shared_report(self):
        r=super().shared_report();r.update(nonlinear_grid=self.grid,nonlinear_law='finite Cartesian grid refinement',
            draws_per_cell=self.and_samples//math.prod(self.grid))
        return r

def main():
    a=argparse.ArgumentParser();a.add_argument('--root',required=True);a.add_argument('--shard',type=int,required=True);args=a.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and args.shard in range(3)
    root=pathlib.Path(args.root);assert str(root)=='/home/Hongjie_Zeng/projects/pbit-qwen3-group64-scale-20261028-issue206'
    here=pathlib.Path(__file__).parent;c=json.loads((here/'config.json').read_bytes());src=verify_source(here.parents[1]);grid=GRIDS[args.shard]
    prep_path=pathlib.Path(c['prepared']);prep=json.loads(prep_path.read_bytes());verify_files(prep);assert prep['model']==c['model'];data=check_data(c)
    for k in ('fixed_xz_calibration','fixed_gu_calibration'):assert sha256(pathlib.Path(c[k]))==c[k+'_sha256']
    xz=json.loads(pathlib.Path(c['fixed_xz_calibration']).read_bytes())['tables'];gu=json.loads(pathlib.Path(c['fixed_gu_calibration']).read_bytes())['tables']
    torch.set_num_threads(4);torch.manual_seed(0);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    tok=AutoTokenizer.from_pretrained(prep['local_path'],local_files_only=True)
    ids=tok(pathlib.Path(data['wiki.test.raw']['path']).read_bytes().decode('utf-8'),return_tensors='pt',add_special_tokens=False).input_ids[0]
    assert ids_sha256(ids.tolist())==prep['test_token_ids_sha256_le_int64']
    out=root/'results'/src['commit'][:12]/'grid_refinement'/('shard'+str(args.shard));out.mkdir(parents=True,exist_ok=False)
    prov=dict(source=src,config_sha256=sha256(here/'config.json'),effective_config=c,model=prep['model'],prepared_sha256=sha256(prep_path),data=data,
        slurm=os.environ['SLURM_JOB_ID'],grid=grid,shard=args.shard,command=sys.argv,variants=['lane','gu_max','all_max'],
        purpose='same NL128, finer grid only;fixedWGU64 and frozen scales,Wd,SDPA unchanged')
    sealed(out/'provenance.json',prov)
    m=AutoModelForCausalLM.from_pretrained(prep['local_path'],local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval();check_config(m.config,c['model'])
    r=score(m,ids,c);assert r['perplexity']==13.566049199388152;r.update(case='bf16',provenance_sha256=sha256(out/'provenance.json'));sealed(out/'bf16.json',r)
    for i,l in enumerate(m.model.layers):
        l.mlp=GridGroupFFN(l.mlp,i).eval()
        for s in ('g','u'):setattr(l.mlp,s+'_top',torch.tensor(gu[str(i)][s],device='cuda',dtype=torch.float32))
        l.mlp.freeze_down()
    gc.collect();torch.cuda.empty_cache()
    immutable=[(getattr(l.mlp,n),getattr(l.mlp,n)._version,getattr(l.mlp,n).data_ptr()) for l in m.model.layers for n in ('gu_codes','down_codes','coeff','g_top','u_top')]
    for v in prov['variants']:
        for seed in (0,1,2):
            configure(m,'sampled',64,seed,xz,True,True)
            for l in m.model.layers:
                z=l.mlp;z.set_spec(8,8,8);z.reset_short('lower_half','joint32',128,seed);z.reset_gu('fixed',64,seed);z.reset_shared(v);z.grid=grid
            name=f'grid{grid[0]}x{grid[1]}x{grid[2]}_{v}_s{seed}';print('START',name,flush=True);r=score(m,ids,c)
            assert all(x._version==ver and x.data_ptr()==ptr for x,ver,ptr in immutable) and all(l.mlp.calls==8 for l in m.model.layers)
            r.update(case=name,variant=v,seed=seed,grid=grid,NL_samples=128,GU_samples=64,
                provenance_sha256=sha256(out/'provenance.json'),diagnostics={str(i):l.mlp.shared_report() for i,l in enumerate(m.model.layers)})
            sealed(out/(name+'.json'),r);print('COMPLETE',name,r['perplexity'],r['seconds'],flush=True)
    sealed(out/'complete.json',dict(status='completed',cases=10,shard=args.shard,
        documents={p.name:sha256(p) for p in sorted(out.glob('*.json')) if not p.name.endswith('.sha256.json')}))

if __name__=='__main__':main()

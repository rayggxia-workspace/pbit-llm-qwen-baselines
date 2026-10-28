"""Issue206: shared/clipped g/u amplitude;sigmoid always sees original g."""
import argparse,gc,json,os,pathlib,sys
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from qwen3.baselines.support import check_config,check_data,sha256,verify_files,verify_source
from qwen3.stochastic.vendor.scoring import ids_sha256
from qwen3.fixed_scale.run import score,configure,sealed
from .independent_gate import IndependentGateFFN

SHARDS={0:('max','g_trim1'),1:('u_trim1','both_trim1'),2:('both_trim4',)}

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--shard',type=int,required=True);a=p.parse_args()
    root=pathlib.Path(a.root);assert str(root)=='/home/Hongjie_Zeng/projects/pbit-qwen3-group64-scale-20261028-issue206'
    assert os.environ.get('SLURM_JOB_ID') and a.shard in SHARDS
    here=pathlib.Path(__file__).parent;c=json.loads((here/'config.json').read_bytes());src=verify_source(here.parents[1])
    prep_path=pathlib.Path(c['prepared']);prep=json.loads(prep_path.read_bytes());verify_files(prep);assert prep['model']==c['model'];data=check_data(c)
    for k in ('fixed_xz_calibration','fixed_gu_calibration'):assert sha256(pathlib.Path(c[k]))==c[k+'_sha256']
    xz=json.loads(pathlib.Path(c['fixed_xz_calibration']).read_bytes())['tables'];gu=json.loads(pathlib.Path(c['fixed_gu_calibration']).read_bytes())['tables']
    torch.set_num_threads(4);torch.manual_seed(0);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    tok=AutoTokenizer.from_pretrained(prep['local_path'],local_files_only=True)
    ids=tok(pathlib.Path(data['wiki.test.raw']['path']).read_bytes().decode('utf-8'),return_tensors='pt',add_special_tokens=False).input_ids[0]
    assert ids_sha256(ids.tolist())==prep['test_token_ids_sha256_le_int64']
    out=root/'results'/src['commit'][:12]/'independent_gate'/('shard'+str(a.shard));out.mkdir(parents=True,exist_ok=False)
    prov=dict(source=src,config_sha256=sha256(here/'config.json'),effective_config=c,model=prep['model'],prepared_sha256=sha256(prep_path),data=data,
        slurm=os.environ['SLURM_JOB_ID'],shard=a.shard,command=sys.argv,torch=torch.__version__,gpu=torch.cuda.get_device_name(),policies=SHARDS[a.shard],
        sigmoid='original g before amplitude clip,RNE signed8 step1/8,existing P8 LUT;no FP32 sigmoid',
        unchanged='x groupmax,Wg/Wu/Wd static PoT64x64,GU64,NLjoint32T128,accurateSDPA',
        controls='conditional NL mean diagnostic only;not hardware or wholeLLM expectation',
        numerical_boundary='GU restoration remains upstream FP32 numerical oracle;not fullchain bittrue',
        scope='existing frozen four-scale tables;no optimized new table,training,RTL,PPA or TLM change')
    sealed(out/'provenance.json',prov)
    model=AutoModelForCausalLM.from_pretrained(prep['local_path'],local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval();check_config(model.config,c['model'])
    def save_score(name,**fields):
        print('START',name,flush=True);r=score(model,ids,c);r.update(case=name,provenance_sha256=sha256(out/'provenance.json'),**fields)
        if name!='bf16':r['diagnostics']={str(i):l.mlp.shared_report() for i,l in enumerate(model.model.layers)}
        sealed(out/(name+'.json'),r);print('COMPLETE',name,r['perplexity'],r['seconds'],flush=True);return r
    r=save_score('bf16');assert r['perplexity']==13.566049199388152
    for i,l in enumerate(model.model.layers):
        l.mlp=IndependentGateFFN(l.mlp,i).eval()
        for s in ('g','u'):setattr(l.mlp,s+'_top',torch.tensor(gu[str(i)][s],device='cuda',dtype=torch.float32))
        l.mlp.freeze_down()
    gc.collect();torch.cuda.empty_cache()
    immutable=[(getattr(l.mlp,n),getattr(l.mlp,n)._version,getattr(l.mlp,n).data_ptr()) for l in model.model.layers for n in ('gu_codes','gu_decoded','gu_tile_lsb','down_codes','down_tile_lsb','coeff','output_exp','g_top','u_top')]
    def configure_case(policy,mean,seed,gate='original_g'):
        configure(model,'sampled',64,seed,xz,True,True)
        for l in model.model.layers:
            m=l.mlp;m.nonlinear_mean=mean;m.set_spec(8,8,8);m.reset_short('lower_half','joint32',128,seed);m.reset_gu('fixed',64,seed);m.reset_gate(policy,gate)
    if a.shard==0:
        expected=[69.67140048601013,63.845430401311084,70.10287010403827]
        for seed in (0,1,2):
            configure_case('max',False,seed,'old_coupled');r=save_score('old_coupled_s'+str(seed),amplitude_policy='max',seed=seed,gate_mode='old_coupled',NL_samples=128,GU_samples=64,control_only=False)
            assert r['perplexity']==expected[seed]
    for policy in SHARDS[a.shard]:
        for mean in (False,True):
            for seed in (0,1,2):
                configure_case(policy,mean,seed)
                save_score(('meanNL_' if mean else 'finiteNL_')+policy+'_s'+str(seed),amplitude_policy=policy,seed=seed,gate_mode='original_g',GU_samples=64,NL_samples=None if mean else 128,control_only=mean)
                assert all(x._version==v and x.data_ptr()==ptr for x,v,ptr in immutable)
                assert all(l.mlp.calls==c['examples'] and l.mlp.gu_sample_calls==0 for l in model.model.layers)
    sealed(out/'complete.json',dict(status='completed',cases=1+6*len(SHARDS[a.shard])+(3 if a.shard==0 else 0),shard=a.shard,
        documents={p.name:sha256(p) for p in sorted(out.glob('*.json')) if not p.name.endswith('.sha256.json')}))

if __name__=='__main__':main()

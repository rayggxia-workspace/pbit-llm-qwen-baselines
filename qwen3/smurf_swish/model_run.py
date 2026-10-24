"""Qwen3-4B actual fixed-g FSM histories, immutable Slurm-only experiment."""
import argparse,gc,json,os,platform,sys
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from qwen3.baselines.support import check_config,check_data,sha256,verify_files,verify_source
from qwen3.stochastic.vendor.scoring import ids_sha256
from qwen3.fixed_scale.run import score,configure,sealed
from .model_tables import CASES,build
from .model_core import FSMFFN
HERE=Path(__file__).resolve().parent

def planned():
    return [(mode,T,s) for mode,T in [('lut_mean',64),('fsm_mean',64),('fsm_mean',128),('fsm',64),('fsm',128)] for s in range(3)]

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--shard',type=int,required=True)
    a=p.parse_args();root=Path(a.root);shard=a.shard
    assert str(root)=='/home/Hongjie_Zeng/projects/pbit-qwen3-smurf-model-20261024-issue175'
    assert os.environ.get('SLURM_JOB_ID') and 0<=shard<len(CASES)
    cpath=HERE/'model_config.json';c=json.loads(cpath.read_bytes());src=verify_source(HERE.parents[1])
    G,N,Sneg=CASES[shard];tables={T:build(G,N,Sneg,T) for T in (64,128)}
    prep_path=Path(c['prepared']);prep=json.loads(prep_path.read_bytes());assert prep['model']==c['model']
    verify_files(prep);data=check_data(c)
    xp=Path(c['fixed_xz_calibration']);up=Path(c['fixed_gu_calibration'])
    assert sha256(xp)==c['fixed_xz_calibration_sha256'] and sha256(up)==c['fixed_gu_calibration_sha256']
    xt=json.loads(xp.read_bytes())['tables'];ut=json.loads(up.read_bytes())['tables']
    torch.set_num_threads(4);torch.manual_seed(0)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    tok=AutoTokenizer.from_pretrained(prep['local_path'],local_files_only=True)
    ids=tok(Path(data['wiki.test.raw']['path']).read_bytes().decode('utf-8'),return_tensors='pt',add_special_tokens=False).input_ids[0]
    assert ids_sha256(ids.tolist())==prep['test_token_ids_sha256_le_int64']
    out=root/'results'/('shard%d'%shard)
    prov=dict(source=src,config_sha256=sha256(cpath),data=data,model=c['model'],prepared_sha256=sha256(prep_path),
        test_token_ids_sha256=ids_sha256(ids.tolist()),fixed_xz_calibration_sha256=sha256(xp),
        fixed_gu_calibration_sha256=sha256(up),command=[sys.executable,*sys.argv],shard=shard,tables=tables,
        environment=dict(torch=torch.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(),
                         host=platform.node(),slurm=os.environ['SLURM_JOB_ID']),
        contract=dict(G=G,states=N,Sneg=Sneg,front_T_K=64,front_fixed_bins=4,weight_bits=8,
            g_quantization='fixed G/256 magnitude step plus sign, RNE, clamp0..255; no online range/bin',
            fsm='literal each-clock update then P8 coefficient comparator then independent u comparator AND',
            u_fixed_offsets=[1,3,5,7],reset_state=0,burnin=0,random_interface='independent R8 per lane/domain/clock',
            g_scale_inside_function=True,z_reencoding=False,gate_up_restore_bittrue=False,
            mean_controls='diagnostic only; not deployable zero-cycle functions'))
    sealed(out/'provenance.json',prov)
    model=AutoModelForCausalLM.from_pretrained(prep['local_path'],local_files_only=True,
        torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval();check_config(model.config,c['model'])
    r=score(model,ids,c);r.update(case='bf16',shard=shard,provenance_sha256=sha256(out/'provenance.json'))
    sealed(out/'bf16.json',r);print('BF16',shard,r['perplexity'],flush=True)
    for i,l in enumerate(model.model.layers):
        l.mlp=FSMFFN(l.mlp,i).eval();l.mlp.setup(G,Sneg,ut[str(i)]['u'],tables)
    gc.collect();torch.cuda.empty_cache()
    immutable=[(t,t._version,t.data_ptr()) for t in model.parameters()]
    immutable += [(getattr(l.mlp,n),getattr(l.mlp,n)._version,getattr(l.mlp,n).data_ptr()) for l in model.model.layers
                  for n in ('gu_codes','gu_decoded','down_codes','coeff','output_exp','g_top','u_top')]
    for mode,T,seed in planned():
        name='%s_T%d_s%d'%(mode,T,seed);configure(model,'sampled',64,seed,xt,True,True)
        for l in model.model.layers:l.mlp.reset_fsm(mode,T,seed)
        print('START',shard,name,flush=True)
        r=score(model,ids,c)
        assert all(t._version==v and t.data_ptr()==ptr for t,v,ptr in immutable)
        assert all(l.mlp.calls==c['examples'] for l in model.model.layers)
        r.update(case=name,shard=shard,seed=seed,mode=mode,T=T,G=G,states=N,Sneg=Sneg,
                 provenance_sha256=sha256(out/'provenance.json'),
                 diagnostics={str(i):l.mlp.report() for i,l in enumerate(model.model.layers)})
        sealed(out/(name+'.json'),r);print('COMPLETE',shard,name,r['perplexity'],r['seconds'],flush=True)
    sealed(out/'complete.json',dict(status='completed',cases=1+len(planned()),shard=shard,
        documents={p.name:sha256(p) for p in sorted(out.glob('*.json')) if not p.name.endswith('.sha256.json')}))

if __name__=='__main__':main()

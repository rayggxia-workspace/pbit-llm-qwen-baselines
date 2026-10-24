"""Three fixed-four-scale policies, joint stratification, T<=128."""
import argparse,json,os,platform,sys,gc
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from qwen3.baselines.support import check_config,check_data,sha256,verify_files,verify_source
from qwen3.stochastic.vendor.scoring import ids_sha256
from qwen3.fixed_scale.run import score,configure,sealed
from .short_core import ShortStreamFFN, POLICIES, GRID

HERE=Path(__file__).resolve().parent
def planned(shard):
    policy=('original','lower_half','lower_floor')[shard]
    rows=[('%s_mean_s%d'%(policy,s),'mean',policy,64,s) for s in range(3)]
    rows += [('%s_iid64_s%d'%(policy,s),'iid',policy,64,s) for s in range(3)]
    rows += [('%s_joint32_T%d_s%d'%(policy,t,s),'joint32',policy,t,s)
             for t in (32,64,128) for s in range(3)]
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--shard',type=int,required=True)
    a=p.parse_args();root=Path(a.root);shard=a.shard
    assert str(root)=='/home/Hongjie_Zeng/projects/pbit-qwen3-and-short-20261024-issue173'
    assert os.environ.get('SLURM_JOB_ID') and 0<=shard<=2
    c=json.loads((HERE/'config.json').read_bytes());src=verify_source(HERE.parents[1])
    prep_path=Path(c['prepared']);prep=json.loads(prep_path.read_bytes());assert prep['model']==c['model']
    verify_files(prep);data=check_data(c)
    xzpath=Path(c['fixed_xz_calibration']);gupath=Path(c['fixed_gu_calibration'])
    assert sha256(xzpath)==c['fixed_xz_calibration_sha256']
    assert sha256(gupath)==c['fixed_gu_calibration_sha256']
    xztables=json.loads(xzpath.read_bytes())['tables'];gutables=json.loads(gupath.read_bytes())['tables']
    torch.set_num_threads(4);torch.manual_seed(0)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    tok=AutoTokenizer.from_pretrained(prep['local_path'],local_files_only=True)
    ids=tok(Path(data['wiki.test.raw']['path']).read_bytes().decode('utf-8'),return_tensors='pt',add_special_tokens=False).input_ids[0]
    assert ids_sha256(ids.tolist())==prep['test_token_ids_sha256_le_int64']
    out=root/'results'/('shard%d'%shard)
    provenance=dict(source=src,config_sha256=sha256(HERE/'config.json'),data=data,model=c['model'],
        prepared_sha256=sha256(prep_path),test_token_ids_sha256=ids_sha256(ids.tolist()),
        fixed_gu_calibration_sha256=sha256(gupath),fixed_xz_calibration_sha256=sha256(xzpath),
        command=[sys.executable,*sys.argv],shard=shard,
        environment=dict(torch=torch.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(),
                         host=platform.node(),slurm=os.environ['SLURM_JOB_ID']),
        sampled_contract=dict(amplitude_bits_plus_sign=8,sigmoid_signed_bits=8,probability_bits_plus_true_one=8,
            coefficient_bits=16,output_accumulator_bits=64,bin_offsets=POLICIES, joint_strata_grid=GRID,output_rounding='integer RNE BF16',
            and_law='32 Cartesian cells; independent draws per cell/lane; event shared across Wd outputs',
            count_compression='7 disjoint boundary-cell binomials + deterministic full cells, not Gaussian/FSM',input_matrix_T_K=64,
            z_reencoding=False,gate_up_restore_bittrue=False))
    sealed(out/'provenance.json',provenance)
    model=AutoModelForCausalLM.from_pretrained(prep['local_path'],local_files_only=True,
        torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval();check_config(model.config,c['model'])
    result=score(model,ids,c);result.update(case='bf16',shard=shard,provenance_sha256=sha256(out/'provenance.json'))
    sealed(out/'bf16.json',result);print('BF16',shard,result['perplexity'],flush=True)
    for i,l in enumerate(model.model.layers):
        l.mlp=ShortStreamFFN(l.mlp,i).eval()
        for s in ('g','u'):setattr(l.mlp,s+'_top',torch.tensor(gutables[str(i)][s],device='cuda',dtype=torch.float32))
        l.mlp.freeze_down()
    gc.collect();torch.cuda.empty_cache()
    immutable=[(t,t._version,t.data_ptr()) for t in model.parameters()]
    immutable += [(getattr(l.mlp,n),getattr(l.mlp,n)._version,getattr(l.mlp,n).data_ptr()) for l in model.model.layers
                  for n in ('gu_codes','gu_decoded','down_codes','coeff','output_exp','g_top','u_top')]
    for name,law,policy,t,seed in planned(shard):
        configure(model,'sampled',64,seed,xztables,True,True)
        for l in model.model.layers:
            l.mlp.set_spec(8,8,8);l.mlp.reset_short(policy,law,t,seed)
        print('START',name,flush=True)
        result=score(model,ids,c)
        assert all(tensor._version==v and tensor.data_ptr()==ptr for tensor,v,ptr in immutable)
        assert all(l.mlp.calls==c['examples'] for l in model.model.layers)
        result.update(case=name,shard=shard,seed=seed,and_samples=t,policy=policy,law=law,matrix_mode='sampled',
            provenance_sha256=sha256(out/'provenance.json'),
            diagnostics={str(i):l.mlp.short_report() for i,l in enumerate(model.model.layers)})
        if law!='mean':assert all(d['z_reencoding'] is False for d in result['diagnostics'].values())
        sealed(out/(name+'.json'),result)
        print('COMPLETE',name,result['perplexity'],result['seconds'],flush=True)
    sealed(out/'complete.json',dict(status='completed',cases=len(planned(shard))+1,shard=shard,
        documents={p.name:sha256(p) for p in sorted(out.glob('*.json')) if not p.name.endswith('.sha256.json')}))

if __name__=='__main__':main()

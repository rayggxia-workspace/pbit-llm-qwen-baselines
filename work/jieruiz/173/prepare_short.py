from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parents[3]
folder=ROOT/'qwen3/and_direct'
source=(folder/'multiscale_run.py').read_text(encoding='utf-8')
start=source.index('def planned(');end=source.index('\ndef main()',start)
plan='''def planned(shard):
    policy=('original','lower_half','lower_floor')[shard]
    rows=[('%s_mean_s%d'%(policy,s),'mean',policy,64,s) for s in range(3)]
    rows += [('%s_iid64_s%d'%(policy,s),'iid',policy,64,s) for s in range(3)]
    rows += [('%s_joint32_T%d_s%d'%(policy,t,s),'joint32',policy,t,s)
             for t in (32,64,128) for s in range(3)]
    return rows
'''
source=source[:start]+plan+source[end:]
changes={
 'Five Slurm shards; no z resampling in the direct sampled paths.':'Three fixed-four-scale policies, joint stratification, T<=128.',
 'from .multiscale_core import MultiScaleFFN, OFFSETS':'from .short_core import ShortStreamFFN, POLICIES, GRID',
 'pbit-qwen3-and-multiscale-20261024-issue173':'pbit-qwen3-and-short-20261024-issue173',
 '0<=shard<=4':'0<=shard<=2',
 "bin_offsets=OFFSETS":"bin_offsets=POLICIES, joint_strata_grid=GRID",
 "and_law='IID independent branches/lanes/clocks, common event across Wd outputs'":"and_law='32 Cartesian cells; independent draws per cell/lane; event shared across Wd outputs'",
 "count_compression='conditional binomial, not Gaussian'":"count_compression='7 disjoint boundary-cell binomials + deterministic full cells, not Gaussian/FSM'",
 'l.mlp=MultiScaleFFN(':'l.mlp=ShortStreamFFN(',
 'for name,direct,mat,bins,t,seed,spec in planned(shard):':'for name,law,policy,t,seed in planned(shard):',
 "configure(model,mat,64,seed,xztables,mat=='sampled',mat=='sampled')":"configure(model,'sampled',64,seed,xztables,True,True)",
 'l.mlp.set_spec(*spec);l.mlp.reset_multi(bins,direct,t,seed)':'l.mlp.set_spec(8,8,8);l.mlp.reset_short(policy,law,t,seed)',
 'and_samples=t,bins=bins,direct_mode=direct,matrix_mode=mat,':"and_samples=t,policy=policy,law=law,matrix_mode='sampled',",
 'l.mlp.multi_report()':'l.mlp.short_report()',
 "if direct=='sampled':":"if law!='mean':",
}
for a,b in changes.items():
    assert a in source,a
    source=source.replace(a,b)
ast.parse(source);(folder/'short_run.py').write_bytes(source.encode())
sb=(folder/'multiscale.sbatch').read_text(encoding='utf-8')
sb=sb.replace('--array=0-4','--array=0-2').replace('pbit-qwen3-and-multiscale-20261024-issue173','pbit-qwen3-and-short-20261024-issue173')
sb=sb.replace('qwen3.and_direct.test_multiscale ','qwen3.and_direct.test_short qwen3.and_direct.test_multiscale ')
sb=sb.replace('-m qwen3.and_direct.multiscale_run ','-m qwen3.and_direct.short_run ')
(folder/'short.sbatch').write_bytes(sb.encode())
print('Prepared 45 cases + 3 matched BF16; T32/64/128, no FSM model evaluation')

from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parents[3]
folder=ROOT/'qwen3/and_direct'
source=(folder/'run.py').read_text(encoding='utf-8')
begin=source.index('def planned(');end=source.index('\ndef main()',begin)
plan='''def planned(shard):
    if shard==0:
        rows=[('w8_oracle','old_reencode','w8_only',1,64,0,(0,0,0))]
        rows += [('old_reencode_s%d'%s,'old_reencode','sampled',1,64,s,(8,8,8)) for s in range(3)]
        rows += [('mean_B%d_s%d'%(b,s),'mean','sampled',b,64,s,(8,8,8)) for b in (1,2,4,8) for s in range(3)]
        return rows
    pairs={1:((2,64),(2,256)),2:((4,64),(4,256)),3:((8,64),(8,256)),4:((4,1024),(8,1024))}[shard]
    return [('direct_B%d_T%d_s%d'%(b,t,s),'sampled','sampled',b,t,s,(8,8,8)) for b,t in pairs for s in range(3)]
'''
source=source[:begin]+plan+source[end:]
source=source.replace('from .core import DirectFFN','from .multiscale_core import MultiScaleFFN, OFFSETS')
source=source.replace('pbit-qwen3-and-direct-20261024-issue173','pbit-qwen3-and-multiscale-20261024-issue173')
source=source.replace('l.mlp=DirectFFN(', 'l.mlp=MultiScaleFFN(')
source=source.replace('output_accumulator_bits=52','output_accumulator_bits=64,bin_offsets=OFFSETS')
source=source.replace('for name,direct,mat,t,seed,spec in planned(shard):','for name,direct,mat,bins,t,seed,spec in planned(shard):')
source=source.replace('l.mlp.reset_direct(direct,t or 64,seed)','l.mlp.reset_multi(bins,direct,t,seed)')
source=source.replace('and_samples=t,direct_mode=direct','and_samples=t,bins=bins,direct_mode=direct')
source=source.replace('l.mlp.direct_report()','l.mlp.multi_report()')
ast.parse(source);(folder/'multiscale_run.py').write_bytes(source.encode())
sb=(folder/'run.sbatch').read_text(encoding='utf-8').replace('pbit-qwen3-and-direct-20261024-issue173','pbit-qwen3-and-multiscale-20261024-issue173')
sb=sb.replace('qwen3.and_direct.test_core ','qwen3.and_direct.test_multiscale qwen3.and_direct.test_core ')
sb=sb.replace('-m qwen3.and_direct.run ','-m qwen3.and_direct.multiscale_run ')
(folder/'multiscale.sbatch').write_bytes(sb.encode())
print('Prepared multiscale runner and Slurm script')

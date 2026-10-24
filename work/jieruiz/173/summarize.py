import hashlib,json,math,statistics,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ARCHIVE=ROOT.parents[1]/'project_archives/qwen3_and_direct_20261024/sealed-2881.tar.gz'
def sha(b):return hashlib.sha256(b).hexdigest()
assert sha(ARCHIVE.read_bytes())=='1f87f6f00a9ffda47ca03b0bca0d55d2236e6fe99cacd5c6bf88f9eed4d54309'
with tarfile.open(ARCHIVE,'r:gz') as tar:
    blobs={x.name:tar.extractfile(x).read() for x in tar.getmembers() if x.isfile()}
def raw(n):return blobs[n]
def read(n):return json.loads(raw(n))
rows=[];provs=[]
for shard in range(5):
    prefix='results/shard%d/'%shard
    done=read(prefix+'complete.json')
    assert done['status']=='completed' and done['cases']==(11 if shard==0 else 4)
    for name,digest in done['documents'].items():
        assert sha(raw(prefix+name))==digest,(shard,name)
        assert read(prefix+name.replace('.json','.sha256.json'))['sha256']==digest
    assert read(prefix+'complete.sha256.json')['sha256']==sha(raw(prefix+'complete.json'))
    p=read(prefix+'provenance.json');provs.append(p)
    assert p['source']['commit']=='098c7a00db27dded1b7047dc5828871e4b057f70'
    assert p['config_sha256']==sha((ROOT/'qwen3/and_direct/config.json').read_bytes())
    assert p['model']['id']=='Qwen/Qwen3-4B' and p['model']['revision']=='1cfa9a7208912126459214e8b04321603b3df60c'
    log=raw('logs/2881_%d.log'%shard).decode()
    assert 'Ran 12 tests' in log and '\nOK\n' in log and 'Traceback' not in log
    for name in done['documents']:
        obj=read(prefix+name)
        if 'perplexity' not in obj:continue
        assert obj['status']=='completed' and obj['scored_tokens']==1024
        assert obj['all_layer_calls']==[8]*36 and obj['all_layer_input_tokens']==[8*2175]*36
        assert obj['provenance_sha256']==sha(raw(prefix+'provenance.json'))
        assert math.isclose(math.exp(obj['nll_sum']/1024),obj['perplexity'],rel_tol=1e-14)
        row=dict(case=obj['case'],shard=shard,ppl=obj['perplexity'],seconds=obj['seconds'],seed=obj.get('seed'),
                 target_positions_sha256=obj['target_positions_sha256'],raw_sha256=sha(raw(prefix+name)))
        if obj.get('direct_mode')=='sampled':
            d=obj['diagnostics'];assert len(d)==36 and all(not x['z_reencoding'] for x in d.values())
            sums=[sum(x['raw_stats'][i] for x in d.values()) for i in range(7)]
            row.update(mean_event_probability=sums[1]/sums[0],zero_count_fraction=sums[2]/sums[0],
                g_clip_fraction=sums[5]/sums[0],u_clip_fraction=sums[6]/sums[0],
                first_layer_event_probability=d['0']['mean_event_probability'],
                first_layer_zero_count_fraction=d['0']['zero_count_fraction'],
                max_output_accumulator=max(x['raw_stats'][4] for x in d.values()),
                coefficient_nmse_max=max(x['coefficient_nmse'] for x in d.values()))
            assert row['max_output_accumulator']<2**51
        rows.append(row)
assert len(rows)==27 and len({r['target_positions_sha256'] for r in rows})==1
refs=[r for r in rows if r['case']=='bf16'];assert len(refs)==5 and len({r['ppl'] for r in refs})==1
by={r['case']:r for r in rows}
expected={'bf16','w8_oracle'}|{m+'_s%d'%s for m in ('old_reencode','mean_legacy','mean_fixed') for s in range(3)}
expected|={'direct_T%d_s%d'%(t,s) for t in (64,256,1024,4096) for s in range(3)}
assert set(by)==expected and len(by)==23
groups=[]
for name in ('old_reencode','mean_legacy','mean_fixed','direct_T64','direct_T256','direct_T1024','direct_T4096'):
    selected=[by[name+'_s%d'%s] for s in range(3)];v=[r['ppl'] for r in selected]
    g=dict(name=name,mean=statistics.mean(v),population_std=statistics.pstdev(v),per_seed=v,
           mean_seconds=statistics.mean(r['seconds'] for r in selected))
    if name.startswith('direct_'):
        for field in ('mean_event_probability','zero_count_fraction','first_layer_event_probability','first_layer_zero_count_fraction','g_clip_fraction','u_clip_fraction'):
            g[field]=statistics.mean(r[field] for r in selected)
    groups.append(g)
out=ROOT/'qwen3/results/and_direct_20261024';out.mkdir(parents=True,exist_ok=True)
def save(path,obj):path.write_bytes((json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode())
summary=dict(status='verified_completed',physical_results=27,unique_cases=23,scored_targets_per_case=1024,
    protocol='8x128 suffix, context2048, all36layers/fullprefix, no chat; NOT full WT2',
    rows=rows,groups=groups,provenance=provs,source_execution='098c7a00db27dded1b7047dc5828871e4b057f70')
save(out/'SUMMARY.json',summary)
save(out/'RAW_INDEX.json',dict(archive=str(ARCHIVE),archive_sha256=sha(ARCHIVE.read_bytes()),
    remote_root='/home/Hongjie_Zeng/projects/pbit-qwen3-and-direct-20261024-issue173',
    members=[dict(name=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(blobs.items())]))
labels=['旧8位非线性均值→z重编码','直连条件均值、原尺度','直连条件均值、有限恢复系数','直连AND 64次','直连AND 256次','直连AND 1024次','直连AND 4096次']
lines=['# 八位AND流直连Wd：Qwen3-4B初筛结果','',
'结论：直接连接可实现，但当前固定g/u范围下三流独立AND在短流时严重退化；4096次恢复较多精度，仍落后于条件均值。不能沿用上一版“8位均值损失小”作为有限流通过的证据。','',
'Slurm2881五片均完成；27份计分结果（23唯一配置，BF16五次复验完全一致）、原字节SHA及36层全前缀覆盖通过。每片12项功能检查全部通过，包含CUDA整数点积对照。无训练、RTL/PPA。','',
'8段×128=1024目标后缀PPL，准确Attention；不是完整WT2，不能与16/32段旧结果的绝对PPL直接比较。输入x仍固定四档共享64分层T64，Wd W8。','',
'| 方案 | PPL（三seed均值 ± 总体SD） |','|---|---:|',
'| 同轮原BF16 | %.6f |'%by['bf16']['ppl'],
'| W8、原非线性对照 | %.6f |'%by['w8_oracle']['ppl']]
for label,g in zip(labels,groups):lines.append('| %s | %.6f ± %.6f |'%(label,g['mean'],g['population_std']))
lines+=['','## 流为何可以直连，误差为何很大','',
'给定g/u，幅度码gc、uc与sigmoid概率码hc分别经8位独立门限比较，AND事件概率p=gc×hc×uc/256³。每个事件加一次带符号Wd权重；局部输出按固定尺度系数合并，最后除以T并转换BF16。无中间z平均、缩放和再采样。',
'模拟用Binomial(T,p)压缩独立事件，再执行整数Wd归约；同一通道事件共享给所有输出。逐拍三比较器AND及输出整数累计的参考验证通过。此加速是分布等价，不能把GPU执行秒数解释为芯片时间。',
'稀少事件概率的乘积估计相对标准差为sqrt((1-p)/(T*p))。八位只决定门限量化，不能保证有限T时乘积的相对误差小。先统计z再重新定标会提高后续流占空比；本次删除这一步，同时失去这个重新定标机会。','',
'| AND采样数 | 首层平均事件概率 | 首层零事件通道比例 | 全层平均零事件比例 |',
'|---|---:|---:|---:|']
for g in groups[3:]:lines.append('| %s | %.6g | %.2f%% | %.2f%% |'%(g['name'],g['first_layer_event_probability'],100*g['first_layer_zero_count_fraction'],100*g['zero_count_fraction']))
lines+=['','后层统计受到前层噪声改变输入的影响；首层更适合跨T诊断。零事件包括原码为零/负g门控很小的合法情况，不能把每个零事件都算错误。','',
'## 明确的电路边界','',
'幅度8位另符号，sigmoid驱动signed8步长1/8，概率8位另true-one；TRAIN固定每64通道g/u二次幂尺度。恢复系数为预先计算的16位整数，每输出tile公共二次幂指数；输出采用保守signed52，整数RNE到BF16。系数乘法、宽累加、符号/指数和转换都需要硬件，未假定免费。条件均值有限系数对照用于隔离恢复格式影响。',
'gate/up矩阵的尺度恢复仍是FP32参考；本次只验证八位非线性与Wd输出定点路径，不是完整硬件前向。独立三流/各通道独立的随机供给也不同于入口共享64。无新PPA。',
'建议先研究降低SgSu导致的稀少事件问题（更合适固定尺度/分组、分解幅度或中间定标），再让训练适配最终确定的有限流契约。不能以当前64/256次直连方案替换训练前向并预期精度自动保持。','',
'执行源码098c7a00db27dded1b7047dc5828871e4b057f70；每seed结果/模型/数据/配置/校准SHA见SUMMARY.json，归档及成员SHA见RAW_INDEX.json。Issue173 / PR174，结果发布不表示合并。']
(out/'REPORT_ZH.md').write_bytes(('\n'.join(lines)+'\n').encode())
print(json.dumps(dict(bf16=by['bf16']['ppl'],groups=groups),ensure_ascii=False,indent=2))

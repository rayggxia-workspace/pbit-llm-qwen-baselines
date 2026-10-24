# -*- coding: utf-8 -*-
import hashlib,json,math,statistics,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ARCHIVE=ROOT.parents[1]/'project_archives/smurf_model_20261024/sealed-2898-2902.tar.gz'
def sha(b):return hashlib.sha256(b).hexdigest()
with tarfile.open(ARCHIVE) as tar:
    blobs={m.name:tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
def read(n):return json.loads(blobs[n])
expected=['462d4fe168fbb7168a5cd742ec1270f02f6ce466','3ac8bfdb05ff6637b058eb8d68a004815b2fc958']
rows=[];provs=[];unique=set()
for shard in range(8):
    prefix='results/shard%d/'%shard;done=read(prefix+'complete.json')
    assert done['status']=='completed' and done['cases']==16
    assert read(prefix+'complete.sha256.json')['sha256']==sha(blobs[prefix+'complete.json'])
    for name,h in done['documents'].items():
        assert sha(blobs[prefix+name])==h
        assert read(prefix+name.replace('.json','.sha256.json'))['sha256']==h
    prov=read(prefix+'provenance.json');provs.append(prov)
    assert prov['source']['commit']==expected[shard//4]
    assert prov['config_sha256']==prov['source']['files_sha256']['qwen3/smurf_swish/model_config.json']
    assert prov['model']['id']=='Qwen/Qwen3-4B'
    assert prov['model']['revision']=='1cfa9a7208912126459214e8b04321603b3df60c'
    job=2898 if shard<4 else 2902;log=blobs['logs/%d_%d.log'%(job,shard)].decode()
    assert 'Ran 13 tests' in log and '\nOK\n' in log and 'Traceback' not in log
    for name in done['documents']:
        o=read(prefix+name)
        if 'perplexity' not in o:continue
        assert o['status']=='completed' and o['scored_tokens']==1024
        assert o['all_layer_calls']==[8]*36 and o['all_layer_input_tokens']==[17400]*36
        assert o['provenance_sha256']==sha(blobs[prefix+'provenance.json'])
        assert math.isclose(math.exp(o['nll_sum']/1024),o['perplexity'],rel_tol=1e-14)
        row={k:o.get(k) for k in ('case','shard','seed','mode','T','G','states','Sneg','seconds','target_positions_sha256')}
        row.update(ppl=o['perplexity'],raw_sha256=sha(blobs[prefix+name]))
        if 'diagnostics' in o:
            ds=o['diagnostics'];assert len(ds)==36
            assert all(not d['z_reencoding'] and not d['g_online_absmax'] and not d['g_per_value_bin_selector']
                and d['front_T']==64 and d['front_K']==64 and d['fsm_sample_after_update'] for d in ds.values())
            assert max(d['accumulator_observed_max'] for d in ds.values())<2**63
            for field in ('g_clip_fraction','g_zero_code_fraction','g_rms','g_max',
                          'expected_event_probability','zero_count_fraction','accumulator_observed_max'):
                row[field]=[ds[str(i)][field] for i in range(36)]
            key=(o['mode'],o['G'],o['Sneg'],o['seed'],None if o['mode']=='lut_mean' else o['states'],o['T'])
        else:key=('bf16',)
        unique.add(key);rows.append(row)
assert len(rows)==128 and len(unique)==118
refs=[r for r in rows if r['case']=='bf16'];assert len(refs)==8 and len({r['ppl'] for r in refs})==1
assert refs[0]['ppl']==13.566049199388152
assert len({r['target_positions_sha256'] for r in rows})==1
for k in ('data','model','prepared_sha256','test_token_ids_sha256','fixed_xz_calibration_sha256','fixed_gu_calibration_sha256'):
    assert all(p[k]==provs[0][k] for p in provs)
groups=[]
for shard in range(8):
    for mode,T in [('lut_mean',64),('fsm_mean',64),('fsm_mean',128),('fsm',64),('fsm',128)]:
        picked=[r for r in rows if r['shard']==shard and r['mode']==mode and r['T']==T]
        assert len(picked)==3 and {r['seed'] for r in picked}=={0,1,2}
        vals=[r['ppl'] for r in picked]
        groups.append(dict(shard=shard,G=picked[0]['G'],states=picked[0]['states'],Sneg=picked[0]['Sneg'],mode=mode,T=T,
            mean=statistics.mean(vals),population_std=statistics.pstdev(vals),per_seed=vals,
            mean_seconds=statistics.mean(r['seconds'] for r in picked),
            g_clip_fraction=statistics.mean(v for r in picked for v in r['g_clip_fraction'])))
# Same LUT control, same front RNG, independent jobs: exact replay.
for seed in range(3):
    a=[r['ppl'] for r in rows if r['shard']==0 and r['mode']=='lut_mean' and r['seed']==seed][0]
    b=[r['ppl'] for r in rows if r['shard']==1 and r['mode']=='lut_mean' and r['seed']==seed][0]
    assert a==b
out=ROOT/'qwen3/results/smurf_swish_20261024/model';out.mkdir(parents=True,exist_ok=True)
def save(n,o):(out/n).write_bytes((json.dumps(o,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
save('SUMMARY.json',dict(status='verified_completed',physical_results=128,unique_cases=118,
    protocol='8x128 suffix, context2048, 36FFN/allprefix, accurate Attention; NOT full WT2',
    source_executions=expected,provenance=provs,rows=rows,groups=groups,matched_bf16=refs[0]['ppl']))
save('RAW_INDEX.json',dict(archive=str(ARCHIVE),archive_sha256=sha(ARCHIVE.read_bytes()),
    remote_root='/home/Hongjie_Zeng/projects/pbit-qwen3-smurf-model-20261024-issue175',
    members=[dict(name=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(blobs.items())]))
gb={(g['shard'],g['mode'],g['T']):g for g in groups}
lines=['# 固定g范围的Swish FSM：Qwen3-4B试测','',
'128份计分全部封存、118唯一任务/配置、原始SHA、36层全前缀和同轮BF16核验通过。每片13项预检通过，包括逐拍CUDA与CPU相同随机数重放、FSM计数均值方差和整数Wd对照。原始2894编译失败记录保留，修复后2898/2902完成，未覆盖失败快照。','',
'**8×128=1024目标后缀PPL，不是完整WT2；模型Qwen3-4B后训练，准确Attention，无训练。BF16=13.566049。** 概率项均3seed；前级固定W8/x四档共享64 T=K64。','',
'| 固定G | 状态数 | 负输出单位Sf | 精确SiLU表条件均值 | FSM64条件均值 | 实际FSM64 | FSM128条件均值 | 实际FSM128 |',
'|---:|---:|---:|---:|---:|---:|---:|---:|']
for shard in range(8):
    a=gb[(shard,'lut_mean',64)]
    vals=[gb[(shard,m,t)]['mean'] for m,t in [('lut_mean',64),('fsm_mean',64),('fsm',64),('fsm_mean',128),('fsm',128)]]
    lines.append('| %g | %d | %g | %s |'%(a['G'],a['states'],a['Sneg'],' | '.join('%.3f'%v for v in vals)))
best=min((g for g in groups if g['mode']=='fsm'),key=lambda g:g['mean'])
lines+=['','本次实际FSM最好配置：G=%g、%d状态、负输出单位%g、T=%d，PPL=%.6f。所有配置仍明显偏离原模型，不能称可用替换。'%(best['G'],best['states'],best['Sneg'],best['T'],best['mean']),
'','范围固定并不必然失败：精确SiLU表控制仍有接近参考的配置。FSM条件均值已经恶化，证明本次并非单靠增加采样即可解决；有限状态函数近似、启动和系数量化是独立瓶颈。小G还叠加截断，均值表也会恶化。先前论文正半轴0..1的函数MAE不能推广到有正负、离群值、36层累积的LLM。',
'','SiLU不是齐次函数：G×SiLU(g/G)≠SiLU(g)。本次目标明确为SiLU(Gq/256)/Sf，G在非线性内部；固定二进制小数点可避免逐输入最大值和g选档，但一个Bernoulli流不能无单位表示任意实数。该失败不是故意采用错误的尺度恢复。',
'','FSM每个g复位0，逐拍输入R8比较、饱和加减1、状态系数R8比较，与独立u比较AND；无预热，无z重编码，Wd只最终精确整数统计。非线性使用IID输入/输出/u，前级矩阵仍分层64；未把FSM有记忆过程压缩成Binomial。输出符号和Sf×Su通过Wd对齐移位恢复。',
'','64/128分别使用各自有限时长占用拟合的系数，因此跨T差异同时包含拟合与采样改变，不能全归采样方差。此前三路方案仍通过整数符号/指数恢复真实g的sigmoid驱动，不是把SiLU(g/G)在输出端简单乘G。',
'','逐层g范围、RMS和截断率来自每种替换方案自身的实际运行；差的方案会改变后续层输入，不能把这些诊断称为未改动BF16模型的原始分布。',
'','G=1/2/4是在观察首轮G8/16诊断后追加的探索，不是独立测试确认。FSM系数按有限T占用均匀输入网格拟合，不是端到端训练，也未按测试集调参。当前失败只针对这类4/8状态计数链及拟合，不否定全部FSM、其他输入编码或再训练。',
'','gate/up恢复仍FP32参考边界，尚非整FFN bittrue/TLM/RTL/PPA。条件均值是诊断oracle，不是零周期硬件。前级64＋后级64/128至少128/192拍，另计归约转换访存。详细各seed、逐层范围、模型/语料/校准/源码SHA见SUMMARY和RAW_INDEX。']
(out/'REPORT_ZH.md').write_bytes(('\n'.join(lines)+'\n').encode('utf-8'))
print(json.dumps(dict(bf16=refs[0]['ppl'],best=best,table=groups),ensure_ascii=False,indent=2))

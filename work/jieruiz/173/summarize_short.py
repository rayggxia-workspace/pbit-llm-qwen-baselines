# -*- coding: utf-8 -*-
"""Verify all sealed Slurm2891 records; never rewrite archived bytes."""
import hashlib,json,math,statistics,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ARCHIVE=ROOT.parents[1]/'project_archives/qwen3_and_direct_20261024/short-sealed-2891.tar.gz'
def sha(b):return hashlib.sha256(b).hexdigest()
assert sha(ARCHIVE.read_bytes())=='e498dc55cfe0dea649f52c3c4635272f32af33d67114b1270328f69ca9587467'
with tarfile.open(ARCHIVE) as t:blobs={x.name:t.extractfile(x).read() for x in t.getmembers() if x.isfile()}
def read(n):return json.loads(blobs[n])
execution=read('snapshot-c44c2edc/execution.json')
assert execution['commit']=='c44c2edc23a9a66c9e48c7f9cf99300fa34cefb0'
rows=[];provs=[]
for shard,policy in enumerate(('original','lower_half','lower_floor')):
    pre='results/shard%d/'%shard;done=read(pre+'complete.json')
    assert done['status']=='completed' and done['cases']==16
    assert read(pre+'complete.sha256.json')['sha256']==sha(blobs[pre+'complete.json'])
    for name,h in done['documents'].items():
        assert sha(blobs[pre+name])==h
        assert read(pre+name.replace('.json','.sha256.json'))['sha256']==h
    p=read(pre+'provenance.json');provs.append(p)
    assert p['source']==execution and p['config_sha256']==sha((ROOT/'qwen3/and_direct/config.json').read_bytes())
    assert p['model']['id']=='Qwen/Qwen3-4B' and p['model']['revision']=='1cfa9a7208912126459214e8b04321603b3df60c'
    log=blobs['logs/2891_%d.log'%shard].decode()
    assert 'Ran 27 tests' in log and '\nOK\n' in log and 'Traceback' not in log
    for name in done['documents']:
        o=read(pre+name)
        if 'perplexity' not in o:continue
        assert o['status']=='completed' and o['scored_tokens']==1024
        assert o['all_layer_calls']==[8]*36 and o['all_layer_input_tokens']==[17400]*36
        assert o['provenance_sha256']==sha(blobs[pre+'provenance.json'])
        assert math.isclose(math.exp(o['nll_sum']/1024),o['perplexity'],rel_tol=1e-14)
        row={k:o.get(k) for k in ('case','shard','seed','policy','law','and_samples','seconds','target_positions_sha256')}
        row.update(ppl=o['perplexity'],raw_sha256=sha(blobs[pre+name]))
        if 'diagnostics' in o:
            ds=o['diagnostics'];assert len(ds)==36
            assert all(not d['z_reencoding'] and not d['fsm'] and d['front_T']==64 and d['front_K']==64 for d in ds.values())
            assert max(d['output_accumulator_observed_max'] for d in ds.values())<2**63
            row['first_layer']=ds['0']
            row['g_clip_fraction_all_layers']=[ds[str(i)]['g_clip_fraction'] for i in range(36)]
            row['g_max_all_layers']=[ds[str(i)]['g_max'] for i in range(36)]
        rows.append(row)
assert len(rows)==48 and len({r['case'] for r in rows})==46
assert len({r['target_positions_sha256'] for r in rows})==1
refs=[r for r in rows if r['case']=='bf16'];assert len(refs)==3 and len({r['ppl'] for r in refs})==1
for k in ('data','model','prepared_sha256','test_token_ids_sha256','fixed_gu_calibration_sha256','fixed_xz_calibration_sha256'):
    assert all(p[k]==provs[0][k] for p in provs)
by={r['case']:r for r in rows};groups=[]
for policy in ('original','lower_half','lower_floor'):
    for label in ('mean','iid64','joint32_T32','joint32_T64','joint32_T128'):
        name=policy+'_'+label;selected=[by[name+'_s%d'%s] for s in range(3)];v=[r['ppl'] for r in selected]
        groups.append(dict(name=name,mean=statistics.mean(v),population_std=statistics.pstdev(v),per_seed=v,
                           mean_seconds=statistics.mean(r['seconds'] for r in selected),
                           first_layer_g_clip=statistics.mean(r['first_layer']['g_clip_fraction'] for r in selected),
                           first_layer_u_clip=statistics.mean(r['first_layer']['u_clip_fraction'] for r in selected)))
old=json.loads((ROOT/'qwen3/results/and_direct_20261024/multiscale/SUMMARY.json').read_bytes());oldby={r['case']:r for r in old['rows']}
assert by['bf16']['ppl']==oldby['bf16']['ppl']
for s in range(3):
    assert by['original_iid64_s%d'%s]['ppl']==oldby['direct_B4_T64_s%d'%s]['ppl']
    assert by['original_mean_s%d'%s]['ppl']==oldby['mean_B4_s%d'%s]['ppl']
out=ROOT/'qwen3/results/and_direct_20261024/short';out.mkdir(parents=True,exist_ok=True)
def save(n,o):(out/n).write_bytes((json.dumps(o,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
save('SUMMARY.json',dict(status='verified_completed',physical_results=48,unique_cases=46,scored_tokens=1024,
     protocol='8x128 suffix, context2048, all36 layers/fullprefix, accurate Attention; NOT full WT2',
     source_execution=execution['commit'],provenance=provs,rows=rows,groups=groups,original_replay_exact=True))
save('RAW_INDEX.json',dict(archive=str(ARCHIVE),archive_sha256=sha(ARCHIVE.read_bytes()),
     remote_root='/home/Hongjie_Zeng/projects/pbit-qwen3-and-short-20261024-issue173',
     members=[dict(name=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(blobs.items())]))
gb={r['name']:r for r in groups};bf=refs[0]['ppl']
lines=['# 三路AND：固定四档与32联合分层短流结果','',
'Slurm2891三片全部封存完成。48份计分/46唯一配置、27项服务器预检、36层全部前缀及documents/sidecar SHA已核验。Qwen3-4B后训练，前级固定W8、x四档共享64分层T=K64，Attention准确；无新训练。','',
'**这是8×128=1024目标后缀PPL，不是完整WT2。** 每个概率配置3seed；同轮原BF16为%.6f。'%bf,'',
'| 固定四档策略 | 仅非线性条件均值 | IID64 | 联合分层32 | 联合分层64 | 联合分层128 |','|---|---:|---:|---:|---:|---:|']
for policy,desc in [('original','S,S/4,S/16,S/64'),('lower_half','S/2,S/8,S/32,S/128'),('lower_floor','S,S/4,S/16,S/128')]:
    lines.append('| %s | %s |'%(desc,' | '.join('%.4f'%gb[policy+'_'+v]['mean'] for v in ('mean','iid64','joint32_T32','joint32_T64','joint32_T128'))))
best=gb['lower_half_joint32_T128']
lines+=['','最好测试项为整体减半四档＋联合分层128：%.6f，较BF16增加%.2f%%。这属于本次探索网格内选择，不能当独立测试确认；还未达到原模型质量。'%(best['mean'],100*(best['mean']/bf-1)),
'','条件均值仍保留前级随机矩阵，只去掉后级有限流噪声，不是可部署零采样路径。分层降低了相同概率码下的计数方差，但深层PPL是非线性函数，不保证每个seed或PPL均改善。不能把理论局部方差减小直接说成整模型无损。',
'','所有S来自TRAIN固定校准，无在线组最大值。sigmoid输入由幅度码、符号和指数通过整数移位/舍入恢复真实g驱动，再查P8表；不是sigma(g/S)。三条流按4×2×4=32联合区间，每区间1/2/4次。Wd直连事件、整数计数/对齐，z无重新编码；gate/up恢复仍FP32参考，非全FFN bittrue。',
'','原尺度mean与IID64的三个seed及BF16均与Slurm2886逐值一致。配置信息、各seed、标准差、层覆盖、原件和模型/数据/执行SHA见SUMMARY与RAW_INDEX。PR174待审；FSM是另一个模块，不能混用这里的PPL。']
(out/'REPORT_ZH.md').write_bytes(('\n'.join(lines)+'\n').encode('utf-8'))
print(json.dumps(dict(bf16=bf,groups=groups),ensure_ascii=False,indent=2))

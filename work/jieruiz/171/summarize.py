"""Verify sealed original archive bytes before reporting the 28-case pilot."""
import hashlib,json,math,statistics,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ARCHIVE=ROOT.parents[1]/'project_archives/qwen3_nonlinear_width_20261024/sealed-2880.tar.gz'
def sha(b):return hashlib.sha256(b).hexdigest()
with tarfile.open(ARCHIVE,'r:gz') as tar:
    blobs={x.name:tar.extractfile(x).read() for x in tar.getmembers() if x.isfile()}
def raw(n):return blobs['results/'+n]
def read(n):return json.loads(raw(n))
complete=read('complete.json')
assert complete['status']=='completed' and complete['cases']==28
for name,digest in complete['documents'].items():
    assert sha(raw(name))==digest,name
for name in complete['documents']:
    assert read(name.replace('.json','.sha256.json'))['sha256']==sha(raw(name)),name
assert read('complete.sha256.json')['sha256']==sha(raw('complete.json'))
provenance=read('provenance.json');calibration=read('calibration.json')
assert provenance['source']['commit']=='71cb58d0b4cfbf42004c34e28d5b5250f6a000c8'
assert provenance['model']['id']=='Qwen/Qwen3-4B'
rows=[]
for name in complete['documents']:
    obj=read(name)
    if 'perplexity' not in obj:continue
    assert obj['status']=='completed' and obj['scored_tokens']==2048
    assert obj['all_layer_calls']==[16]*36
    assert obj['all_layer_input_tokens']==[16*2175]*36
    assert obj['provenance_sha256']==sha(raw('provenance.json'))
    assert abs(math.exp(obj['nll_sum']/obj['scored_tokens'])-obj['perplexity'])<1e-12
    if obj['case']!='bf16':
        assert obj['calibration_sha256']==sha(raw('calibration.json'))
        assert len(obj['diagnostics'])==36
    aggregate=[sum(d['raw_stats'][i] for d in obj.get('diagnostics',{}).values()) for i in range(11)]
    rows.append(dict(case=obj['case'],ppl=obj['perplexity'],seconds=obj['seconds'],
        seed=obj.get('seed'),spec=obj.get('spec'),target_positions_sha256=obj['target_positions_sha256'],
        g_clip_fraction=aggregate[1]/max(aggregate[0],1),u_clip_fraction=aggregate[2]/max(aggregate[0],1),
        g_nmse=aggregate[5]/max(aggregate[6],1e-30),u_nmse=aggregate[7]/max(aggregate[8],1e-30),
        z_nmse=aggregate[9]/max(aggregate[10],1e-30),raw_sha256=sha(raw(name))))
expected={'bf16','w8_oracle'}|{'gu%d'%b for b in (6,7,8,10,12)}|{'field%d'%b for b in (8,10,12)}|{'prob%d'%b for b in (6,8,10,12)}
expected|={'combined_%d_%d_%d'%s for s in ((6,8,8),(8,8,8),(8,10,8),(10,10,10),(12,12,12))}
expected|={'fixed64_%d_%d_%d_s%d'%(*s,seed) for s in ((0,0,0),(8,8,8),(10,10,10)) for seed in (0,1,2)}
assert {r['case'] for r in rows}==expected and len(rows)==28
assert len({r['target_positions_sha256'] for r in rows})==1
by={r['case']:r for r in rows}
groups=[]
for spec in ((0,0,0),(8,8,8),(10,10,10)):
    values=[by['fixed64_%d_%d_%d_s%d'%(*spec,s)]['ppl'] for s in (0,1,2)]
    groups.append(dict(spec=spec,mean=statistics.mean(values),population_std=statistics.pstdev(values),per_seed=values))
scales={s:sorted(set(v for l in calibration['tables'].values() for v in l[s])) for s in ('g','u')}
summary=dict(status='verified_completed',cases=28,scored_tokens=2048,all_layers=36,
    protocol='16x128 vectorized suffix, context2048, no chat; NOT full WT2',
    source=provenance['source'],model=provenance['model'],data=provenance['data'],
    config_sha256=provenance['config_sha256'],prepared_sha256=provenance['prepared_sha256'],
    calibration_sha256=sha(raw('calibration.json')),provenance_sha256=sha(raw('provenance.json')),
    nonlinear='conditional mean, finite codes/LUT, no finite AND sampling',
    matrix_bittrue=False,rows=rows,random_matrix_groups=groups,calibration_scale_values=scales)
out=ROOT/'qwen3/results/nonlinear_width_20261024';out.mkdir(parents=True,exist_ok=True)
def save(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
save(out/'SUMMARY.json',summary)
save(out/'RAW_INDEX.json',dict(archive=str(ARCHIVE),archive_sha256=sha(ARCHIVE.read_bytes()),
    remote_root='/home/Hongjie_Zeng/projects/pbit-qwen3-nonlinear-width-20261024-issue171',
    members=[dict(name=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(blobs.items())]))
base=by['w8_oracle']['ppl']
lines=['# Qwen3-4B非线性位宽初筛结果（Issue171）','',
    'Slurm2880，28/28封存结果及原字节SHA、36层/全部前缀覆盖通过。无训练，Attention保持准确。',
    '这是16段×128=2048目标token的后缀PPL，不是完整WT2；与旧32段PPL不可直接比较。非线性使用三独立流AND的条件均值，无有限流采样噪声，矩阵恢复仍是FP32参考。','',
    '幅度b位不含符号；sigmoid驱动f位含符号、固定[-16,16)；概率p位另有true-one。TRAIN固定每层/64通道PoT范围，测试不调尺度。','',
    '| 单因素/组合（幅度/驱动/概率） | PPL | 相对同轮W8原非线性 |','|---|---:|---:|']
for name in ['bf16','w8_oracle']+['gu%d'%b for b in (6,7,8,10,12)]+['field%d'%b for b in (8,10,12)]+['prob%d'%b for b in (6,8,10,12)]+['combined_%d_%d_%d'%s for s in ((6,8,8),(8,8,8),(8,10,8),(10,10,10),(12,12,12))]:
    row=by[name];lines.append('| %s | %.6f | %+.3f%% |'%(name,row['ppl'],100*(row['ppl']/base-1)))
lines+=['','原BF16与W8替换参考的矩阵权重/内部算术不同；不能把低于BF16解释为量化提高模型能力。','',
    '| 固定四档T64/K64随机矩阵，非线性格式 | 三seed PPL均值±总体SD | 相对同背景原非线性 |','|---|---:|---:|']
for g in groups:lines.append('| %s | %.6f ± %.6f | %+.3f%% |'%('/'.join(map(str,g['spec'])),g['mean'],g['population_std'],100*(g['mean']/groups[0]['mean']-1)))
lines+=['','0/0/0表示未改非线性参考，不表示0位硬件。随机性来自矩阵，三流非线性仍为条件均值。',
    '', '## 位宽建议与限制','',
    '先以8位幅度+符号、8位sigmoid驱动、8位概率+满幅旁路作为候选接口，10/10/10保留作精度余量对照。是否够用须结合上述实际差值判断，不能只看单因素；6位幅度在本批已有明显退化。7位幅度+符号单因素有结果，但尚无其完整组合/随机背景验收，不能宣称总共8位已验证。',
    '有限三流AND样本数、驱动物理误差/相关性、有限跨档与跨tile累加、实际PPA均未验证。该结果只初筛数值接口，不能继承为完整电路PPL；不根据本次test重新调校准范围。',
    '', 'g固定尺度取值：'+str(scales['g']), 'u固定尺度取值：'+str(scales['u']),
    '', '源码执行：`'+provenance['source']['commit']+'`；完整模型/数据/配置/源码SHA见SUMMARY，原件归档位置/成员SHA见RAW_INDEX。']
(out/'REPORT_ZH.md').write_bytes(('\n'.join(lines)+'\n').encode())
print(json.dumps(dict(cases=len(rows),base=base,groups=groups),ensure_ascii=False))

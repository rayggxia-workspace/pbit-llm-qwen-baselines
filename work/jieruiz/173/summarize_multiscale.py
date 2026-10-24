"""Read sealed multiscale results without extracting/reformatting originals."""
import hashlib,json,math,statistics,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ARCHIVE=ROOT.parents[1]/'project_archives/qwen3_and_direct_20261024/multiscale-sealed-2886.tar.gz'
def sha(b):return hashlib.sha256(b).hexdigest()
assert sha(ARCHIVE.read_bytes())=='9d7fbc40697ebbd6e4a80194778308784e6b2b803864438fbbd5b34675935b4b'
with tarfile.open(ARCHIVE,'r:gz') as tar:
    blobs={x.name:tar.extractfile(x).read() for x in tar.getmembers() if x.isfile()}
def raw(n):return blobs[n]
def read(n):return json.loads(raw(n))
execution=read('snapshot-8249fad6/execution.json')
assert execution['commit']=='8249fad60203679f6fc51f0661aaaac2889c86f1'
rows=[];provs=[];raw_cases={}
for shard in range(5):
    prefix='results/shard%d/'%shard
    done=read(prefix+'complete.json')
    assert done['status']=='completed' and done['cases']==(17 if shard==0 else 7)
    for name,digest in done['documents'].items():
        assert sha(raw(prefix+name))==digest,(shard,name)
        assert read(prefix+name.replace('.json','.sha256.json'))['sha256']==digest
    assert read(prefix+'complete.sha256.json')['sha256']==sha(raw(prefix+'complete.json'))
    p=read(prefix+'provenance.json');provs.append(p)
    assert p['source']==execution
    assert p['config_sha256']==sha((ROOT/'qwen3/and_direct/config.json').read_bytes())
    assert p['model']['id']=='Qwen/Qwen3-4B' and p['model']['revision']=='1cfa9a7208912126459214e8b04321603b3df60c'
    log=raw('logs/2886_%d.log'%shard).decode()
    assert 'Ran 18 tests' in log and '\nOK\n' in log and 'Traceback' not in log
    for name in done['documents']:
        obj=read(prefix+name)
        if 'perplexity' not in obj:continue
        assert obj['status']=='completed' and obj['scored_tokens']==1024
        assert obj['all_layer_calls']==[8]*36 and obj['all_layer_input_tokens']==[8*2175]*36
        assert obj['provenance_sha256']==sha(raw(prefix+'provenance.json'))
        assert math.isclose(math.exp(obj['nll_sum']/1024),obj['perplexity'],rel_tol=1e-14)
        raw_cases[obj['case']]=obj
        row=dict(case=obj['case'],shard=shard,ppl=obj['perplexity'],seconds=obj['seconds'],seed=obj.get('seed'),
                 target_positions_sha256=obj['target_positions_sha256'],raw_sha256=sha(raw(prefix+name)))
        if obj.get('direct_mode') in ('sampled','mean'):
            ds=obj['diagnostics'];assert len(ds)==36 and all(not d['z_reencoding'] for d in ds.values())
            row['first_layer']=ds['0']
            row['all_layer_rms']={k:[ds[str(i)][k] for i in range(36)] for k in ('x_rms','g_rms','u_rms')}
            assert max(d['output_accumulator_observed_max'] for d in ds.values())<2**63
            row['required_bound_bits']=max(d['required_bound_bits'] for d in ds.values())
        rows.append(row)
assert len(rows)==45 and len({r['target_positions_sha256'] for r in rows})==1
refs=[r for r in rows if r['case']=='bf16'];assert len(refs)==5 and len({r['ppl'] for r in refs})==1
by={r['case']:r for r in rows}
names=['old_reencode']+['mean_B%d'%b for b in (1,2,4,8)]+['direct_B%d_T%d'%(b,t) for b,t in ((2,64),(2,256),(4,64),(4,256),(8,64),(8,256),(4,1024),(8,1024))]
expected={'bf16','w8_oracle'}|{name+'_s%d'%s for name in names for s in range(3)}
assert set(by)==expected and len(by)==41
old=json.loads((ROOT/'qwen3/results/and_direct_20261024/SUMMARY.json').read_bytes())
oldby={r['case']:r for r in old['rows']}
assert by['bf16']['ppl']==oldby['bf16']['ppl']
for s in range(3):
    assert by['old_reencode_s%d'%s]['ppl']==oldby['old_reencode_s%d'%s]['ppl']
    assert by['mean_B1_s%d'%s]['ppl']==oldby['mean_fixed_s%d'%s]['ppl']
groups=[]
for name in names:
    selected=[by[name+'_s%d'%s] for s in range(3)];v=[r['ppl'] for r in selected]
    g=dict(name=name,mean=statistics.mean(v),population_std=statistics.pstdev(v),per_seed=v,
        mean_seconds=statistics.mean(r['seconds'] for r in selected))
    if name!='old_reencode':
        g['first_layer']={k:statistics.mean(r['first_layer'][k] for r in selected) for k in (
            'mean_event_probability','x_rms','g_rms','u_rms','mean_g_probability','mean_u_probability')}
        g['first_layer_bin_hist']=[[sum(r['first_layer']['bin_hist'][j][k] for r in selected) for k in range(15)] for j in range(3)]
        if name.startswith('direct_'):g['first_layer']['zero_count_fraction']=statistics.mean(r['first_layer']['zero_count_fraction'] for r in selected)
    groups.append(g)
out=ROOT/'qwen3/results/and_direct_20261024/multiscale';out.mkdir(parents=True,exist_ok=True)
def save(path,obj):path.write_bytes((json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode())
summary=dict(status='verified_completed',physical_results=45,unique_cases=41,scored_targets_per_case=1024,
    protocol='8x128 suffix, context2048, all36layers/fullprefix, no chat; NOT full WT2',
    source_execution=execution['commit'],provenance=provs,rows=rows,groups=groups,
    matched_old_bf16_and_controls_exact=True)
save(out/'SUMMARY.json',summary)
save(out/'RAW_INDEX.json',dict(archive=str(ARCHIVE),archive_sha256=sha(ARCHIVE.read_bytes()),
    remote_root='/home/Hongjie_Zeng/projects/pbit-qwen3-and-multiscale-20261024-issue173',
    members=[dict(name=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(blobs.items())]))
gby={g['name']:g for g in groups}
lines=['# g/u固定多档编码＋尺度感知sigmoid＋Wd输出对齐','',
'结论：固定多档显著改善直连AND短流精度；B8/T256三seed PPL为13.9061，相对同轮原BF16 13.5660约+2.51%，B8/T1024为13.4698。B8/T64仍为15.9779，不能认为64次已无损。B4/T256为14.4663，可作为更简单的对照。此次无需训练、无需中间z恢复/重采样，但新增选档、指数与对齐成本，尚无PPA。','',
'Slurm2886五片完成；45份封存计分/41唯一配置、18项服务器功能检查、36层全前缀及原字节SHA通过。后训练Qwen3-4B，准确Attention，无训练；8段×128=1024目标后缀PPL，不是完整WT2。源码8249fad6。','',
'本轮BF16、旧路径三seed和B1条件均值分别与前轮逐值一致，可按同协议比较。入口x仍固定四档共享64分层T64，权重W8；非线性三流独立IID。','',
'| g/u尺度 | 无有限AND噪声的条件均值PPL | AND64次 | AND256次 | AND1024次 |',
'|---|---:|---:|---:|---:|']
for b in (1,2,4,8):
    values=[gby['mean_B%d'%b]['mean']]
    for t in (64,256,1024):
        name='direct_B%d_T%d'%(b,t)
        if b==1:values.append(next(g['mean'] for g in old['groups'] if g['name']=='direct_T%d'%t))
        elif name in gby:values.append(gby[name]['mean'])
        else:values.append(None)
    lines.append('| B%d | %s |'%(b,' | '.join('未测' if v is None else '%.4f'%v for v in values)))
lines+=['','同轮BF16 %.6f；旧8位均值→z重编码 %.6f。上述随机配置为3seed平均；每seed及总体SD见SUMMARY。B1有限流沿用同协议已完成前轮，不重复跑。'%(by['bf16']['ppl'],gby['old_reencode']['mean']),
'','## 分档到底改变了什么','',
'旧版每64通道只有一个TRAIN固定最大量程S。B2=[S,S/64]；B4=[S,S/4,S/16,S/64]；B8=[S,S/2,...,S/128]。各通道比较后选能容纳值的最小档，不在推理时计算组最大值。B8同时提高档位密度和低端覆盖，不把提升归因于档数的单一因素。','',
'| 首层统计（条件均值路径） | B1 | B2 | B4 | B8 |','|---|---:|---:|---:|---:|']
for key,label in [('x_rms','x RMS'),('g_rms','g RMS'),('u_rms','u RMS'),('mean_g_probability','平均g幅度概率'),('mean_u_probability','平均u幅度概率'),('mean_event_probability','平均AND概率')]:
    lines.append('| %s | %s |'%(label,' | '.join('%.6g'%gby['mean_B%d'%b]['first_layer'][key] for b in (1,2,4,8))))
lines+=['','线性映射的数值大小由训练权重与输入相关性决定，没有保证g/u大于x。是否适合短流主要看|g|/Sg和|u|/Su，而不是原数值单位；最大值定标使典型小值占空比偏低。后层统计会受前层噪声影响，首层跨方案输入相同。','',
'## sigmoid与输出对齐','',
'g=sign*q*2^(e-8)。幅度流用q/256，但sigmoid驱动用clip(RNE(sign*q*2^(e-5)),-128,127)，每码1/8，再查固定P8 LUT与独立门限比较。没有把sigma(g)替换成sigma(g/Sg)，也没有执行运行时FP32 sigmoid。物理p-bit应通过真实g/2驱动tanh响应；DAC增益及有限相关时间另测。',
'g/u档位的指数偏移相加：B4共16配对但只有7个乘积指数，B8共64配对但只有15个。先按同指数归约带符号Wd W8贡献，再移位到最小公共单位并合并。64倍是6位；双边都是64倍则12位。移位方向由概率被放大还是数值单位变大决定，不能省略符号和Wd自身的scale。',
'这里指数合并指同一局部量程/权重scale域；不同tile的原始Sg0*Su0和Wd量化尺度不同，仍须执行既定系数恢复，不能直接在整矩阵中无条件共用7或15个计数器。',
'本轮用准确整数归约，未测近似APC。16位定点scale系数沿用前轮，移位需额外保护位；采用signed64模拟容器并校验实际配置上界，不能把它说成必需64位电路或免费移位。低层可分层归约并最终舍入，但需另测误差。',
'随机流本身不携带指数；元数据须跟随流或由分桶/布线隐式确定。g/u→sigmoid驱动已用整数移位/舍入/饱和实现，gate/up矩阵恢复仍是前轮FP32参考边界，不是全FFN bittrue/PPA。','',
'## 文献能借鉴什么','',
'[Scaled Population Arithmetic, ASP-DAC2020](https://research.ibm.com/publications/scaled-population-arithmetic-for-efficient-stochastic-computing)用显式缩放改善随机表示的误差，但属于并行population运算，不能继承其硬件收益。',
'[Integral Stochastic Computing](https://arxiv.org/abs/1509.08972)扩展表示范围并修改FSM激活，原文§II-C及IV还讨论sigmoid/tanh关系；它的DBN不是SwiGLU。',
'[Hardware-Driven Nonlinear Activation, IJCNN2017](https://arxiv.org/abs/1703.04135)使用APC、状态机及输出历史设计激活，而不是仅凭AND实现sigmoid。FSM增益、有限流长度、自相关和三流AND依赖必须重新验证。',
'本次使用LUT+独立比较器是为了先分离尺度误差与状态机误差；不声称这是能耗最优。完整方法说明见qwen3/and_direct/MULTISCALE_ZH.md。','',
'成果与每seed参数/模型/数据/执行SHA见SUMMARY；原字节归档及成员SHA见RAW_INDEX。Issue173/PR174，未合并。']
(out/'REPORT_ZH.md').write_bytes(('\n'.join(lines)+'\n').encode())
print(json.dumps(dict(bf16=by['bf16']['ppl'],groups=[{k:v for k,v in g.items() if k not in ('first_layer_bin_hist',)} for g in groups]),ensure_ascii=False,indent=2))

import datetime,hashlib,json,pathlib,statistics
import argparse
_parser=argparse.ArgumentParser(description='Summarize authorized raw evidence without publishing activations or per-case long JSON')
_parser.add_argument('--evidence-dir',required=True,help='Contains submission32.json, raw/<execution_sha>/, optional confirmation evidence')
_parser.add_argument('--checkout',required=True,help='Target formal repository root')
_args=_parser.parse_args()
HERE=pathlib.Path(_args.evidence_dir).resolve()
W=pathlib.Path(_args.checkout).resolve()
OUT=W/'qwen/results/dual_range_20261018';OUT.mkdir(parents=True,exist_ok=True)
r=json.loads((HERE/'submission32.json').read_text(encoding='utf-8'));head=r['commit']
def write(name,value):
 (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
rows=[]; artifacts=[];references=[]
for tokens,suffix,collection in [(128,'','collection32.json'),(2048,'_prefix2048','collection32-confirm.json')]:
 root=HERE/'raw'/(head+suffix)
 if not root.exists():continue
 for path in sorted((root/'runs').glob('*.json')):
  v=json.loads(path.read_text(encoding='utf-8'));c=v['configuration']
  row=dict(prefix_tokens=tokens,**c,ppl=v['perplexity'],nll=v['nll'],scored_tokens=v['scored_tokens'],seconds=v['forward_seconds'],sha256=hashlib.sha256(path.read_bytes()).hexdigest())
  rows.append(row)
  if c['kind']=='baseline':references.append(row)
 if (HERE/collection).exists():
  c=json.loads((HERE/collection).read_text(encoding='utf-8'))
  artifacts.append(dict(prefix_tokens=tokens,server_output=c['server_output'],collected_at=c['collected_at'],files=c['files']))
groups=[]
keys=sorted({(v['prefix_tokens'],v.get('variant',''),v['kind'],v.get('scope',''),v.get('cycles',0)) for v in rows})
for tokens,variant,kind,scope,cycles in keys:
 selected=[v for v in rows if (v['prefix_tokens'],v.get('variant',''),v['kind'],v.get('scope',''),v.get('cycles',0))==(tokens,variant,kind,scope,cycles)]
 values=[v['ppl'] for v in selected if v['ppl'] is not None]
 groups.append(dict(prefix_tokens=tokens,variant=variant,kind=kind,scope=scope,cycles=cycles,completed=len(selected),ppl_mean=statistics.mean(values) if values else None,ppl_std=statistics.pstdev(values) if values else None))
write('SUMMARY.json',dict(execution_commit=head,rows=rows,groups=groups,expected_primary=39,expected_confirmation=10,primary_completed=sum(v['prefix_tokens']==128 for v in rows),confirmation_completed=sum(v['prefix_tokens']==2048 for v in rows),warning='All replacements are prefix PPL, not full WT2. bf16_full is repeated unchanged full-corpus reference.'))
write('ARTIFACT_INDEX.json',dict(issue=32,execution_commit=head,artifacts=artifacts,access='Original calibration and per-case long diagnostics stay in the authorized personal server project. Teacher activations were transient GPU tensors and were not persisted. No weights/text/activation arrays included in Git.',old_calibration_index='experiments/qwen_dual_iid_exact_20261018/CALIBRATION_ARTIFACTS.json'))
diag=json.loads((HERE/'raw'/head/'projection_diagnostics.json').read_text(encoding='utf-8'))
metrics=['input_mean_probability','weight_mean_probability','input_encoding_nmse','weight_reencoding_nmse','deterministic_projection_nmse','input_variance_nmse_T256','extra_weight_variance_nmse_T256','dual_total_mse_nmse_T256']
agg=[]
for projection in ('gate','up','down'):
 for variant in ('old','input','weight','both','both_idealW'):
  a=[v for v in diag['rows'] if v['projection']==projection and v['variant']==variant]
  agg.append(dict(projection=projection,variant=variant,layers=len(a),**{k:statistics.mean(v[k] for v in a) for k in metrics}))
write('PROJECTION_SUMMARY.json',dict(rows=agg,aggregation='Arithmetic mean across24 layers of per-layer normalized MSE; not global energy-weighted MSE',source=diag['source'],variance=diag['variance'],raw_sha256=hashlib.sha256((HERE/'raw'/head/'projection_diagnostics.json').read_bytes()).hexdigest()))
def find(tokens,variant,kind='dual',cycles=256,scope='all'):
 a=[v for v in groups if (v['prefix_tokens'],v['variant'],v['kind'],v['cycles'],v['scope'])==(tokens,variant,kind,cycles,scope)]
 if not a:return '待完成'
 v=a[0];return f"{v['ppl_mean']:.4f} ± {v['ppl_std']:.4f} ({v['completed']} seed)" if v['ppl_mean'] is not None else '指数溢出，见NLL'
lines=['# Qwen双随机独立范围缩放：结果与定位','',f'Issue32；执行源 `{head}`。全部24FFN，准确BF16 Attention；自然IID、A共享64、W逐连接独立、精确计数；无训练、OR或序列挑选。','',
'## 先看总体结果','',
'原未修改BF16完整WT2重新复现11.652735047455899（299077计分token），模型/语料/token/旧校准hash均核验。服务器kernel8/8含新旧legacy回归、共享计数及方差数学测试通过。','',
'下面所有替换PPL都是固定测试前缀，**不是完整WT2 PPL**。128token计分127个目标；2048token计分2047个目标。不同前缀只与各自BF16参考比较。','',
'| T256方案 | 128token PPL，3seed均值±总体标准差 |','|---|---:|',
f"| 旧输入/旧权重范围 | {find(128,'old')} |",f"| 只收紧输入范围 | {find(128,'input')} |",f"| 只收紧权重范围 | {find(128,'weight')} |",f"| 输入和权重都收紧 | {find(128,'both')} |",'']
for n in (128,2048):
 ref=[v for v in references if v['prefix_tokens']==n and v['name']=='bf16_prefix']
 if ref:lines.append(f"{n}token原BF16参考PPL：{ref[0]['ppl']:.6f}。")
lines+=['','| 更长2048token确认 | PPL |','|---|---:|',f"| both，无采样期望控制 | {find(2048,'both','mean')} |",f"| both，T128双随机 | {find(2048,'both',cycles=128)} |",f"| both，T256双随机 | {find(2048,'both')} |",'','## 更少采样与分支定位','', '| 双方收紧范围 | 128token PPL |','|---|---:|']
for t in (64,128,256,1024):lines.append(f"| 全FFN双随机，T{t} | {find(128,'both',cycles=t)} |")
lines += [f"| 仅gate/up采样，down期望，T256 | {find(128,'both',scope='gu')} |",f"| gate/up期望，仅down采样，T256 | {find(128,'both',scope='down')} |",f"| 同范围固定W、仅输入随机，T256 | {find(128,'both','fixed')} |",'','分支消融的期望路径仍使用该方案相同A8/权重编码；不是恢复原BF16投影。','',
'| 无采样量化控制 | 128token PPL |','|---|---:|']
for v in ('old','input','weight','both'):lines.append(f"| {v} | {find(128,v,'mean')} |")
lines+=['','## 局部误差为何改善','',
'在未修改teacher前128个train token中，取各层前16个MLP输入；down输入为teacher的BF16 SwiGLU输出。相同输入分别测四种编码的线性投影。下表为T256理论期望MSE/该层目标能量，再对24层等权平均；包含量化均值偏差、共享64输入方差和独立W新增方差。不是实测采样误差，也没有包含带噪SwiGLU及跨层传播。','',
'| 线性投影 | old | 仅输入 | 仅权重 | both |','|---|---:|---:|---:|---:|']
for proj in ('gate','up','down'):
 vals=[next(x for x in agg if x['projection']==proj and x['variant']==v)['dual_total_mse_nmse_T256']*100 for v in ('old','input','weight','both')]
 lines.append('| '+proj+' | '+' | '.join(f'{v:.3f}%' for v in vals)+' |')
lines+=['',
'旧down中，额外W采样方差约39.81%，输入共享采样方差约11.04%，均值偏差约0.648%；权重噪声仍占采样方差约78%。但收紧输入范围同时降低这两项，所以“修正输入最有效”不等于“权重噪声不重要”。','',
'teacher局部输入平均概率：gate/up从4.93%升到20.40%，down从0.761%升到16.588%；W从约14～16%升到约29～30%。双方修正后，down总NMSE约降低40倍。保留旧W8均值的row64_ideal与严格R8结果非常接近，新增权重概率舍入不是主要误差来源。','',
'## 范围实现与限制','',
'旧实现A和W本来已有独立尺度。问题是固定A范围来自8192个train token的最大包络，W范围来自64×64 tile，典型值只用到小部分概率范围。新A用每token/64通道absmax，新W用每输出行/64输入absmax。A/W均为独立8位概率q/256，最大幅度S=M×256/255；W从相同旧W8解码值重编码。','',
'输入动态absmax需要在线归约和尺度恢复，权重尺度元数据比旧tile多64倍。本次是数值定位，不是已经证明更省能的硬件方案；不能继承原固定范围的PPA。完整随机WT2尚未运行，也没有新训练、RTL/PT或TLM结果。','',
'源码见`experiments/qwen_dual_range_20261018/`；原始结果、完整命令/配置/环境/hash及授权位置见ARTIFACT_INDEX.json和work/jieruiz/32/提交回执。']
(OUT/'RESULTS_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'primary_completed':sum(v['prefix_tokens']==128 for v in rows),'confirmation_completed':sum(v['prefix_tokens']==2048 for v in rows),'published_files':[p.name for p in OUT.iterdir() if p.is_file()]}))

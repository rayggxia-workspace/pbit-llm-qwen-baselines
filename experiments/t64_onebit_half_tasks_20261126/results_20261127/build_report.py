"""Build tables from small sealed original JSONs; never run model inference."""
from pathlib import Path
import csv,hashlib,json

OWN=Path(__file__).resolve().parent
E=OWN/'evidence'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(name):
    raw=(E/name).read_bytes()
    assert sha(raw)==(E/Path(name).with_suffix('.sha256')).read_text().strip(),name
    return json.loads(raw)
def save(path,value):
    raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
    path.write_bytes(raw);path.with_suffix('.sha256').write_bytes((sha(raw)+'\n').encode())

s2=read('S2_SUMMARY.json');s4=read('S4_SUMMARY.json');audit=read('VERIFIED_RESULTS.json')
gate=read('S2_GATE.json');cpu=read('CPU_PREFLIGHT.json')
assert s2['status']==s4['status']==gate['status']=='completed' and audit['status']=='verified'
assert (s2['completed_parts'],s2['completed_groups'],cpu['tests'])==(100,8,18)
assert audit['S2_scored_pairs']==12040 and audit['S4_scored_pairs']==27090
rows=audit['rows'];assert len(rows)==8
for row in rows:
    actual=next(x for x in s2['groups'] if x['case']==row['case'] and x['task']==row['task'])
    assert actual['metrics']==row['S2']
    oldcase=dict(row['case'],id=row['case']['id'][3:])
    previous=next(x for x in s4['groups'] if x['case']==oldcase and x['task']==row['task'])
    assert previous['metrics']==row['S4']

summary=dict(status='verified',date='2026-11-27',source_commit=audit['S2_source_commit'],
    seed=101,model='Qwen3-4B frozen trained100M T64 / W8, native non_ffn',
    attention='accurate SDPA, unchanged',S2_parts=100,S2_groups=8,rows=rows,
    originals_sha256={p.name:sha(p.read_bytes()) for p in sorted(E.glob('*.json'))},
    main_conclusion='S2 improves prior pilot PPL, but task accuracy is mixed; high-budget results are close to S4',
    scope='Full PIQA1838 and ARC-C1172; single deployment seed; no S2 complete WT2 in this run')
save(OWN/'SUMMARY.json',summary)
with (OWN/'COMPARISON.csv').open('w',encoding='utf-8',newline='') as f:
    fields=['case','budget','x_policy','task','documents','S4_acc','S2_acc','delta_acc_pp','S4_acc_norm','S2_acc_norm','delta_acc_norm_pp']
    writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader()
    for r in rows:
        c=r['case'];writer.writerow(dict(case=c['id'],budget=f"{c['T_x']}/{c['T_and']}",
             x_policy='original_four' if c['policy']=='gu_onebit64' else 'dynamic64',task=r['task'],documents=r['documents'],
             S4_acc=r['S4']['acc,none'],S2_acc=r['S2']['acc,none'],delta_acc_pp=r['delta_pp']['acc,none'],
             S4_acc_norm=r['S4']['acc_norm,none'],S2_acc_norm=r['S2']['acc_norm,none'],delta_acc_norm_pp=r['delta_pp']['acc_norm,none']))

lines=['# S/S2与S/S4：完整任务准确率对照','',
 '2026-11-27，Issue225 / PR266。100/100分片、8/8完整组已完成；独立CPU62241逐题复核通过，GPU资源已释放。',
 '', 'S2并未在所有准确率指标上优于S4。16/32且x保持原四档时，两任务acc都提高；x也动态64共享时PIQA降低1.52个百分点。64/128时两者总体接近。此前S2的四项8窗PPL均改善，但不能据此推断任务准确率全面改善。',
 '', '## 1. 完整任务acc（百分比）','',
 '|GU/Wd采样|x尺度规则|PIQA S4|PIQA S2|变化/百分点|ARC-C S4|ARC-C S2|变化/百分点|',
 '|---|---|---:|---:|---:|---:|---:|---:|']
def pair(tx,policy):
    return [next(r for r in rows if r['case']['T_x']==tx and r['case']['policy']==policy and r['task']==task)
            for task in ['piqa','arc_challenge']]
for tx,ta in [(16,32),(64,128)]:
    for policy in ['gu_onebit64','all64_onebit']:
        a,b=pair(tx,policy)
        vals=[100*a['S4']['acc,none'],100*a['S2']['acc,none'],a['delta_pp']['acc,none'],
              100*b['S4']['acc,none'],100*b['S2']['acc,none'],b['delta_pp']['acc,none']]
        lines.append('|'+f'{tx}/{ta}|'+('原四档' if policy=='gu_onebit64' else '动态64共享')+'|'+'|'.join(f'{v:+.2f}' if i in (2,5) else f'{v:.2f}' for i,v in enumerate(vals))+'|')
lines+=['','g/u均为64项共享动态二次幂基准、每元素1bit选择S或小档；S4小档与门限为S/4，S2为S/2。两种x规则分别配对，不混算。',
 '', '## 2. acc_norm（百分比）','',
 '|GU/Wd采样|x尺度规则|PIQA S4|PIQA S2|ARC-C S4|ARC-C S2|','|---|---|---:|---:|---:|---:|']
for tx,ta in [(16,32),(64,128)]:
    for policy in ['gu_onebit64','all64_onebit']:
        a,b=pair(tx,policy)
        vals=[100*a['S4']['acc_norm,none'],100*a['S2']['acc_norm,none'],100*b['S4']['acc_norm,none'],100*b['S2']['acc_norm,none']]
        lines.append('|'+f'{tx}/{ta}|'+('原四档' if policy=='gu_onebit64' else '动态64共享')+'|'+'|'.join(f'{v:.2f}' for v in vals)+'|')
lines+=['', 'PIQA的acc_norm四项均提高；ARC-C低预算提高、高预算降低约0.60～0.68个百分点。保留两种指标，不只选择改善项。',
 '', '## 3. 配置、对照和复核','',
 '- 模型：冻结trained100M T64/W8及原non_ffn；准确SDPA Attention，未启用QK筛选/概率Attention，无新训练。主比较为相同权重、预算、任务与请求顺序的S4/S2。',
 '- PIQA完整validation1838题、ARC-Challenge完整test1172题；官方lm-eval0.4.8零样本、seed101，不套聊天模板、不截断。所有题干和答案位置均经36层所选FFN；单部署seed不是多训练seed结果。',
 '- 新CPU62236十八项PASS；GPU Gate62237 COMPLETED/0:0，7分51秒。完整原BF16 WT2为11.5364289819，292窗/299077目标；模型、数据、harness身份核对、S4 logits和逐答案分数回放及S2重复一致通过。',
 '- 正式worker62238_0/1均COMPLETED/0:0，分别2:06:32和2:07:35；合计4.2353 GPU小时，不含独立Gate。CPU汇总62239完成，100/100片与8/8组齐、缺项和失败为空。',
 '- 独立CPU62241在原共享存储重新读取650份封存JSON，重算S2的12040与S4的27090个配置×题目计分；校验原文档SHA、输入ledger、36层覆盖、代码/模型/配置身份，汇总完全一致。唯一测试题3010道，配置×题目记录不是独立文本样本量。',
 '- 新推理源码354bef257affa393d5677c04c9d71004e9d88286、35文件快照冻结；独立审计脚本在原执行目录之外，未修改原快照。audit源码SHA与原件索引在VERIFIED_RESULTS.json。',
 '- 本批没有S2完整WT2；此前PPL只为8个分散窗口/9215目标。未改变RTL/TLM默认、64bit状态或新增PPA。PR266不自动合并。',
 '', '原字节小归档：project_archives/scale_results225_20261126/S2_TASKS_AND_AUDIT_20261127.tar.gz，SHA-256 6a3dc66d3768b7be7d540f5f13a159bd2247044f2294fe6723dac84fa3e78bca。大逐题输出和模型留原共享存储；准确恢复见work/rayggxia/225/onebit_half_tasks_20261126/HANDOFF.md。',
 '', '重建汇总：python build_report.py；只读取evidence中的封存小型JSON，不运行模型。']
(OWN/'REPORT_ZH.md').write_bytes(('\n'.join(lines)+'\n').encode())
index={p.relative_to(OWN).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(OWN.rglob('*')) if p.is_file() and p.name not in ['FILE_INDEX.json','FILE_INDEX.sha256']}
save(OWN/'FILE_INDEX.json',index)
print(json.dumps(dict(status='verified',rows=len(rows),indexed_files=len(index))))

"""Save a bounded operational ETA; never label projected completion actual."""
from pathlib import Path
import json,hashlib,datetime
H=Path(__file__).resolve().parent;ROOT=H.parents[3];WS=ROOT.parents[1]
load=lambda p:json.loads(Path(p).read_bytes())
x=load(H/'ETA_OBSERVATION.json')
cases=[]
for c in x['cases']:
    p=c['pilot'];cases.append(dict(model=c['model'],scheme=c['scheme'],seed=c.get('seed'),job_id=c['job_id'],
        completed_layers=c['complete_layers'],target_layers=c['target_layers'],
        elapsed_seconds=c['elapsed_seconds'],recent_median_layer_seconds=c['median_layer_seconds'],
        first_layer_seconds=c['first_layer_wall_seconds'],pilot_layer_seconds=p['last_body_wall_seconds'],
        pilot_head_seconds=p['observed_head_seconds'],
        last_progress=c['last_progress'],exit_code=c['exit_code']))
summary=dict(status='OPERATIONAL_ETA_NOT_COMPLETION',observed_UTC=x['observed_UTC'],
    observed_Beijing='2026-11-10 14:37',remaining_wall_hours_by_model={'qwen3_4b':[5,7],'llama32_3b':[4,6],'deepseek_7b':[10,13]},
    whole_batch_expected_Beijing='2026-11-11 00:00–04:00',
    assumptions=['rough range from actual latestcompletedlayer median and remaininglayers',
        'DeepSeekBF16 only gate throughput available;largest uncertainty',
        'fullhead added separately;completedQwen reference4303–4938s and gatehead sensitivity',
        'no majorCPUloadchange,failure,restart;notguaranteeddeadline'],
    concurrency=dict(user_preference='noartificialparallelcap',Qwen_ArrayTaskThrottle=0,
        update=x['array_unlimited_update'],cross_model_full_jobs='12individualjobs;noartificialcap',
        dependencies='keep native validation afterok gates',no_execution_source_changed=True),
    cases=cases)
(H/'ETA_SUMMARY.json').write_bytes((json.dumps(summary,indent=2)+'\n').encode())
text='''# 28nm TLM运行完成时间估计

2026-11-10北京时间14:37读取；这是服务器CPU仿真的剩余墙钟估计，不是已完成结果或模型token延迟。

|批次|预计还需|预计完成，北京时间|
|---|---:|---|
|Qwen三组数字基线|5–7小时|11月10日19:30–21:30|
|Llama概率三seed＋三数字基线|4–6小时|11月10日18:30–20:30|
|DeepSeek概率三seed＋三数字基线|10–13小时|11月11日00:30–03:30|

整体按11月11日凌晨0–4点安排，取最慢DeepSeek BF16组，不把并行批次的时长相加。粗区间随实际吞吐更新，不是承诺截止时间。

依据：Qwen W8screen已14/36层、约241秒/层，W8dense12/36、306秒/层，BF16 5/36、486秒/层。Llama多数4–5/28层，概率277–333秒/层、W8约259–290、BF16约494。DeepSeek多数仅1/30层，约600–790秒；BF16当时门禁刚完成、约1103秒/层，故其整批估计不确定性更大。完整lm_head另加预算，已完成Qwen参考约4303–4938秒，不按384head门禁直接当完整head。

用户明确后续不设人为并行上限。Qwen38650228已将ArrayTaskThrottle从3改为0（取消上限），新跨模型12项本来就是独立提交，无两项上限。依赖原生门禁的afterok保留，集群自身资源/QOS仍由调度器处理。没有重启/重交或修改冻结执行源。

观测原件ETA_OBSERVATION.json仅本地；公开轻量分项ETA_SUMMARY.json。初次状态脚本遇登录节点Python3.6缺fromisoformat，后用strptime重读成功；调度修改为幂等元数据更新，未引起任何实验重跑。
'''
(H/'ETA_ZH.md').write_bytes(text.encode())
note='''## 2026-11-10 用户要求仿真不设人为并行上限；按实际吞吐更新ETA

Issue225/PR249。用户明确本项目CPU TLM后续不人为设置%2等并行上限。已将Qwen数字38650228的ArrayTaskThrottle=0，新两模型12完整任务原本独立无人工上限；保留原生验证afterok依赖，不重启/改源。EDA资源/QOS为实际调度约束，不声称不存在。

北京时间14:37观测：Qwen数字完成5/12/14层（目标36），Llama多为4–5/28，DeepSeek多为1/30；按近期实际层吞吐＋单列完整head预算，Qwen尚5–7h、Llama4–6h、DeepSeek10–13h。整批约11月11日0–4点，最慢DeepSeekBF16，属于粗ETA，非完成回执；负载/后续吞吐/失败会改变。恢复本任务cross28_20261110/ETA_ZH.md、ETA_SUMMARY.json和原始ETA_OBSERVATION。此次无新仿真/重交/取消任务。

---

'''
for p in (ROOT/'progress/rayggxia/STATUS.md',H/'HANDOFF.md'):
    old=p.read_bytes()
    if note.encode() not in old:p.write_bytes(note.encode()+old)
mem=WS/'PROJECT_MEMORY_ZH.md';canonical=WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md'
old=mem.read_bytes();assert old==canonical.read_bytes()
if note.encode() not in old:
    canonical.write_bytes(note.encode()+old);mem.write_bytes(note.encode()+old)
paths=['work/rayggxia/225/cross28_20261110/'+n for n in ('estimate.py','record_eta.py','ETA_SUMMARY.json','ETA_ZH.md','HANDOFF.md')]
paths+=['progress/rayggxia/STATUS.md']
(H/'ETA_PUBLIC_FILES.json').write_bytes((json.dumps([dict(path=n,content=(ROOT/n).read_bytes().decode('utf8'),
    sha256=hashlib.sha256((ROOT/n).read_bytes()).hexdigest()) for n in paths],ensure_ascii=False)+'\n').encode())
print(json.dumps(dict(files=len(paths),whole_batch_ETA=summary['whole_batch_expected_Beijing'],not_completed=True)))

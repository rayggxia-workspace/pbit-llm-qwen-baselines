"""Consume new ownerPPA and record the PPL-matched selection;no runtimepatch."""
from pathlib import Path
import hashlib,json,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PROJECT=ROOT.parents[1]
OUT=ROOT/'architecture_tlm/module_handoff/attention_score_front_compare_20261108'
OWNER=PROJECT/'architecture_tlm/module_handoff/attention_score_front_ppa_20261108'
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode())
old={p.name:p.read_bytes() for p in OUT.iterdir() if p.is_file()}
for n,b in old.items():assert b==(PROJECT/OUT.relative_to(ROOT)/n).read_bytes()
raw=(OWNER/'TLM_PROFILE.json').read_bytes()
assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()=='002a2499c65b5558e128e0acf9884fd1f9d1f8f0'
profile=json.loads(raw);table=[]
for clock in ('100','250'):
 for kind in ('s12_max_gap','fp32_max_gap'):
  c=profile[clock][kind]
  assert c['ready'] and c['actions_already_in_gross'] and not c['integrated_sampler_replacement_ready']
  assert all(v>=0 for v in c['slacks_ns'].values())
  assert abs(c['area55_mm2']-c['raw_area_um2']*.81/1e6)<1e-12
  assert abs(c['gross_query_nJ']-c['active_average_mW']*c['query_cycles']*(1000/int(clock))/1000)<1e-9
  assert c['input_score_read_words16']==(32 if kind=='s12_max_gap' else 64)
  table.append(dict(clock_MHz=int(clock),frontend_kind=kind,area55_mm2=c['area55_mm2'],gross_query_nJ=c['gross_query_nJ'],
    cycles=c['query_cycles'],input_read_bytes=c['input_score_read_bytes'],PVT=c['PVT']))
facts=load(OUT/'AUDIT_FACTS.json')
assert 'current_measured_frontends' not in facts
facts['historical_before_new_PPA']={k:facts.pop(k) for k in ('old_S12','new_FP32')}
facts.update(status='UPDATED_WITH_OWNER_FRONTEND_PPA_NO_NEW_CONSUMER_SIMULATION',
 producer_commit='55e06025f871278191dbb33df71497e79f932c16',current_measured_frontends=profile,
 PPL_matched_frontend_kind='s12_max_gap',standalone_cards_ready=True,integrated_sampler_replacement_ready=False,
 current_TLM_runtime_changed=False,frozen_jobs_changed=False,
 selection_scope='PPL-matched consumer contract,not claim of whole-model bittrueverification or integratedPPAclosure')
save(OUT/'AUDIT_FACTS.json',facts)
index=load(OUT/'SOURCE_INDEX.json')['sources']
for n in ('TLM_PROFILE.json','PPA_SUMMARY.json','HANDOFF_ZH.md','SHA_INDEX.json'):
 p=OWNER/n;index['latest_PPA_'+n]=dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
for key,p in {
 'latest_provider_interface':PROJECT/'architecture_tlm/attention_score_front_20261108/profile.py',
 'full_WT2_selection':PROJECT/'tmp/attention-compare-issue198-20261027/experiments/attention_full_sweep_20261106/methods.py',
 'full_WT2_numeric':PROJECT/'tmp/attention-compare-issue198-20261027/experiments/attention_gap_accuracy_20261102/methods.py'
}.items():index[key]=dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
save(OUT/'SOURCE_INDEX.json',dict(sources=index,raw_reports_or_owner_source_copied=False))
new='''# 最新更新：主线应匹配A（S12先量化），已有A/B实测价卡

2026-11-08，Issue225消费Attention Issue198的新交接。以下优先于后面的历史审计；“FP32仅有宏价”已被本次新独立PPA更新，不能再沿用为当前状态。

**用户指出正确：现有主要完整PPL采用FP32分数先RNE饱和为S12/F4，再求整数最大值和差，最后clip为U8/F4并查P8。对应新交接的A：`s12_max_gap`，不是B：`fp32_max_gap`。** 全WT2扫描的Patch明确选择`ising64_gap_s12_p8`；联合T64-FFN完整WT2也使用这一数制。两种前端均做电路测量只是对照，不代表PPL改成了B。

## 新的独立前端价格

|版本|路径|面积mm²|gross nJ/128分数query|无停顿拍数|分数SRAM输入读|
|---|---|---:|---:|---:|---:|
|100MHz SS|A S12|0.01646636|0.176562|65|512B|
|100MHz SS|B FP32差|0.01813694|0.480859|71|1024B|
|250MHz TT|A S12|0.01902807|0.302215|67|512B|
|250MHz TT|B FP32差|0.02125239|0.836385|73|1024B|

各频率内相同接口配对：A面积比B小约9.21%/10.47%，gross查询能量低约63.28%/63.87%，少6拍，输入分数读减半。只适用于这批合成激励和独立前端；A有部分S12饱和，倍率不能当真实Qwen或整机常数。面积已乘0.81一次；100SS与250TT不能当纯频率扫描。表中不含外部SRAM能量、LUT/P8保持、随机源/比较器/仲裁或V/PV。

新A已加入mask/异常规则；250MHz的A/B都计入同样输入/输出FIFO。不能用旧11月4日0.01505mm²/0.16629nJ去和新版B比较。新版B是六级专用差值/双RNE通路，已经有RTL/DC/STA/PT，不能再用四个通用FP32 ADD代理作它的当前价卡。边界与告警仍是前布局范围。

## 与当前PPL一致的接入方向

1. 消费者显式选择`frontend_kind='s12_max_gap'`。新库的`forward()`/`card()`缺省仍为B，主线不能省略参数；`quote()`也应明确传A。该库缺省不改变冻结PPL执行配置。
2. **优先复用原采样器的S12后端。** 旧`ab_both`已经从4路S12开始，包含scores寄存器、max、13bit gap/clip及LUT装载。最自然的匹配路径为：QK FP32→4路FP32/S12转换与必要握手→复用原S12存储/max/gap/LUT→P8/R8/赢家/V。独立A是完整前端参考，不应再整体叠加在原采样器前。
3. 如统一改成gap输入接口，则新A处理到U8，原采样器需移除/旁路原scores/max/gap并保留共同LUT、P8、随机与赢家/V；不能一边保留旧全块、一边加新全块。
4. 全链净价尚未闭合：提供方明确`integrated_sampler_replacement_ready=false`。不能直接从旧完整sampler扣整个A，A还含原sampler没有的FP32转换/FIFO/控制。需要转换/握手的增量价卡，或集成gap接口后的去重实测/严格分窗，再更新完整TLM。

**本次将后续接入依据明确为A，更新文档和机读事实；未修改现行TLM运行源码或默认，也未改任何冻结作业。** 现有FP32前端宏任务结果保持原标签；后续不要将其成本与A的完整PPL拼成同一已验收配置。B保留为对照候选，完整PPL/位真边界分别说明。

新交接入口：`architecture_tlm/module_handoff/attention_score_front_ppa_20261108/`，生产提交`55e06025f871278191dbb33df71497e79f932c16`。消费端核对公开profile Git blob、四张价卡的STA/面积/能量单位/输入读，未重复生产方的原始96artifact全审计或35921对电路测试。准确路径与SHA见SOURCE_INDEX，当前数据见AUDIT_FACTS。

---

## 历史审计原文（新PPA到达前，保留追溯）

'''
(OUT/'HANDOFF_ZH.md').write_bytes(new.encode()+old['HANDOFF_ZH.md'])
save(OUT/'VALIDATION.json',dict(status='PASS_LATEST_PROFILE_AND_CONSUMER_SELECTION',sources_verified=len(index),
 public_profile_blob_verified='002a2499c65b5558e128e0acf9884fd1f9d1f8f0',
 selected_frontend_kind='s12_max_gap',qualified_cards_checked=4,
 checks=['nonnegative_data_and_gate_slack','rawarea_times0.81_once','gross_mW_times_service_ns_equalsnJ','A32_vsB64_input_words',
 'full_WT2_s12_dispatch','no_integrated_replacement_claim'],new_consumer_PPA_or_PPL_run=False,no_defaults_changed=True))
for p in OUT.iterdir():
 target=PROJECT/p.relative_to(ROOT);assert target.read_bytes()==old[p.name];target.write_bytes(p.read_bytes())
status=ROOT/'progress/rayggxia/STATUS.md'
status.write_bytes(('''## 2026-11-08 Issue225：新前端PPA已核，当前PPL对应A

已读取198/199新交接55e06025，公开profile blob及四张价卡单位/STA/读字检查通过。当前完整PPL明确S12/F4先量化→整数max-gap→U8/P8，后续接入依据选A=s12_max_gap，B仅对照；新版A100/250面积.016466/.019028mm²、gross.176562/.302215nJ、65/67拍。旧审计“B仅宏价”已更新为新实测，旧原文保留。

旧ab_both已有S12 scores/max/gap，优先复用其后端并接FP32/S12转换；不得整块加A或扣A。提供方全链replacement_ready=false，净价待去重；本轮仅消费核验和文档，不改runtime/default/冻结作业，无新TLM/PPL/PT。公开及交接见score_front_audit_20261108/LATEST_PPA_PUBLICATION.json；PR249不合并，Projects待同步。

''').encode()+status.read_bytes())
handoff=HERE/'HANDOFF.md';handoff.write_bytes(('''## 新PPA消费补充（2026-11-08）

当前PPL明确对应A=s12_max_gap，后续主线应显式传A；提供方forward/card默认B不是PPL配置。新版四张独立前端价卡已核，旧“B仅宏价”历史结论已更新；完整采样器去重尚未ready，不改冻结运行。正式HANDOFF/AUDIT_FACTS/SOURCE_INDEX/VALIDATION同步；不重复producer测试或原始归档全审计。

''').encode()+handoff.read_bytes())
canonical=PROJECT/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';mirror=PROJECT/'PROJECT_MEMORY_ZH.md'
b=canonical.read_bytes();assert b==mirror.read_bytes()
note='''## 2026-11-08：新A/B前端价卡消费，PPL对应A

用户再次指出完整PPL先S12再max-gap，已核全WT2 dispatch为ising64_gap_s12_p8及联合243同数制。消费225/PR249更新score_front_compare交接顶部与机读事实：后续主线依据A=s12_max_gap，新库forward/card缺省B不能省参。生产199提交55e06025，公开profile blob及4卡面积/能量/STA/读字核验；A100/250 .016466/.019028mm²、.176562/.302215nJ、65/67拍，新B有真实专用流水PPA，撤销“仍只有宏价”的当前说法，旧审计留历史。无新消费者PPL/PT/TLM。

旧ab_both本有S12 scores/max/gap；优先复用旧后端加FP32/S12转换/握手增量，或完整改gap接口去重，不能整块新A与旧sampler叠加或减整个A。producer integrated_sampler_replacement_ready=false，故本轮仅明确A选择及文档，不擅自写全链闭合/修改default/runtime/冻结作业。发布看score_front_audit_20261108/LATEST_PPA_PUBLICATION.json；PR249不合并，Projects待同步。

---

'''.encode();assert canonical.read_bytes()==b and mirror.read_bytes()==b
canonical.write_bytes(note+b);mirror.write_bytes(note+b)
files=list(OUT.iterdir())+[status,handoff,HERE/'apply_latest_ppa.py']
items=[dict(path=p.relative_to(ROOT).as_posix(),content=p.read_bytes().decode(),sha256=sha(p)) for p in files]
save(HERE/'LATEST_PUBLIC_FILES.json',items)
subprocess.run(['git','-c','core.autocrlf=false','add','--sparse','--']+[x['path'] for x in items],cwd=ROOT,check=True)
for x in items:assert hashlib.sha256(subprocess.check_output(['git','show',':'+x['path']],cwd=ROOT)).hexdigest()==x['sha256']
subprocess.run(['git','-c','core.whitespace=cr-at-eol,-blank-at-eof','diff','--cached','--check'],cwd=ROOT,check=True)
print(json.dumps(dict(files=len(items),cards_checked=4,PPL_matched_kind='s12_max_gap',runtime_changed=False)))

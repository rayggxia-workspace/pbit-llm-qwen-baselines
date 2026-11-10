from pathlib import Path
import ast,hashlib,json,statistics
H=Path(__file__).resolve().parent;ROOT=H.parents[3];WS=ROOT.parents[1]
load=lambda p:json.loads(Path(p).read_bytes())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
audit=load(H/'AUDIT_REMOTE.json');done=[c for c in audit['cases'] if c['status']=='completed_seal_verified']
running=[c for c in audit['cases'] if c['status']!='completed_seal_verified']
assert len(done)==13 and len(running)==2
states={}
for n in ('digital250_20261110','cross28_20261110'):
    for row in load(H.parent/n/'STATUS.json')['accounting']:
        z=row.split('|')
        if '.' not in z[0]:states[z[0]]=(z[1],z[2])
for c in done:assert states[c['job_id']]==('COMPLETED','0:0'),c['job_id']
assert not any(c['status']=='failed' for c in audit['cases'])
refpath=ROOT/'architecture_tlm/process_28nm/250MHz/FULL_RESULTS_20261110.json'
ref=load(refpath);assert ref['status']=='THREE_SEEDS_FULL_NATIVE_COMPLETED_VERIFIED'
for c in ref['records']:
    for name,info in c['files'].items():assert sha(info['local'])==info['sha256']
def aggregate(group):
    split=lambda k:statistics.mean(c['head_split']['without_lm_head_stage'][k] for c in group)
    return dict(model=group[0]['model'],scheme=group[0]['scheme'],completed_seeds=len(group),
        time_ms=statistics.mean(c['time_ms'] for c in group),core_mJ=statistics.mean(c['core_mJ'] for c in group),
        total_4pJ_mJ=statistics.mean(c['total_mJ_by_pJbit']['4.0'] for c in group),
        area_mm2=group[0]['area_mm2'],without_lm_head_time_ms=split('time_ms'),
        without_lm_head_core_mJ=split('core_energy_mJ'),
        without_lm_head_total_4pJ_mJ=statistics.mean(c['head_split']['without_lm_head_stage']['total_mJ_by_external_pJbit']['4.0'] for c in group))
rows=[dict(model='qwen3_4b',scheme='SC_ising',completed_seeds=3,time_ms=ref['time_ms'],
    core_mJ=ref['core_mJ'],total_4pJ_mJ=ref['total_4pJ_mJ'],area_mm2=ref['area_mm2'],
    without_lm_head_time_ms=ref['without_lm_head']['time_ms'],
    without_lm_head_core_mJ=ref['without_lm_head']['core_energy_mJ'],
    without_lm_head_total_4pJ_mJ=ref['without_lm_head_total_4pJ_mJ'],prior_batch_reference=True)]
for model in ('qwen3_4b','llama32_3b','deepseek_7b'):
    for scheme in ('SC_ising','BF16_dense','W8_dense','W8_screen'):
        g=[c for c in done if c['model']==model and c['scheme']==scheme]
        if not g:continue
        if scheme=='SC_ising' and len(g)<3:continue # preserve2/3 seeds,do not present final average
        rows.append(aggregate(g))
ratios={}
for model in ('qwen3_4b','llama32_3b'):
    s=next(c for c in rows if c['model']==model and c['scheme']=='SC_ising')
    d=next(c for c in rows if c['model']==model and c['scheme']=='W8_screen')
    ratios[model]=dict(speedup_vs_W8screen=d['time_ms']/s['time_ms'],
        core_energy_saved_pct=100*(1-s['core_mJ']/d['core_mJ']),
        total_4pJ_saved_pct=100*(1-s['total_4pJ_mJ']/d['total_4pJ_mJ']),
        SC_area_extra_pct=100*(s['area_mm2']/d['area_mm2']-1))
result=dict(status='PARTIAL_BATCH13_OF15_SEAL_AND_SLURM_VERIFIED',observed_UTC=audit['observed_UTC'],
    count_scope='newQwen3digital+Llama6+DeepSeek6;priorQwen3SC separate reference',
    completed=13,total=15,failed=0,running=running,rows=rows,ratios=ratios,
    completed_cases=done,prior_Qwen_SC_reference=dict(path=str(refpath),sha256=sha(refpath)),
    assumptions='conditional28nm250B1N2048;nativeLPDDRderived8533;external4pJ/bit;notPPLorphysicalchip',
    ETA_remaining=dict(DeepSeek_SC_seed17='about1hour;lm_headinprogress',
        DeepSeek_BF16='about2to3hours;25of30layerscomplete',whole_batch='2026-11-11 around03:00,allowuntil04:00'))
D=ROOT/'architecture_tlm/process_28nm/results_20261111';D.mkdir(exist_ok=True)
(D/'SUMMARY.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
names={'SC_ising':'概率版（3seed均值）','BF16_dense':'BF16稠密','W8_dense':'W8稠密','W8_screen':'W8＋SparQ完整PV'}
text='''# 28nm250完整TLM任务进度与已完成结果

2026-11-11北京时间00:42核验。昨天新增15项完整case中13项Slurm COMPLETED/0:0，EXIT、SEAL所列原件SHA、全层/完整head/代码配置SHA及能量加和均通过；没有失败。Qwen概率三seed是此前已完成的独立参考，不重复计入15项。

|批次|完整完成数|当前状态|
|---|---:|---|
|Qwen三数字基线|3/3|已核验|
|Llama概率三seed＋三数字|6/6|已核验|
|DeepSeek概率三seed＋三数字|4/6|SCseed17处于lm_head；BF16正在第26/30层|

剩余两项：38650676概率seed17已完成30层，head已运行约48分钟；按另两seed约104–109分钟head墙钟，预计还约1小时。38650679 BF16已完成25层，近5层约1490–1569秒/层；加独立head预算后预计还2–3小时。整体约凌晨3点，保留到4点的浮动。属于吞吐推算，不是完成承诺；不重交或修改健康冻结任务。
'''
for model,label in [('qwen3_4b','Qwen3-4B'),('llama32_3b','Llama-3.2-3B-Instruct'),('deepseek_7b','DeepSeek-LLM-7B-Chat（未收齐）')]:
    text+='\n## '+label+'\n\n|方案|含head时间ms/token|片上mJ/token|含外存4pJ情景mJ/token|覆盖面积mm²|\n|---|---:|---:|---:|---:|\n'
    for c in rows:
        if c['model']==model:text+=f"|{names[c['scheme']]}|{c['time_ms']:.3f}|{c['core_mJ']:.3f}|{c['total_4pJ_mJ']:.3f}|{c['area_mm2']:.3f}|\n"
    if model=='deepseek_7b':text+='\n概率版仅2/3seed完成，BF16未完成；不把两seed均值当最终三seed结果。逐seed已完成值和原件SHA保留SUMMARY.json。\n'
text+='\n## 扣除lm_head阶段\n\n同一次执行在final_norm处取前缀，硬件常驻面积不减；不等同独立冷启动删除head。\n\n|模型/方案|不含head时间ms/token|片上mJ/token|含外存4pJ情景mJ/token|\n|---|---:|---:|---:|\n'
for c in rows:text+=f"|{c['model']}/{c['scheme']}|{c['without_lm_head_time_ms']:.3f}|{c['without_lm_head_core_mJ']:.3f}|{c['without_lm_head_total_4pJ_mJ']:.3f}|\n"
text+='''
## 解释边界

同28nmTT0.9V25C/250MHz、B1/2K、832KiB/178宏、同LPDDR/DMA。数字三方案近等总面积，较概率版低0.47%–1.70%，没有宣称严格等面积或最优数字ASIC。W8沿既有混合数制，非全定点数字CIM。外存是4pJ/bit情景，6.6/8敏感性仍在原BUDGET；共享资源和gross/idle不重复计费。物理4Q槽、无效头门控、代表性地址、scalar/转换/平台宏及PHY等边界沿冻结合同，不是新PPL或完整芯片实测。

本机原始状态和独立校验：work/rayggxia/225/tlm_status_20261111/；远端源/输出路径、源码/配置和原件SHA见SUMMARY。只读核验，无新Slurm任务、GPU、训练或RTL/PT；并行上限保持取消。任务尚未全部结束，PR未合并。
'''
(D/'REPORT_ZH.md').write_bytes(text.encode())
note='''## 2026-11-11 TLM进度：新增15项已封存核验13项，余DeepSeek两项

Issue225/PR249，00:42北京实核。Qwen数字3/3、Llama6/6、DeepSeek4/6；13项均COMPLETED0:0、EXIT0、SEAL原件/源/配置SHA、真实全层/head及能量行加和通过，无失败。Qwen概率3seed为此前参考，不重复计15。QwenBF16/W8dense/W8screen含head111.119648/94.998940/85.450204ms；Qwen概率51.132604ms。Llama三seed概率43.929332ms，BF16/W8dense/W8screen86.102848/74.136052/66.688448ms。面积/片上与外存能量、扣head见process_28nm/results_20261111/REPORT_ZH.md、SUMMARY.json。

DeepSeek38650676概率seed17完成30层，正跑lm_head，余约1h；另两seed已完成但不当最终三seed平均。38650679 BF16已25/30层、正在第26层，预计余2–3h，整批约凌晨3点、保留到4点浮动。没有重启/重交/改冻结源，CPU并行上限保持取消。新报告本地完成，发布看本work/PUBLICATION；PR待审未合并，Projects待同步。

---

'''
(H/'MEMORY_NOTE.txt').write_bytes(note.encode())
for p in (ROOT/'progress/rayggxia/STATUS.md',ROOT/'work/rayggxia/225/cross28_20261110/HANDOFF.md',ROOT/'architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md'):
    old=p.read_bytes()
    if note.encode() not in old:p.write_bytes(note.encode()+old)
mem=WS/'PROJECT_MEMORY_ZH.md';canonical=WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md'
old=mem.read_bytes();assert canonical.read_bytes()==old
if note.encode() not in old:
    canonical.write_bytes(note.encode()+old);mem.write_bytes(note.encode()+old)
paths=['architecture_tlm/process_28nm/results_20261111/'+n for n in ('REPORT_ZH.md','SUMMARY.json')]
paths+=['work/rayggxia/225/tlm_status_20261111/'+n for n in ('inspect_results.py','head_progress.py','HEAD_RUNTIME.json','AUDIT_REMOTE.json','report.py','MEMORY_NOTE.txt')]
paths+=['progress/rayggxia/STATUS.md','work/rayggxia/225/cross28_20261110/HANDOFF.md','architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md']
for n in paths:
    p=ROOT/n
    if p.suffix=='.py':ast.parse(p.read_text(),feature_version=(3,9))
    if p.suffix=='.json':load(p)
    if n.startswith('architecture_tlm/'):
        dest=WS/n;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes())
(H/'PUBLIC_FILES.json').write_bytes((json.dumps([dict(path=n,content=(ROOT/n).read_bytes().decode('utf8'),sha256=sha(ROOT/n)) for n in paths],ensure_ascii=False)+'\n').encode())
print(json.dumps(dict(status='13_OF15_VERIFIED',rows=rows,ratios=ratios,public_files=len(paths))))

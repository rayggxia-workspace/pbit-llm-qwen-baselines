from pathlib import Path
import ast,hashlib,json
H=Path(__file__).resolve().parent;ROOT=H.parents[3];WS=ROOT.parents[1];P=ROOT/'architecture_tlm/process_28nm'
load=lambda p:json.loads(Path(p).read_bytes())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump=lambda p,x:p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode())
plan=load(H/'UPLOAD_PLAN.json');sub=load(H/'SUBMISSION.json');package=Path(plan['package']);mf=load(package/'FROZEN_MANIFEST.json')
for n,v in mf['files_sha256'].items():assert sha(package/n)==v
assert sha(plan['local'])==plan['sha256']
cases=[]
for scheme in mf['schemes']:
    d=H/('gate2_'+scheme);seal=load(d/'SEAL.json');r=load(d/'RESULT.json');b=load(d/'BUDGET.json')
    assert seal['status']=='completed' and load(d/'VALIDATION.json')['status']=='PASS'
    for n,v in seal['files_sha256'].items():assert sha(d/n)==v
    assert r['code_sha256']=={p.name:sha(p) for p in (P/'digital250_20261110').glob('*.py')}
    assert r['scope']=='layer_or_partial' and r['layers']==1 and r['head_probe_rows']==384
    cases.append(dict(scheme=scheme,path=str(d),seal_sha256=sha(d/'SEAL.json'),time_ms=r['time_ms'],
        wall_seconds=r['wall_seconds'],area_mm2=b['conditional_subsystem_area_mm2'],
        core_mJ=b['conditional_subsystem_energy_mJ'],checks=load(d/'VALIDATION.json'),
        FFN_actions=b['FFN_actions'],Attention_actions=b['Attention_actions']))
validation=dict(status='PASS',cases=cases,scope='threeanalytic1layer384headchecks;notfullorSTA',
    frozen_manifest_sha256=sha(package/'FROZEN_MANIFEST.json'),archive_sha256=plan['sha256'],
    preserved_early_failures=['construct_:namespace module search path;fixed restoration after legacybootstrap',
        'construct2_:NamespacePath.insert unsupported;fixed explicitpathlist',
        'construct3_:inspectgeneratedretimefunction;restored identical4cycleoriginalbeforeadaptation'],
    final_change='fourQ feature-top service/actions corrected;allthreefinalchecks rerun',
    source_files=mf['files_sha256'])
dump(H/'VALIDATION.json',validation);dump(P/'digital250_20261110/VALIDATION.json',validation)
note='''## 2026-11-10｜28nm250概率完整收齐；55nm式三数字基线已提交

Issue225/PR249，rayggxia。用户本对话确认28nm主数字对照沿55nm的BF16_dense/W8_dense/W8_screen，新增共享尺度P8/W8数字CIM只作补充；此前“CIM唯一主对照”为先前范围，不替代本次最新决定。

概率数组38644764三seed已全部COMPLETED0:0，原件SEAL/SHA、36层/完整151936head、帧/采样/字节与闭合账本通过。完整均值51.132604ms/token，扣head43.594377ms；片上15.267553mJ，外存4pJ情景总188.432048mJ，覆盖6.480303mm²。旧46.01856ms为局部外推，现用完整原生结果。原件project_archives/tlm28p250_full225_20261110，正式process_28nm/250MHz/FULL_RESULTS_20261110_ZH.md及JSON。

数字三组已接28nm实测原语与显式宏价，同832KiB/178宏、同LPDDR/DMA；共享FMA576/448/448路，W8另16整数GU，近等总面积6.449627/6.369820/6.399385mm²（比目标低0.47/1.70/1.25%）。前端448KiB/82端口＋Attention384KiB/96端口，SC不使用的96KiB跨K状态释放，原256KiB CIM区域复用于数字FFN/投影。旧area55字段仅API名，数值28nm×1，未套55nm价或0.81。

三项最终解析一层＋384head检查PASS；原生门禁数组38650227、完整数组38650228已于北京时间13:30提交，下标0BF16_dense/1W8_dense/2W8_screen；aftercorr各组通过后自动跑36层＋完整head。每项请求1CPU12GiB（实际Slurm3CPU），各数组最多2并行，无GPU/训练/新增RTL/PT。最新状态STATUS，不把已提交或解析门禁写成原生完整完成。

恢复work/rayggxia/225/digital250_20261110/HANDOFF.md、ops.py status。包371485605a0d3ba723279345b19f62dea32f7772ba757bd40b938dd75e3f02bd，MF0873dd0ba873923be07792f19cf31f354f6914421100616cbef0ffb0ff67c967。执行快照不可变，不重交健康任务；55nm、500MHz、其他模块原交接不改。完整数字结果待收，PR待审未合并，Projects待维护者同步。

---

'''
(H/'MEMORY_NOTE.txt').write_bytes(note.encode())
for path in [ROOT/'progress/rayggxia/STATUS.md',ROOT/'work/rayggxia/225/HANDOFF.md',ROOT/'architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md']:
    raw=path.read_bytes()
    if note.encode() not in raw:path.write_bytes(note.encode()+raw)
mem=WS/'PROJECT_MEMORY_ZH.md';canonical=WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md'
old=mem.read_bytes();assert canonical.read_bytes()==old
if note.encode() not in old:
    updated=note.encode()+old
    assert mem.read_bytes()==canonical.read_bytes()==old
    canonical.write_bytes(updated);mem.write_bytes(updated)
coord=P/'250MHz/DIGITAL_BASELINE_COORDINATION_20261110_ZH.md'
header='''> **2026-11-10最新范围修正：**用户确认沿55nm三组BF16_dense/W8_dense/W8_screen作主表；共享尺度P8/W8数字CIM只保留补充。三组接口已接入28nm、近等总面积及832KiB有限存储，门禁38650227/完整38650228已提交，尚非完整结果。下文两级定点CIM优先文字保留为此前协调历史；以本更新和digital250_20261110/README_ZH.md为准。

'''
if header.encode() not in coord.read_bytes():coord.write_bytes(header.encode()+coord.read_bytes())
full=P/'250MHz/FULL_RUN_20261110_ZH.md';header2='''> **2026-11-10终态更新：**概率三seed完整原生作业已全部收齐并核验，见FULL_RESULTS_20261110_ZH.md。数字三组也已独立提交；本文其余“概率待完成/数字未提交”为此前提交时点历史。

'''
if header2.encode() not in full.read_bytes():full.write_bytes(header2.encode()+full.read_bytes())
hand=H.parent/'full250_20261109/HANDOFF.md'
update='''# 2026-11-10终态：概率三seed完成

完整原件已收齐并SHA核验，见COLLECTION.json及正式250MHz/FULL_RESULTS_20261110_ZH.md；下方running/未完成文字是历史时点。数字三组新交接转../digital250_20261110/HANDOFF.md，不重交本概率批。

'''
if update.encode() not in hand.read_bytes():hand.write_bytes(update.encode()+hand.read_bytes())
paths=['architecture_tlm/process_28nm/digital250_20261110/'+n for n in ('README_ZH.md','model.py','pricing.py','run.py','FFN_SOURCE_PROFILE.json','VALIDATION.json')]
paths+=['architecture_tlm/process_28nm/250MHz/'+n for n in ('FULL_RESULTS_20261110.json','FULL_RESULTS_20261110_ZH.md','FULL_RUN_20261110_ZH.md','DIGITAL_BASELINE_COORDINATION_20261110_ZH.md')]
paths+=['architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md','progress/rayggxia/STATUS.md','work/rayggxia/225/HANDOFF.md']
paths+=['work/rayggxia/225/digital250_20261110/'+n for n in ('ops.py','prepare.py','remote_submit.py','remote_status.py','record.py','HANDOFF.md','UPLOAD_PLAN.json','SUBMISSION.json','REMOTE_PREFLIGHT.json','STATUS.json','VALIDATION.json')]
paths+=['work/rayggxia/225/full250_20261109/'+n for n in ('collect.py','summarize.py','COLLECTION.json','HANDOFF.md')]
for name in ('worker.py','FROZEN_MANIFEST.json'):
    (H/name).write_bytes((package/name).read_bytes());paths.append('work/rayggxia/225/digital250_20261110/'+name)
for n in paths:
    p=ROOT/n
    if p.suffix=='.py':ast.parse(p.read_text(encoding='utf8'),feature_version=(3,9))
    if p.suffix=='.json':load(p)
    if n.startswith('architecture_tlm/'):
        dest=WS/n;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes());assert sha(dest)==sha(p)
dump(H/'PUBLIC_FILES.json',[dict(path=n,sha256=sha(ROOT/n),content=(ROOT/n).read_bytes().decode('utf8')) for n in paths])
print(json.dumps(dict(status='READY_TO_PUBLISH',public_files=len(paths),digital_tasks_submitted=True,probability_full_verified=True,local_final_checks=len(cases))))

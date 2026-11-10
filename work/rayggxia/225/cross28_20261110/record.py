from pathlib import Path
import ast,hashlib,json
H=Path(__file__).resolve().parent;ROOT=H.parents[3];WS=ROOT.parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_bytes())
dump=lambda p,x:p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode())
sub=load(H/'SUBMISSION.json');plan=load(H/'UPLOAD_PLAN.json');mf=load(Path(plan['package'])/'FROZEN_MANIFEST.json')
assert len(sub['full_jobs'])==12 and sub['pilot']=='38650669'
assert sha(plan['local'])==plan['sha256']
for n,v in mf['files_sha256'].items():assert sha(Path(plan['package'])/n)==v
raw=load(H/'LOCAL_GATES.json');assert len(raw)==8 and all(x['exit_code']==0 for x in raw)
checks=[]
for x in raw:
    d=H/('gate_'+x['model']+'_'+x['scheme']);r=load(d/'RESULT.json');b=load(d/'BUDGET.json');seal=load(d/'SEAL.json')
    assert r['status']==seal['status']=='completed' and load(d/'VALIDATION.json')['status']=='PASS'
    for n,v in seal['files_sha256'].items():assert sha(d/n)==v
    assert r['scope']=='layer_or_partial' and r['layers']==1 and r['head_probe_rows']==384
    for n,v in r['code_sha256'].items():
        assert sha(ROOT/'architecture_tlm/process_28nm'/n)==v
    checks.append(dict(model=x['model'],scheme=x['scheme'],path=str(d),time_ms=r['time_ms'],
        area_mm2=b['conditional_subsystem_area_mm2'],core_mJ=b['conditional_subsystem_energy_mJ'],
        seal_sha256=sha(d/'SEAL.json'),checks=load(d/'VALIDATION.json')))
validation=dict(status='PASS',cases=checks,scope='8analytic1layer384headchecks;notnativefullorPPL',
    frozen_manifest_sha256=plan['manifest_sha256'],files_sha256=mf['files_sha256'])
dump(H/'VALIDATION.json',validation);D=ROOT/'architecture_tlm/process_28nm/cross_models_20261110'
dump(D/'VALIDATION.json',validation)
note='''## 2026-11-10｜28nm250两模型仿真已提交；Qwen数组取消自设两项上限

Issue225/PR249，rayggxia，交叉引用245/PR247。Qwen数字数组38650228原等待原因JobArrayTaskLimit来自本脚本--array=0-2%2，不是EDA全局只有两项能力。已只调ArrayTaskThrottle=3并核用户/jobname；后续队列实核Qwen三项均RUNNING，未重启/重交/改源，THROTTLE_UPDATE留回执。不能据此宣称集群没有其他资源/QOS规则。

按用户要求扩展Llama-3.2-3B-Instruct（revision0cb88a4f764b7a12671c53f0838cd831a0843b95，H3072/F8192/L28/Q24/KV8/V128256）和DeepSeek-LLM-7B-Chat（afbda8b347ec881666061fa67447046fc5164ec8，H4096/F11008/L30/Q32/KV32/V102400）。同28nmTT250、832KiB/178宏、B1/2K、同LPDDR/DMA和各方案原物理资源，不按参数量缩放时间。

已适配3/1Q每KV、DeepSeek4个KV波次、>32KiB尺度元数据在原96KiB激活内起点64→56KiB、无QKNorm和独立untied embedding。4Q物理issue槽时间保留，未用FMA16片增量活动门控代理，物理面积/idle保留并分列有效/物理工作量；不是最优专用映射或新模型质量验证。

本地8构造及8解析一层＋384head均PASS，工作量/字节/全部逻辑KV/完整词表尾块/池排空/账本已核。2026-11-10 14:09北京提交原生门禁数组38650669（8项，无%2），完整12任务38650670—38650681各自依赖对应门禁，不再人为限制两并行；每模型SC三seed17/503/1009＋BF16dense/W8dense/W8screen单seed。完整实际28/30层＋完整词表，结果仍待收；初查8门禁RUNNING、12完整Dependency，无即时错误。

远端tlm28cross250_225_e0291ed6b5a9，包227f2509a117c4673807074f23b303473dc8aea4065cc9fae905ea0db7ca83b1，MF874c258f0b87631b386a8567977f43920cf598e77e3336fd96a08191d58dec72。门禁1CPU12GiB、完整1CPU24GiB（实际按Slurm粒度3CPU），无GPU/训练/PPL/新电路。正式process_28nm/cross_models_20261110/；恢复work/rayggxia/225/cross28_20261110/HANDOFF.md、ops.py status。快照不可变，不重交健康任务；55nm与既有Qwen冻结不改，PR未合并，Projects待维护者同步。

---

'''
(H/'MEMORY_NOTE.txt').write_bytes(note.encode())
for p in (ROOT/'progress/rayggxia/STATUS.md',ROOT/'architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md',ROOT/'work/rayggxia/225/HANDOFF.md'):
    old=p.read_bytes()
    if note.encode() not in old:p.write_bytes(note.encode()+old)
mem=WS/'PROJECT_MEMORY_ZH.md';canonical=WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md'
old=mem.read_bytes();assert canonical.read_bytes()==old
if note.encode() not in old:
    assert mem.read_bytes()==canonical.read_bytes()==old
    canonical.write_bytes(note.encode()+old);mem.write_bytes(note.encode()+old)
for name in ('worker.py','FROZEN_MANIFEST.json'):(H/name).write_bytes((Path(plan['package'])/name).read_bytes())
paths=['architecture_tlm/process_28nm/cross_models_20261110/'+n for n in ('model.py','run.py','MODELS.json','README_ZH.md','VALIDATION.json')]
paths+=['work/rayggxia/225/cross28_20261110/'+n for n in ('ops.py','prepare.py','remote_submit.py','remote_status.py',
    'worker.py','FROZEN_MANIFEST.json','cluster.py','THROTTLE_UPDATE.json','validate.py','VALIDATION.json',
    'LOCAL_GATES.json','CONSTRUCTION_CHECKS.json','HANDOFF.md','SUBMISSION.json','UPLOAD_PLAN.json','REMOTE_PREFLIGHT.json','STATUS.json','record.py','MEMORY_NOTE.txt')]
paths+=['progress/rayggxia/STATUS.md','architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md','work/rayggxia/225/HANDOFF.md']
for n in paths:
    p=ROOT/n
    if p.suffix=='.py':ast.parse(p.read_text(),feature_version=(3,9))
    if p.suffix=='.json':load(p)
    if n.startswith('architecture_tlm/'):
        dest=WS/n;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes());assert sha(dest)==sha(p)
dump(H/'PUBLIC_FILES.json',[dict(path=n,sha256=sha(ROOT/n),content=(ROOT/n).read_bytes().decode('utf8')) for n in paths])
print(json.dumps(dict(status='READY_TO_PUBLISH',files=len(paths),local_gates=len(checks),native_gates=sub['pilot'],full_jobs=len(sub['full_jobs']))))

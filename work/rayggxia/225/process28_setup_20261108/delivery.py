from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PROJECT=ROOT.parents[1]
CROSS=PROJECT/'tmp/cross-model245-20261106';CW=CROSS/'work/rayggxia/245/mainline_20261108'
def save(p,x):p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode())
def prepend(p,t):p.write_bytes(t.encode()+p.read_bytes())
s=json.loads((CW/'revision2/STATUS_CURRENT.json').read_bytes());plan=json.loads((CW/'delivery/PLAN.json').read_bytes())
rows=[]
for name,tail in sorted(s['logs'].items()):
 if not name.startswith('full-'):continue
 worker=int(name.split('_')[-1].split('.')[0]);events=[]
 for line in tail.splitlines():
  try:events.append(json.loads(line))
  except json.JSONDecodeError:pass
 stage=next((x for x in reversed(events) if 'stage' in x),{})
 case=plan[worker]
 rows.append(dict(worker=worker,case=case,current_layer_zero_based=stage.get('layer'),
  current_layer_one_based=stage.get('layer',-1)+1,stage=stage.get('stage'),wall_seconds=stage.get('wall_seconds')))
full=[x for x in s['sealed'] if x['path'].startswith('results/full/')]
assert not full,'Recompute current-case assignment after completedfullcases'
assert len(rows)==8 and len(s['pilot_gates'])==8
summary=dict(status='RUNNING_NO_FULL_CASE_COMPLETED_YET',checked_UTC=s['checked_UTC'],full_job='38631668',
 running_workers=8,completed_full_cases=len(full),expected_full_cases=36,pilot_gates_passed=8,
 aggregate_job='38631676',workers=rows,failures_found=False,
 note='Eachworker firstcase isQwen;later workerloop includesLlama andDeepSeek;currentlayer not completedfullmodel')
status_path=CW/'delivery/STATUS_CHECK_20261108T111153Z.json';save(status_path,summary)
prepend(CROSS/'progress/rayggxia/STATUS.md','''## 2026-11-08 19:11北京时间：三模型批次健康，0/36完整case

实际SSH核38631668八worker均RUNNING（已1:09:04），无失败；8/8前置门禁保留。首轮Qwen当前第9～18层/36层，后续同worker继续Llama/DeepSeek；不是三个模型都已经出完整结果。汇总38631676等待afterok。状态小索引delivery/STATUS_CHECK_20261108T111153Z.json，未重提/改源/取消健康任务。12～24h整批初估暂保留，不承诺结束时刻。

''')
prepend(ROOT/'progress/rayggxia/STATUS.md','''## 2026-11-08 Issue225：建立独立28nm准备目录，未运行完整TLM

用户要求先建对应工艺文件夹。新增architecture_tlm/process_28nm：250MHz已标定FFN/BF16/同步A9组件、500MHz诊断及零uncertainty条件索引、缺项与来源SHA。28HPC+ TT0.9V，面积×1，不套55的.81；28原C19门限缓存18/34拍与55delta_v3隔离。PROCESS_PROFILE整机时间/面积/能量null、full_system_ready/default_enabled均false，无整机运行入口。四来源SHA/三组件PVT/面积/同步A9/无整机值核验通过。

沿Issue225/PR249/task/225-tlm-unified250-20261107，未改55默认或38629485/38631668冻结运行；无新TLM/EDA/GPU/PT。源与公开状态见work/rayggxia/225/process28_setup_20261108/PUBLICATION.json，未有回执前仅本地完成。Projects待维护者同步，PR不合并。

''')
(HERE/'HANDOFF.md').write_bytes('''# Issue225：28nm工艺目录准备

2026-11-08，负责人rayggxia；分支task/225-tlm-unified250-20261107，PR249，base task/225-norm-stream-20261106。用户只要求先建目录，不提供完整TLM；沿既有28nm组件消费范围接续，不重复Issue204的电路工作。

本地源码architecture_tlm/process_28nm/六文件、辅助build.py/delivery.py。根工作区同路径已同字节镜像。250包含最新合格A9同步复位以及FFN/BF16；原A9异步和500失败不晋升。来源准确字节SHA与本地路径在SOURCE_INDEX；未复制工艺库、波形、网表、原报告或整个owner源码。四来源SHA/PVT/面积×1、同步A9/空整机值检查通过，无新PT/TLM运行。

28nm SRAM、Attention/Ising/向量/转换/DMA/CIM接口/互连仍待对应工艺模块标定与资源分配；外存可显式复用原LPDDR边界，不随工艺自动加速。500MHz的零setup uncertainty只是条件推算，不是新STA。后续先完善组件，再做时钟/资源/等面积映射与Qwen锚点；不把55nm剩余模块缩放后冒充完整28nm结果。当前full_system_ready=false、整机值null；不改全局默认或55任务。

发布仅本目录、小型索引、当前STATUS及本交接，回执PUBLICATION.json记录准确commit和读回核验；PR保持draft/open/unmerged，Projects待维护者同步。根备忘录/阅读镜像已同步。三模型status属于Issue245，不将其运行结果写成28nm数据。
'''.encode())
canonical=PROJECT/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';mirror=PROJECT/'PROJECT_MEMORY_ZH.md'
raw=canonical.read_bytes();assert raw==mirror.read_bytes()
note='''## 2026-11-08：28nm独立目录与三模型运行回查

用户要求新建28nm对应TLM文件夹，暂不做完整模型。Issue225/PR249新增architecture_tlm/process_28nm，250MHz收FFN/BF16/最新同步A9、500MHz仅诊断/条件分析、四来源SHA与缺项。28HPC+ TT0.9V、面积×1；全片频率/时间/能量/面积null，full_system_ready/default_enabled=false，无运行入口。不套55面积.81或delta_v3周期、不改55默认，不新交TLM/EDA/PT。未来补28 SRAM/Attention/向量转换/DMA/CIM接口/资源映射后才接整机。发布看work/rayggxia/225/process28_setup_20261108/PUBLICATION.json。

19:11北京时间实际SSH：三模型full38631668八worker均RUNNING1:09:04，前置8/8通过，本批完整0/36。首轮Qwen第9～18层/36层，后续Llama/Deep仍在worker序列；汇总38631676依赖等待，无失败/无重交。状态索引work/rayggxia/245/mainline_20261108/delivery/STATUS_CHECK_20261108T111153Z.json。12～24h整批旧估计保留，非完成保证；不能把进度层数写成整机结果。

---

'''.encode()
assert note not in raw and canonical.read_bytes()==raw and mirror.read_bytes()==raw
canonical.write_bytes(note+raw);mirror.write_bytes(note+raw)
def export(root,paths,out):
 save(out,[dict(path=p.relative_to(root).as_posix(),content=p.read_bytes().decode(),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths])
export(ROOT,list((ROOT/'architecture_tlm/process_28nm').rglob('*.json'))+[ROOT/'architecture_tlm/process_28nm/README_ZH.md',
 ROOT/'progress/rayggxia/STATUS.md',HERE/'HANDOFF.md',HERE/'build.py',HERE/'delivery.py'],HERE/'PUBLIC_FILES.json')
export(CROSS,[status_path,CROSS/'progress/rayggxia/STATUS.md'],HERE/'CROSS_STATUS_FILES.json')
print(json.dumps(dict(folder_files=6,public_files=11,status_full_completed=0,workers=8,process28_full_TLM=False)))

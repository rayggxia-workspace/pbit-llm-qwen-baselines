from pathlib import Path
import ast,datetime,hashlib,json
H=Path(__file__).resolve().parent;ROOT=H.parents[3];WS=ROOT.parents[1];D=ROOT/'architecture_tlm/process_28nm'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
s=json.loads((H/'SUBMISSION.json').read_bytes());p=json.loads((H/'UPLOAD_PLAN.json').read_bytes())
assert s['status']=='SUBMITTED' and s['pilot'] and s['full_array']
package=Path(p['package']);mf=json.loads((package/'FROZEN_MANIFEST.json').read_bytes())
for n,v in mf['files_sha256'].items():assert sha(package/n)==v
assert sha(Path(p['local']))==p['sha256'] and sha(package/'FROZEN_MANIFEST.json')==s['manifest_sha256']
before_dir=Path(json.loads((H.parent/'update250_20261109/PLAN.json').read_bytes())['execution'])
before=(before_dir/'sram_characterization.py').read_bytes();after=(D/'sram_characterization.py').read_bytes()
old=b'roundoff_bound=max(1e-12,2*events*math.ulp(1.0))'
new=b'roundoff_bound=max(1e-12,2*events*(2.0**-52)) # binary64 epsilon;also Python3.6 on EDA'
assert before.replace(old,new)==after
dump(H/'PORTABILITY_PATCH.json',dict(file='architecture_tlm/process_28nm/sram_characterization.py',
    prior_sha256=hashlib.sha256(before).hexdigest(),executed_sha256=sha(D/'sram_characterization.py'),
    old_line=old.decode(),new_line=new.decode(),equivalent_binary64_epsilon=True,
    base_commit='e6dc60c46d880df03efc2ca60ea9ba931ea576b1',effect='no timing or cost change;old executions untouched'))
submitted=datetime.datetime.fromisoformat(s['submitted_UTC']).replace(tzinfo=datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=8)))
doc=f'''# Qwen3-4B：28nm250完整概率版Slurm任务

实际提交：{submitted.isoformat()}（北京时间）。Issue225 / PR249，rayggxia。已提交，完成状态以每项SEAL＋EXIT＋实际Slurm状态为准，不将依赖队列写成已完成。

|任务|Slurm ID|范围|
|---|---|---|
|CPU门禁|{s['pilot']}|原生外存、一层＋384词条head，seed17|
|完整数组|{s['full_array']}，下标0/1/2|36层＋完整151936词表，seed17/503/1009|

完整数组依赖门禁afterok，通过后自动启动，最多2项并行。每项请求1CPU/12GiB，pilot4h、full12h，无GPU；集群可能按节点粒度实际分配3CPU，实际分配以sacct为准，不能把请求数当实测分配。各项有独立工作目录及原生DRAM统计文件，不会并发覆盖统计输出。

## 冻结的配置

Qwen/Qwen3-4B revision1cfa9a7208912126459214e8b04321603b3df60c的执行形状；B1/2K；28nm TT0.9V25°C、250MHz；3随机FFN公共核、GU16/Wd32；SparQ K128、Ising/PV S64、A/S12优先分数前端；256共享BF16 FMA、PV每头2ADD；832KiB/178真实宏。沿最新6.480303mm²条件成本账本，宏/hold/参考宽度边界保留。

本次用**原生Ramulator桥＋既有derived8533配置**，保留LPDDR命令/队列/回压，8533为衍生时序而非独立JEDEC8533签核。外存能量仍采用独立4/6.6/8pJ/bit情景，不能把原生时序模型说成新DRAM芯片实测功耗。完整输出提供含head、扣head阶段时间/能量、各模块面积与动作能量；共享硬件面积不随36层重复。

这是完整硬件事务执行，不加载真实模型权重、不生成文本、不计算PPL；筛选/采样使用已冻结代表性输入及地址轨迹。精度实验是另一条证据，不能因这次硬件运行宣称新精度通过。

## 结果与恢复

服务器根：`{s['root']}`。

- `outputs/pilot/`；`outputs/seed17/`、`seed503/`、`seed1009/`：RESULT/BUDGET/VALIDATION/SEAL。
- `work/<case>/INVOCATION.json`、`EXIT.json`、`run.log`：实际命令、源清单、Slurm ID及返回码。
- `logs/`：Slurm日志；根SUBMISSION记录依赖和作业ID。
- 本地入口：`work/rayggxia/225/full250_20261109/ops.py status`；使用已有EDA登录助手，不在代码/聊天中放凭据。

包SHA-256：`{p['sha256']}`；执行清单SHA-256：`{s['manifest_sha256']}`，大小{p['bytes']}B。manifest逐文件核验源码/配置，并验证已有runtime/dependencies/host三个冻结清单。原始源码包和结果按项目共享/本地索引保存，不修改已提交源。

源基于e6dc60c及一项等值兼容补丁：binary64 epsilon由math.ulp(1.0)改为2**-52，价格与调度不变，六项既有检查通过；补丁前后SHA见PORTABILITY_PATCH。Slurm显式使用已有Python3.9.6/GCC11.2环境与已验证原生库，避免登录节点默认Python3.6造成版本混淆。

本机已检查既有队列，无同配置TLM重复任务；未取消其他健康作业。若门禁失败，完整数组不执行；保持失败源与回执后另做修复，不能原地改冻结包。

数字对照仍未提交；需要的模块确认见[DIGITAL_BASELINE_COORDINATION](DIGITAL_BASELINE_COORDINATION_20261110_ZH.md)。数字主线优先两级量化整数MAC/CIM，旧浮点Wd只作参考；接入、等面积和存储调度由TLM侧完成。
'''
(D/'250MHz/FULL_RUN_20261110_ZH.md').write_bytes(doc.encode())
note=f'''## 2026-11-10 28nm250完整概率版已提交：本地回执待发布

Issue225/PR249，rayggxia；沿task/225-tlm-unified250-20261107。北京时间{submitted.strftime('%H:%M')}提交EDA门禁{s['pilot']}与完整三seed数组{s['full_array']}，afterok依赖、最多2并行；请求1CPU/12GiB，实际Slurm可能分配3CPU，无GPU。36层/151936词表、GU16/Wd32/K128/S64/S12、3核/832KiB保持；原生LPDDR derived8533后端。不是仅跑2层或缩小head的全量任务；门禁本身仍一层/384head。

服务器根{s['root']}；源码包SHA{p['sha256']}，MF{s['manifest_sha256']}。各case独立work防止DRAM统计互相覆盖。现已提交，不把门禁运行/全量依赖等待写成完成；最新状态见本work/STATUS。冻结源码不修改，binary64等值兼容补丁与六检查另存。55/500不变，无新EDA电路/GPU/PPL。

数字新决定：两级量化整数MAC/CIM优先，z25位尾数/指数到共享P8、Wd复用/状态位宽及计费边界需FFN确认；Attention只确认完整PV概率数制/转换和可选R8实际数量归一化。现有参考价格已够，不能再用旧浮点Wd的7.9x/21x称最强数字优势。详细转发文件process_28nm/250MHz/DIGITAL_BASELINE_COORDINATION_20261110_ZH.md；未向其他对话发消息。等面积/数字执行/内存排布由TLM端负责，确认不阻塞概率作业。

恢复本work/ops.py status，完成只认EXIT=0与SEAL/原件SHA；需要修复则独立新快照，不重复提交健康任务。本地提交回执已齐，GitHub同步看本work/PUBLICATION；PR未合并，Projects待维护者同步。

---

'''
(H/'MEMORY_NOTE.txt').write_bytes(note.encode());(H/'HANDOFF.md').write_bytes(('# 完整概率版提交与数字对照交接\n\n'+note+doc).encode())
sp=ROOT/'progress/rayggxia/STATUS.md';sp.write_bytes(note.encode()+sp.read_bytes())
hp=ROOT/'work/rayggxia/225/HANDOFF.md';hp.write_bytes((f'# 最新任务：完整概率版已提交\n\n门禁{s["pilot"]}、全量数组{s["full_array"]}；恢复[本次交接](full250_20261109/HANDOFF.md)。先查STATUS，不重复提交。\n\n').encode()+hp.read_bytes())
# Mirror only owned formal files, not other conversations' handoffs.
paths=['architecture_tlm/process_28nm/'+n for n in ('sram_characterization.py','250MHz/FULL_RUN_20261110_ZH.md','250MHz/DIGITAL_BASELINE_COORDINATION_20261110_ZH.md')]
paths+=['progress/rayggxia/STATUS.md','work/rayggxia/225/HANDOFF.md']
paths+=['work/rayggxia/225/full250_20261109/'+n for n in ('ops.py','prepare.py','remote_submit.py','remote_status.py','record.py','HANDOFF.md','UPLOAD_PLAN.json','SUBMISSION.json','PORTABILITY_PATCH.json','REMOTE_PREFLIGHT.json')]
for n in ('worker.py','FROZEN_MANIFEST.json'):
    (H/n).write_bytes((package/n).read_bytes());paths+=['work/rayggxia/225/full250_20261109/'+n]
for path in paths:
    f=ROOT/path
    if f.suffix=='.py':ast.parse(f.read_text(encoding='utf8'))
    if f.suffix=='.json':json.loads(f.read_bytes())
    if path.startswith('architecture_tlm/'):
        target=WS/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes());assert sha(target)==sha(f)
dump(H/'PUBLIC_FILES.json',[dict(path=n,sha256=sha(ROOT/n),content=(ROOT/n).read_bytes().decode('utf8')) for n in paths])
print(json.dumps(dict(status='SUBMISSION_RECORDED_NOT_COMPLETED',pilot=s['pilot'],full=s['full_array'],public_files=len(paths),digital_submitted=False)))

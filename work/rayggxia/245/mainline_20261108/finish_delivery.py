from pathlib import Path
import hashlib,json,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PROJECT=ROOT.parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,s):p.write_bytes(s.encode())
def dump(p,x):write(p,json.dumps(x,indent=2,ensure_ascii=False)+'\n')
note='''
### 已启动回执（2026-11-08 18:04北京时间）

8/8门禁已通过driver及Slurm退出码；完整worker数组 **38631668_[0-7%8]** 已全部进入RUNNING，共执行36case；最终汇总 **38631676** 等待afterok。完整结果尚未收齐。PILOT_SUMMARY为单层预检，不能当整token；STATUS_CURRENT留存实际时点。按已观测每冷层约4～11分钟及最长模型30/36层，完整批次初估12～24小时，受共享CPU实际性能影响，不能承诺精确结束时间。
'''
p=ROOT/'architecture_tlm/model_scaling_20261106/CURRENT_MAINLINE_ZH.md';write(p,p.read_text(encoding='utf-8')+note)
p=ROOT/'progress/rayggxia/STATUS.md';write(p,'## 当前运行回执：full38631668 / aggregate38631676，8/8门禁通过（2026-11-08）\n\n完整8worker均已运行；36case尚未收齐。正式交付CURRENT_MAINLINE_ZH.md；delivery/PILOT_SUMMARY及FULL_SUBMISSION、AGGREGATE_JOB已收，未把单层当整机。下述“安排”阶段现已进入执行。\n\n'+p.read_text(encoding='utf-8'))
p=ROOT/'work/rayggxia/245/HANDOFF.md';write(p,'## 当前作业ID补充（2026-11-08）\n\n8/8门禁退出码0:0，full worker38631668_[0-7%8]均已RUNNING；aggregate38631676 afterok等待。最新STATUS及8项单层封存摘要见mainline_20261108/delivery；完整结果尚未收齐。禁止重交或改快照。\n\n'+p.read_text(encoding='utf-8'))
entry='''
## CM245-current：跨模型接回当前100/250主线（2026-11-08）

问题：旧三模型试接仍为串行相加，不能继承主线优化/有效250v3价格。实现：current_mainline.py保留有限FIFO/早补货、PV生产消费重叠、公共FFN；数字共享FMA真租约，W8 GU四K64合包、有限双包FIFO、NL五级II1；参数化3Q组与MHA四波、36KiB元数据/Norm真实bank读写。资源：1001088KiB/6核、250960KiB/3核，数字同总面积上限，离散切片缺口显式报。有效v3价仅55，28候选不混。

证据：8/8原生/解析单层门禁与5本地前驱检查；Qwen250解析逐周期一致，100差12拍（0.010%）保留，容差0.1%而字节/MAC/帧/容量严格；未把未归因差异称为已解释。完整36case（24配置）EDA38631668已启动，汇总38631676 afterok；成果入口[CURRENT_MAINLINE_ZH.md](model_scaling_20261106/CURRENT_MAINLINE_ZH.md)，Issue245/PR247。改进是本任务硬件映射，不修改全项目默认，不宣称全局最优或真实文本质量。原串行结果/严格相等失败/配额失败仍保留。

口径：r16是归约加法器路数，SparQ始终r32；当前已标定GU16/Wd32而非未标定GU8。SRAM动作与全物理漏电一次、共享FMA一次、gross服务＋余时等待；外存4/6.6/8pJ/bit独立情景。SS/TT代理、CIM接口/NoC/CTS/PHY未全片标定，完整报告待收，不从冷层外推最终收益。
'''
rel='architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md';p=ROOT/rel
base=subprocess.check_output(['git','show','HEAD:'+rel],cwd=ROOT).decode()
assert 'CM245-current' not in base;p.parent.mkdir(exist_ok=True);write(p,base+entry)
canonical=PROJECT/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';mirror=PROJECT/'PROJECT_MEMORY_ZH.md'
raw=canonical.read_bytes();assert raw==mirror.read_bytes()
memory='''## 2026-11-08 Issue245：三模型已接主线，完整36case运行

用户要求三模型当前概率硬件与数字基线PPA。复用Issue245/PR247/task/245-cross-model-estimate；Qwen3-4B36层、Llama3.2-3B-Instruct28层、DeepSeek7BChat30层，同一1001088KiB/6核/33.284710mm²与250960KiB/3核/22.086073mm²芯片。有效55TT250 delta_v3价格已接；28候选不混。四路径SC/BF16dense/W8dense/W8screen，SC三seed17/503/1009，数字单seed，共24配置/36完整case，含/不含head阶段。当前校准GU16/Wd32，不把GU8算法候选当实测硬件。

保留主线有限FIFO/早补货、PV并行生产消费；数字FMA全阶段真共享，GU四K64合包/NL五级II1，真实bank/DMA/回压/权重字节/Norm/尺度访存。DeepMHA四波，逻辑KV输入偏移已改，元数据33024B分36KiB，Norm16KiB双槽；保留物理4Q填充QK/数字PV，SC只采有效头。r16指归约路数，SparQ仍r32，撤销旧“维数没对齐”说法。

revision2八门禁38631497全部退出0:0；full **38631668_[0-7%8]** 已8worker运行，每个4/5case，1逻辑线程12GiB，实际分区3CPU/任务，0GPU，48h上限非ETA。汇总38631676 afterok，强制36唯一全层含head/原生/SHA守恒才产出完成报告。初估12～24h，非承诺；未收齐前不把单层乘层数或当最终PPA。冻结root/public3/home/t6s011227/pbit_chimera_pipeline_20260920/tlm245_current_3a7dd5e0679e；zipSHA3a7dd5e0679ed56cdb60e37ef54c3c787d62e4470a7436e414f6348a63ab0bbf，manifest982f9303785c364ed7c7ac5384927f0a12f98388433708306878e5f14fbae925。

原revision1 pilot38631345保留作诊断：100锚点精确相等门禁差12拍、逻辑KV输入偏移待修；其SEAL不等于driver通过。原pending协调38631395确认后取消，无full启动；36元素直接提交因AssocMaxSubmitJobLimit未生成任务。revision2单独修正，100解析1.206270ms vs本地1.206150，差约.010%，2501.085720一致；容差.1%，所有工作量严格，不宣称差异原因已证明。旧24个串行适配pilot封存仍仅历史。

入口architecture_tlm/model_scaling_20261106/CURRENT_MAINLINE_ZH.md及work/rayggxia/245/HANDOFF.md。恢复仅launcher_r2.py status，禁止重prepare/改冻结源/重跑健康case。新胶合/元价格/汇总与回执本地齐，发布看PUBLICATION_CURRENT；PR未合并、Projects待维护者同步。能量在声明组件边界闭合，SS100控制/格式和部分250SS代理、CIM/PHY/NoC/CTS仍未全片实测，外存4/6.6/8pJ是情景。无新GPU/PPL/训练/PT，不改变默认或健康225作业。

---

'''
assert 'Issue245：三模型已接主线，完整36case运行' not in raw.decode()
new=memory.encode()+raw
assert canonical.read_bytes()==raw and mirror.read_bytes()==raw
canonical.write_bytes(new);mirror.write_bytes(new)
dump(HERE/'MEMORY_SYNC.json',dict(before_sha256=sha(raw),after_sha256=sha(new),canonical=str(canonical),mirror=str(mirror),same_bytes=True))
files=json.loads((HERE/'PUBLIC_FILES.json').read_bytes());paths={x['path'] for x in files}
paths|={rel,'work/rayggxia/245/mainline_20261108/collect_gates.py','work/rayggxia/245/mainline_20261108/finish_delivery.py'}
paths|={p.relative_to(ROOT).as_posix() for p in (HERE/'delivery').glob('*.json')}
dump(HERE/'PUBLIC_FILES.json',[dict(path=n,content=(ROOT/n).read_bytes().decode('utf-8'),sha256=sha((ROOT/n).read_bytes())) for n in sorted(paths)])
print(json.dumps(dict(status='delivery_ready',files=len(paths),full_job='38631668',aggregate='38631676',memory_sha=sha(new))))

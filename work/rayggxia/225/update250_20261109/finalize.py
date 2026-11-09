from pathlib import Path
import ast,hashlib,json,subprocess,sys,zipfile
H=Path(__file__).resolve().parent;ROOT=H.parents[3];WS=ROOT.parents[1];D=ROOT/'architecture_tlm/process_28nm'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_bytes())
def dump(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
r=load(D/'250MHz/UPDATED_TLM_20261109.json');e=r['full36_estimate'];b=load(D/'250MHz/BINDINGS.json')
assert r['status']=='PASS_UPDATED250_INTEGRATION_AND_PRICE_CLOSURE'
cmd=[sys.executable,'-X','utf8','-B',str(D/'test_refresh250.py')]
with (H/'UNIT_TESTS.log').open('wb') as stream:code=subprocess.run(cmd,stdout=stream,stderr=subprocess.STDOUT).returncode
assert code==0;dump(H/'UNIT_TESTS.json',dict(command=cmd,exit_code=code,tests=6,log_sha256=sha(H/'UNIT_TESTS.log')))
r['unit_tests']='test_refresh250.py:6passed';dump(D/'250MHz/UPDATED_TLM_20261109.json',r)

# Update current index values, preserving actualfull36 fields as unexecuted.
default=load(D/'DEFAULT_SRAM832_20261109.json');row=next(x for x in default['rows'] if x['clock_MHz']==250)
row.update(conditional_subsystem_area_mm2=e['area_mm2'],default_config_sha256=sha(D/'250MHz/WHOLE_CONFIG.json'),
    tested_config_sha256=load(H/'p250/RESULT.json')['macro_config_sha256'],
    latest_binding_sha256=sha(D/'250MHz/BINDINGS.json'),latest_validation='250MHz/UPDATED_TLM_20261109.json',
    full_default36_estimate_time_ms=e['time_ms'],full_default36_estimate_core_energy_mJ=e['core_energy_mJ'],
    full_default36_estimate_is_actual_run=False)
default['cost_update250']='zero-margin FFN/FMA,PV reference closure and explicit platform macros;500 unchanged'
dump(D/'DEFAULT_SRAM832_20261109.json',default)
p=D/'DEFAULT_SRAM832_20261109_ZH.md';text=p.read_text(encoding='utf8')
text=text.replace('6.566340/6.592880mm²','6.480303/6.592880mm²')
text+='\n250MHz新价格接入及条件时间/能量见[最新250MHz报告](250MHz/UPDATED_TLM_20261109_ZH.md)。500MHz价格/配置不变；上述面积更新不是新完整36层实际回放。\n';p.write_bytes(text.encode())

doc='''# 28nm / 250MHz：最新价卡与TLM更新

2026-11-09，Issue225 / PR249，rayggxia。仅更新250MHz；55nm及500MHz配置不变。六个CPU回放、六项账本/来源检查通过，无新增EDA或GPU任务。当前条件核心子系统账本已闭合，物理整片PPA仍不作为本报告结论。

## 当前主线

Qwen3-4B，B1，2K上下文；W8随机FFN GU16/Wd32、公共核3个，核服务18/34拍；256 BF16 FMA、4上下文/反馈4拍；SparQ K128、Ising/PV S64，32个Q头每头2个PV ADD/反馈7拍。SRAM832KiB/178真实宏（30×8KiB＋148×4KiB），前端106共享端口、Attention72端口；16KiB DMA返回保持。外存继续用136.4606GB/s、30ns解析后端；不因片上时钟改变带宽。

分数前端按用户已确认的A路径：FP32输入先量化S12/F4，再整数max-gap到8位LUT地址/P8阈值。B路径FP32先max-gap的价卡仍可查，但未切换主线，未将B的两遍读取/周期套给A。共同前端与gap采样核各计一次，不叠加旧完整ab_both核。

## 本次实际接入

|部分|选择及依据|
|---|---|
|随机FFN|零余量同RTL重综合，单核0.372693132mm²，GU/Wd10.1625/9.218958pJ每DOT64；原18/34拍不变|
|共享BF16 FMA|新零余量FMA16/C4，0.060761862mm²、203.825pJ每DOT64；全片16组只计一次|
|数字参考|A9端点、BF16/W8双模式池、FP32 ADD、数字CIM、WS/OS及整数GU等登记为可用对照；不额外实例化到概率主线|
|Ising/R8|依交接保留原已验收映射；新小面积Ising另列，能量更高的新R8不替换；systematic仅归档|
|PV累加|实测vacc16为依据，保留128个FP32状态及全部寄存器/ICG，仅其余逻辑按2/16估计；不是新2ADD整块PPA|
|V控制|采用新补测Vctrl参考价，按实际unique_V/miss与reuse次数混合计费；不包含SRAM或外存|
|平台宏|DMA16KiB＋操作数FIFO8KiB＋描述符4KiB按真实28nm寄存器单元面积外推，另有向量/输出0.25mm²及CIM接口0.15mm²；总功率40mW情景，20–80mW敏感性|

主FFN/数字组件6项72PT、九旧网表零余量STA，以及三项重综合38PT已齐。原始归档与映射SHA由来源索引定位，选中三项新PPA归档SHA已再次核对；没有把复用STA当新映射功耗。PV的setup已通过，部分hold依用户决定暂缓；不自动升级为全时序/后布局通过。参考Vctrl16bank与当前9bank/组调度不同，作为显式结构参考计价，真实访存争用仍按当前布局执行。

## 面积、时间和能量

**面积预算6.4803mm²**，原6.5663mm²，减少1.31%。包括SRAM、计算与具名宏；不额外加15%统一预留，不含外部DRAM die、LPDDR PHY、pad、CPU、封装及全局CTS/SPEF。28nm面积系数1。

下面为一/两层与实际1024/1152/2048词条head探针构成的条件外推；**尚未实际执行完整36层及151936词表运行**。六个小回放本身均已完成并封存，不将预测写成完整作业完成。

|指标|条件估计|
|---|---:|
'''
for name,value,unit in [('含lm_head时间',e['time_ms'],'ms/token'),('扣除lm_head阶段时间',e['without_lm_head_stage_ms'],'ms/token'),
    ('lm_head阶段时间',e['lm_head_stage_ms'],'ms'),('片上核心能量',e['core_energy_mJ'],'mJ/token'),
    ('核心＋外存能量，4pJ/bit情景',e['total_energy_mJ_by_external_pJbit']['4.0'],'mJ/token'),
    ('扣除lm_head阶段核心＋外存能量，同情景',e['without_lm_head_stage_total_mJ_at4pJbit'],'mJ/token'),
    ('核心平均功率',e['core_average_W'],'W'),('核心＋外存平均功率，同情景',e['total_average_W_at4pJbit'],'W')]:
    doc+=f'|{name}|{value:.4f} {unit}|\n'
doc+='''
“扣除lm_head阶段”是同一次执行的final_norm前缀，保留原硬件常驻功耗，仍含阶段前已重叠预取的64KiB读出权重；不是独立移除整个lm_head重排后的运行。报告按真实前缀/后缀分账，二者精确加回总数。完整head外存权重777,912,320B，其中64KiB在前缀，不能丢失或重复计费。

整模型外推用一次性embedding/final_norm加冷/稳态层增量；head以实际384词条整层阶段为锚，加148×(2048−1024词条探针)，避免拟合负启动延迟。归档含128词条尾部检查。采样器沿已测平均服务宏＋冻结地址流；不是逐query物理p-bit或新PPL。外存4/6.6/8pJ/bit只是独立能量情景，未额外叠加同边界背景功率；本次未做原生LPDDR命令回放。

|模块|面积mm²|完整token核心能量条件外推mJ|
|---|---:|---:|
'''
for x in e['parts']:doc+=f"|{x['component']}|{x['area_mm2']:.6f}|{x['total_mJ']:.6f}|\n"
doc+='''
每动作gross先移除其测量窗口背景，再加物理实例完整驻留idle；平台40mW属于总功率宏，只计一次。FFN核已包含随机源/SNG/Sigmoid/AND/归约/ICG，不再另加同一前端；共享FMA、SRAM面积也不按36层重复。PV标量能量来自参考宽度，stalled及Vctrl backpressure作为敏感性，未假称真实2ADD/当前缓存整块功耗。

## 实际验证与剩余边界

250MHz两层＋384head为2.211800ms；500MHz单层＋384head为0.997290ms，均与更新前逐项相同。动作、核帧、尺度/编码、SRAM计数与178bank活动、外存各类请求和地址摘要一致；500MHz完整BUDGET也一致。新250MHz另跑一层＋384head，均通过SEAL/源码/配置、边界/排空与矩阵/采样计数。新价格改变成本，不改变该轮执行周期。

六项单元/账本检查通过：新源/三个选中归档SHA，价卡与其他频率保护，条件账本加总，gross/idle恒等式，head分账，旧prepare不能覆盖新默认。历史制备脚本保留，但新默认用refresh250.py重建，防止无意回退。

当前不需要再等新一批主模块电路仿真。仍明确保留：紧凑PV结构参考、DMA/向量/接口宏、S2动态价估计、hold暂缓、平均采样延迟与地址oracle；这些是目前约定的架构估算边界。完整36层原生外存、数字R8可变输出的同资源整链、其他K/S/模型及布局签核各自另验，不能继承本次完成状态。

正式配置：本目录BINDINGS.json、WHOLE_CONFIG.json、COMPONENTS.json；预更新版本另存PRE_REFRESH。精确结果及SHA：UPDATED_TLM_20261109.json、CONDITIONAL_ESTIMATE_20261109.json；原件归档入口work/rayggxia/225/update250_20261109/ARCHIVE_INDEX.json。仅本次默认和计价更新，原有冻结执行不改，55nm/500MHz不变，无新PPL/训练或EDA。
'''
(D/'250MHz/UPDATED_TLM_20261109_ZH.md').write_bytes(doc.encode())
(D/'250MHz/README_ZH.md').write_bytes(('''# 28nm / 250MHz TLM当前入口

[最新结果、成本边界与验证](UPDATED_TLM_20261109_ZH.md)。配置权威为BINDINGS.json＋WHOLE_CONFIG.json，COMPONENTS用于展示。更新命令：`python -X utf8 -B architecture_tlm/process_28nm/refresh250.py --workspace <a_P_BIT绝对路径>`；验证：同目录test_refresh250.py。旧prepare_bindings.py不会覆盖已更新默认。

概率主线：3共享FFN核、GU16/Wd32、K128/S64、S12优先分数前端、832KiB/178宏；500MHz和55nm独立。run_whole.py仍支持完整36层/完整head命令，必须指定新的输出目录。当前完整token表是明确外推，不能当作已执行整机。预更新配置/价卡保留PRE_REFRESH，旧任务只按其封存SHA恢复。
''').encode())
intro='> **2026-11-09：250MHz已接新零余量FFN/FMA、PV参考与平台宏，面积预算6.4803mm²。** 六个小回放与六项检查通过；完整token46.02ms为条件外推。500MHz保持6.5929mm²预算。见[250MHz最新报告](250MHz/UPDATED_TLM_20261109_ZH.md)。\n\n'
for name in ('README_ZH.md','WHOLE_MODEL_ZH.md'):
    p=D/name;p.write_bytes((intro+p.read_text(encoding='utf8')).encode())
note='''## 2026-11-09 28nm250 TLM最新价卡已接入：本地完成待发布

Issue225/PR249，rayggxia；task/225-tlm-unified250-20261107，base task/225-norm-stream-20261106，工作目录tmp/tlm-unified250-issue225-20261107。新SC/FMA/整数GU零余量价、主数字参考、17Attention卡可用，选原Ising/R8，S12优先分数前端保持；PV新实测参考按保留固定状态的2/16结构代理，V控制按真实miss/reuse，平台宏显式闭合，无旧“PV缺价”。不是全芯片PPA。

六CPU回放封存：250两层+384head2.2118ms与原逐项不变，500单层.99729ms且BUDGET不变；新250单层及1024/1152/2048head探针通过；六账本/来源/防覆盖检查通过。面积6.480303mm²，较6.566340少1.31%。一/两层及head条件外推完整46.01856ms、扣head阶段39.408936ms，核心15.016133mJ、4pJ情景总188.191138mJ；不是实际完整36层/原生LPDDR运行。head分账保留前缀重叠预取64KiB，硬件常驻面积不变。

来源与原件SHA见本work/PLAN、EXTRA_PLAN、ARCHIVE_INDEX、UNIT_TESTS及正式250MHz/UPDATED_TLM_20261109.json；报告UPDATED_TLM_20261109_ZH.md。3新归档SHA核验。原冻结任务、55/500默认不改，无新EDA/GPU。当前本地完成，发布回执见本work/PUBLICATION；PR待审未合并，Projects待维护者同步。下一步完整回放用新绑定冻结新目录；数字R8整链必须按可变输出实际轨迹，不能强塞S64。

---

'''
status=ROOT/'progress/rayggxia/STATUS.md';status.write_bytes(note.encode()+status.read_bytes())
(H/'HANDOFF.md').write_bytes(('# 28nm250最新TLM交接\n\n'+note+'''
复现：先运行process_28nm/refresh250.py更新250价卡（读取现有PRE_REFRESH基线，不动500）；运行test_refresh250.py。已有执行不能覆写，原件zip恢复后按PLAN/EXTRA_PLAN冻结命令改--out到新的绝对目录。run_validation.py是本轮一次性冻结/执行工具，collect.py核验后产生明确外推；finalize.py是本地一次性归档/交付，不重复覆写归档。

物理面积/芯片签核仍未完成，按选定边界条件账本闭合；新profile中的full_system_ready=false不能解读为模块尚未仿真。严格保留PV负hold、紧凑宽度和16bank控制到9bank runtime代理。量化A/S12与B/FP32都已有价，当前按用户要求选A，不能只换价不换两遍读与周期。新小面积Ising只注册可选，不自动换；新R8更费能不换。全部CPU执行已完成，无需GPU/Slurm查询。
''').encode())
rh=ROOT/'work/rayggxia/225/HANDOFF.md';old=rh.read_bytes();rh.write_bytes(('# 最新：28nm250 TLM价卡/账本更新\n\n[本次可执行交接](update250_20261109/HANDOFF.md)。832KiB混合宏保持；当前250面积6.4803mm²，500不变。发布实际状态见本次PUBLICATION。\n\n').encode()+old)

arc=WS/'project_archives/tlm250_refresh225_20261109';arc.mkdir(exist_ok=True);z=arc/'sealed_cases_and_sources.zip';assert not z.exists()
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as pack:
    for name in ('PLAN.json','EXTRA_PLAN.json','UNIT_TESTS.log','UNIT_TESTS.json'):
        pack.write(H/name,name)
    for folder in [Path(load(H/'PLAN.json')['execution'])]+[H/n for n in ('p250','p250_one','p500','head250_1024','head250_1152','head250_2048')]:
        for p in folder.rglob('*'):
            if p.is_file():pack.write(p,p.relative_to(H))
    for p in H.glob('*_RETURN.json'):pack.write(p,p.name)
dump(H/'ARCHIVE_INDEX.json',dict(path=str(z),sha256=sha(z),bytes=z.stat().st_size,
    scope='six completed CPU TLM cases,immutable sources/configs and receipts;no PDK or circuit netlists'))
note_path=H/'MEMORY_NOTE.txt';note_path.write_bytes(note.encode())
paths=['architecture_tlm/process_28nm/'+n for n in (
    'refresh250.py','pricing250.py','whole_pricing.py','run_whole.py','prepare_bindings.py','test_refresh250.py',
    '250MHz/BINDINGS.json','250MHz/WHOLE_CONFIG.json','250MHz/COMPONENTS.json',
    '250MHz/BINDINGS_PRE_REFRESH_20261109.json','250MHz/WHOLE_CONFIG_PRE_REFRESH_20261109.json','250MHz/COMPONENTS_PRE_REFRESH_20261109.json',
    '250MHz/REFRESH_SOURCE_INDEX.json','250MHz/UPDATED_TLM_20261109.json','250MHz/CONDITIONAL_ESTIMATE_20261109.json',
    '250MHz/UPDATED_TLM_20261109_ZH.md','250MHz/README_ZH.md',
    'DEFAULT_SRAM832_20261109.json','DEFAULT_SRAM832_20261109_ZH.md','README_ZH.md','WHOLE_MODEL_ZH.md')]
paths+=['progress/rayggxia/STATUS.md','work/rayggxia/225/HANDOFF.md']
paths+=['work/rayggxia/225/update250_20261109/'+n for n in ('run_validation.py','run_one_layer.py','collect.py','finalize.py','HANDOFF.md','ARCHIVE_INDEX.json','UNIT_TESTS.json')]
for path in paths:
    p=ROOT/path
    if p.suffix=='.json':load(p)
    if p.suffix=='.py':ast.parse(p.read_text(encoding='utf8'),filename=path)
    if path.startswith('architecture_tlm/'):
        target=WS/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes());assert sha(target)==sha(p)
dump(H/'PUBLIC_FILES.json',[dict(path=p,content=(ROOT/p).read_bytes().decode('utf8'),sha256=sha(ROOT/p)) for p in paths])
print(json.dumps(dict(status='LOCAL250_UPDATE_VALIDATED_AND_DELIVERY_PREPARED',files=len(paths),archive_sha256=sha(z),
    area_mm2=e['area_mm2'],time_estimate_ms=e['time_ms'],full36_actually_run=False)))

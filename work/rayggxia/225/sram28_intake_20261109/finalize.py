"""Document and register real28 SRAM intake; preserve producer artifacts."""
from pathlib import Path
import hashlib,json,subprocess,sys

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];WS=ROOT.parents[1]
FORMAL=ROOT/'architecture_tlm/process_28nm'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(s.encode())
def dump(p,x):write(p,json.dumps(x,ensure_ascii=False,indent=2)+'\n')

x=json.loads((FORMAL/'SRAM_INTAKE_20261109.json').read_bytes())
cards=json.loads((FORMAL/'SRAM_CALIBRATION_20261109.json').read_bytes())
report='''# 28nm真实SRAM已接入TLM

2026-11-09，Issue225 / PR249，接入维护人rayggxia，原SRAM表征交付人jieruiz。

本版用真实TSMC28HPC+ S0 256×128、4KiB、1RW宏替换跨工艺迁移估值。只替换SRAM价格/证据字段，保留有限bank、端口、DMA信用、FIFO、预取和回压模型。250/500MHz配置均已接入；55nm配置和运行中的冻结任务不变。

|参数|250MHz|500MHz|
|---|---:|---:|
'''
for label,key,mul in [('16B随机读gross，pJ','read_gross_pJ_per16B',1),('16B随机写gross，pJ','write_gross_pJ_per16B',1),('读事件增量，pJ','read_pJ_per16B',1),('写事件增量，pJ','write_pJ_per16B',1),('停钟背景，每bank µW','leak_W_per4KiB',1e6),('开钟idle，每bank µW','clock_on_idle_W_per4KiB',1e6)]:
    report+=f"|{label}|{cards['versions']['250'][key]*mul:.6f}|{cards['versions']['500'][key]*mul:.6f}|\n"
report+='''|返回延迟/接受间隔|1拍/1拍|1拍/1拍|

每宏面积0.01188012105mm²，240宏共**2.851229052mm²**，面积系数1；不乘本项目55nm的0.81。宏本体时序支持上述服务，240bank远端连线仍沿当前模型，不称整片物理签核。未改成120个8KiB宏，避免减少独立端口。

采用“相对停钟idle的增量访问能量×次数＋所有物理宏停钟功率×总时间”。因此不能再叠加一次gross读写。假定空闲bank关钟；真实ICG与bank外围由平台边界承担，未冒称本次已测。JSON另给开钟idle敏感性。

CIM权重接口沿用户刚确定的普通SRAM代理：每个使用的8KiB权重帧读一次并跨采样复用。原DMA写入/宏面积/泄漏已经收费；不新增一套权重DFF，也不把等效读事件改成串行延迟。

## 验证与结果

12个最终功耗窗口的原始power报告从归档逐SHA核验；4个完整PT随机读/写窗口由TLM账本精确重现。旧250/500/500双拍SRAM三个集成回放按原动作重计，原RESULT/BUDGET/SEAL字节不改。CIM已计读去重、面积、角点、数制和无55nm价格混入检查通过。没有新EDA/PT/全模型时序任务。

下面是此前“小规模TLM＋36层/全词表外推”条件估计，仅更新SRAM及其权重读代理；其他平台宏和500MHz FMA代理仍保持原范围。**不是新完成的36层原生LPDDR仿真或完整芯片PPA。**

|版本|覆盖子系统面积，无统一布局预留|含head时间|片上能量|总能量，外存4pJ/bit|
|---|---:|---:|---:|---:|
'''
for r in x['cases']:
    report+=f"|{r['clock_MHz']}MHz|{r['area_mm2']:.3f}mm²|{r['time_ms']:.3f}ms|{r['chip_energy_mJ']:.3f}mJ|{r['total_energy_mJ_at4pJbit']:.3f}mJ|\n"
report+='''
用户决定暂不考虑统一15%布局/控制预留，因此面积按已计模块与SRAM直接相加，统一系数为1。已有具名控制模块与寄存器面积保留，不与百分比预留混淆。片上能量增加来自实测读写价格高于旧迁移估计，以及显式补计CIM权重等效读；时间没有变化，因为1拍返回和II1没有改变。外存字节/带宽/能量情景不变。

机器接口：`SRAM_CALIBRATION_20261109.json`、两频`WHOLE_CONFIG.json`；执行：`whole_model.py`/`run_whole.py`，计费：`whole_pricing.py`/`sram_characterization.py`。`SRAM_INTAKE_20261109.json`含所有来源SHA、三原回放重计和条件整机数值。严格完整整机值仍保留null，因为其他模块尚有明确宏价/缺项；SRAM已从未计列表移除。

原交付文档与待导入记录保持原字节/创建时状态；本次新接入状态以本文件和发布回执为准。12窗均seed17/TT0.9V25°C；SS及其他尺寸仅库提取，没有补造SS活动PT、多seed、后布局或睡眠唤醒结果。受限库、厂商模型、原波形及网表不上传。
'''
write(FORMAL/'SRAM_INTAKE_20261109_ZH.md',report)
source_report=WS/'architecture_tlm/process_28nm/SRAM_CHARACTERIZATION_RESULTS_ZH_20261109.md'
(FORMAL/source_report.name).write_bytes(source_report.read_bytes())
note='''## 2026-11-09 28nm SRAM真实宏已接入

Issue225/PR249，rayggxia接入，原表征jieruiz。S0真实4KiB/128bit/1RW、TT0.9V25°C，250/500各六窗；12原功耗报告SHA与归档校验、4完整PT读写窗口账本复现、3原集成回放重计通过。普通SRAM不再用55残差迁移价；240宏面积2.851229052mm²，28面积×1。

两频WHOLE_CONFIG已写真实随机读写价格与停钟增量基线，1拍返回/II1保持。whole_model/run_whole/whole_pricing已实际接接口，SRAM从未计列表移除。普通SRAM代理也用于驻留CIM权重每tile一次读；写入/面积/泄漏不重复。未改55nm或冻结任务，无新EDA/长时序回放。

原条件整机估计接入SRAM并按用户决定取消15%统一预留后，250/500中心面积7.139/7.165mm²、时间45.901/40.991ms、片上15.013/15.050mJ，总4pJ情景188.208/188.268mJ。仍是小TLM＋36层/完整head外推，500FMA/PV/平台等原宏限制保留，不能写新完整芯片或原生全层结果。正式process_28nm/SRAM_INTAKE_20261109_ZH.md/json与SRAM_CALIBRATION；历史粗估原件不改。

受限1.5MB完整库表JSON保留本机/授权服务器，只公开所需标量、说明和SHA。中央记录sram28-s0-225-20261109沿原run归档，owner不改。发布状态看本次work/PUBLICATION.json，PR未合并；Projects待维护者同步。
'''
for name in ('README_ZH.md','WHOLE_MODEL_ZH.md'):
    p=FORMAL/name;old=p.read_text(encoding='utf8')
    heading='> 2026-11-09更新：真实28nm SRAM宏已接入250/500配置。见[SRAM接入结果](SRAM_INTAKE_20261109_ZH.md)。下方此前SRAM未表征/跨工艺估值均为历史状态，其它模块限制仍保留。\n\n'
    if not old.startswith(heading):write(p,heading+old)
status=ROOT/'progress/rayggxia/STATUS.md'
if not status.read_text(encoding='utf8').startswith(note):write(status,note+'\n---\n\n'+status.read_text(encoding='utf8'))
write(HERE/'HANDOFF.md',note+'\n复核命令：python -B architecture_tlm/process_28nm/intake_sram.py；保留原件，只有价格变化无需重跑时序。\n')
master=WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';mirror=WS/'PROJECT_MEMORY_ZH.md'
old=master.read_bytes();assert old==mirror.read_bytes()
new=old if old.startswith(note.encode()) else (note+'\n---\n\n').encode()+old
assert master.read_bytes()==mirror.read_bytes()==old
master.write_bytes(new);mirror.write_bytes(new)

# Restore only tracked registry metadata in the existing sparse task checkout.
tracked=subprocess.check_output(['git','ls-files','-z','digital_circuit_simulation_registry'],cwd=ROOT).decode('utf8').strip('\0').split('\0')
for name in tracked:
    p=ROOT/name
    if not p.exists():
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(subprocess.check_output(['git','show',':'+name],cwd=ROOT))
original=WS/'sram28_char_20261109/sram28-s0-225-20261109.json'
record=json.loads(original.read_bytes())
for a in record['artifacts']:
    p=Path(a['path'])
    if p.is_file():assert sha(p)==a['sha256']
    elif a.get('required'):raise FileNotFoundError(p)
record['status']='macro_characterization_complete_TLM_bound'
record['integration']=dict(integrator='rayggxia',issue=225,PR=249,
    original_record_sha256=sha(original),calibration_sha256=sha(FORMAL/'SRAM_CALIBRATION_20261109.json'),
    full_chip=False,new_PPA=False)
dump(HERE/'REGISTRY_INPUT.json',record)
registry=ROOT/'digital_circuit_simulation_registry/registry.py'
dest=ROOT/'digital_circuit_simulation_registry/records/sram28-s0-225-20261109.json'
commands=([['add',str(HERE/'REGISTRY_INPUT.json')]] if not dest.exists() else [])+[['check'],['render']]
if dest.exists():assert json.loads(dest.read_bytes())==record
for args in commands:
    p=subprocess.run([sys.executable,'-B',str(registry),*args],cwd=ROOT,capture_output=True,text=True,encoding='utf8')
    write(HERE/('registry_'+args[0]+'.txt'),p.stdout+p.stderr)
    assert p.returncode==0,(args,p.stdout,p.stderr)

files=['architecture_tlm/process_28nm/'+n for n in (
    '250MHz/WHOLE_CONFIG.json','500MHz/WHOLE_CONFIG.json','SRAM_CALIBRATION_20261109.json',
    'SRAM_CHARACTERIZATION_RESULTS_ZH_20261109.md','SRAM_INTAKE_20261109_ZH.md','SRAM_INTAKE_20261109.json',
    'intake_sram.py','sram_characterization.py','whole_pricing.py','whole_model.py','run_whole.py',
    'README_ZH.md','WHOLE_MODEL_ZH.md')]
files+=['digital_circuit_simulation_registry/'+n for n in ('records/sram28-s0-225-20261109.json','catalog.json','00_总览.md','01_结果地址索引.md','runs.csv','artifact_locations.csv')]
files+=['work/rayggxia/225/sram28_intake_20261109/'+n for n in ('HANDOFF.md','finalize.py','registry_check.txt','registry_render.txt')]
files+=['progress/rayggxia/STATUS.md']
for name in files:
    p=ROOT/name
    if name.startswith('architecture_tlm/'):
        target=WS/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
# Preserve other unmerged registry records in the root reading union.
regname='digital_circuit_simulation_registry/records/sram28-s0-225-20261109.json'
(WS/regname).write_bytes((ROOT/regname).read_bytes())
catalog_path=WS/'digital_circuit_simulation_registry/catalog.json'
catalog=json.loads(catalog_path.read_bytes())
if record['id'] not in catalog['record_ids']:
    catalog['record_ids'].append(record['id']);catalog['as_of']=max(catalog['as_of'],record['registered_on'])
    dump(catalog_path,catalog)
p=subprocess.run([sys.executable,'-B',str(WS/'digital_circuit_simulation_registry/registry.py'),'check'],capture_output=True,text=True,encoding='utf8')
write(HERE/'root_registry_check.txt',p.stdout+p.stderr);assert p.returncode==0
p=subprocess.run([sys.executable,'-B',str(WS/'digital_circuit_simulation_registry/registry.py'),'render'],capture_output=True,text=True,encoding='utf8')
write(HERE/'root_registry_render.txt',p.stdout+p.stderr);assert p.returncode==0
dump(HERE/'PUBLIC_FILES.json',dict(files=[dict(path=n,sha256=sha(ROOT/n),content=(ROOT/n).read_text(encoding='utf8')) for n in files]))
subprocess.run(['git','-c','core.autocrlf=false','add','--sparse','--',*files],cwd=ROOT,check=True)
subprocess.run(['git','-c','core.whitespace=cr-at-eol,-blank-at-eof','diff','--cached','--check','--',*files],cwd=ROOT,check=True)
for n in files:assert hashlib.sha256(subprocess.check_output(['git','show',':'+n],cwd=ROOT)).hexdigest()==sha(ROOT/n)
print(json.dumps(dict(files=len(files),registry_pass=True,root_union_preserved=True,stage_SHA=True)))

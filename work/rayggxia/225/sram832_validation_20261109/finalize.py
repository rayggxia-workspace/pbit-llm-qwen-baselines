"""Publish only small integration sources, checks, and reproducible indexes."""
from pathlib import Path
import hashlib,json,subprocess,sys

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];WS=ROOT.parents[1]
P=ROOT/'architecture_tlm/process_28nm'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(s.encode())
def dump(p,x):write(p,json.dumps(x,ensure_ascii=False,indent=2)+'\n')

subprocess.run([sys.executable,'-X','utf8','-B',str(HERE/'collect.py')],cwd=ROOT,check=True)
x=json.loads((P/'SRAM832_VALIDATION_20261109.json').read_bytes())
chosen=[v for v in x['rows'] if v['capacity_KiB']==832]
assert len(chosen)==2
changes={z['clock_MHz']:z['time_change_pct'] for z in chosen}
coord=ROOT/'architecture_tlm/module_handoff/SRAM_REDUCTION_COORDINATION_ZH_20261109.md'
t=coord.read_text(encoding='utf8').replace('当前已启动独立冻结的小配对回放；完成情况见',
    '两频共四个独立冻结小流程已经完成并核验；250/500MHz相对同频960KiB分别增加'+f"{changes[250]:.4f}%/{changes[500]:.4f}%。完整范围见")
write(coord,t)
for n in ('README_ZH.md','WHOLE_MODEL_ZH.md'):
    p=P/n;v=p.read_text(encoding='utf8').replace('832KiB仅逻辑候选','832KiB已完成两频小配对，仍为候选')
    header='> 2026-11-09：宿主已独立完成832KiB两频小配对，见[验证结果](SRAM832_VALIDATION_20261109_ZH.md)。默认960KiB保持；[需其它模块确认的清单](../module_handoff/SRAM_REDUCTION_COORDINATION_ZH_20261109.md)。\n\n'
    if not v.startswith(header):write(p,header+v)
area=P/'AREA_SRAM_REVIEW_20261109_ZH.md'
v=area.read_text(encoding='utf8')
header='> 后续验证已完成：832KiB在两频小流程通过有限bank/工作量配对，详见[结果](SRAM832_VALIDATION_20261109_ZH.md)。下方“尚未回放”是审查建立时状态；容量默认仍960KiB。\n\n'
if not v.startswith(header):write(area,header+v)
note=f'''## 2026-11-09 SRAM缩减分工明确，832KiB两频小配对已由宿主确认

Issue225/PR249，rayggxia。用户无需先找其他对话；激活128→96KiB、八Attention48→36KiB均由宿主实现并实减bank240→208，前端144→136/Attention96→72。Qwen3-4B/B1/2K/K128/S64/GU16/Wd32，250三核两层+384head、500两核一层+384head，四case同冻源7a3335833c8f、单进程顺序完成。250原2.205336→2.208844ms(+{changes[250]:.4f}%)，500原.996176→{chosen[1]['time_ms']:.6f}ms(+{changes[500]:.4f}%)；不是完整token时间。

四SEAL/SHA、实际容量/端口/边界/排空、核帧/转换/尺度/采样/算术及外存字节/地址摘要配对通过；SRAM读量和bank冲突按实际调度保留。宏面积少.380164mm²；无15%面积口径下的28nm250/500容量预算6.758447/6.784987mm²，未把小流程周期变化外推为完整token。现默认960KiB不自动切换；55nm/其它模型/长上下文/原生LPDDR/完整36层未在本轮验证，无新RTL/PT/PPL。

正式process_28nm/SRAM832_VALIDATION_20261109_ZH.md/json、可选candidate_sram.py；对接清单module_handoff/SRAM_REDUCTION_COORDINATION_ZH_20261109.md。后续CIM驻留32→16槽/内外存归属向FFN确认；Attention只在推广其他配置时补最大活跃数据约定；S0已有数据，不需重跑SRAM PT。发布看本work/PUBLICATION，PR待审未合并，Projects待同步。
'''
status=ROOT/'progress/rayggxia/STATUS.md';old=status.read_text(encoding='utf8')
if not old.startswith(note):write(status,note+'\n---\n\n'+old)
write(HERE/'HANDOFF.md',note+'\n恢复：读PLAN与四SEAL，不重跑健康或已封存case。下一步如采用832，另做完整token/原生及55频率回放；当前无需将任务转给其他对话。\n')
a=WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';b=WS/'PROJECT_MEMORY_ZH.md'
old=a.read_bytes();assert old==b.read_bytes()
value=old if old.startswith(note.encode()) else (note+'\n---\n\n').encode()+old
assert a.read_bytes()==b.read_bytes()==old;a.write_bytes(value);b.write_bytes(value)

files=['architecture_tlm/process_28nm/'+n for n in ('candidate_sram.py','whole_model.py','run_whole.py',
    'SRAM832_VALIDATION_20261109.json','SRAM832_VALIDATION_20261109_ZH.md','README_ZH.md','WHOLE_MODEL_ZH.md','AREA_SRAM_REVIEW_20261109_ZH.md')]
files+=['architecture_tlm/module_handoff/SRAM_REDUCTION_COORDINATION_ZH_20261109.md']
files+=['work/rayggxia/225/sram832_validation_20261109/'+n for n in ('run_pairs.py','collect.py','finalize.py','PLAN.json','HANDOFF.md')]
files+=['progress/rayggxia/STATUS.md']
for name in files:
    if name.startswith('architecture_tlm/'):
        target=WS/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
dump(HERE/'PUBLIC_FILES.json',dict(files=[dict(path=n,sha256=sha(ROOT/n),content=(ROOT/n).read_text(encoding='utf8')) for n in files]))
subprocess.run(['git','-c','core.autocrlf=false','add','--sparse','--',*files],cwd=ROOT,check=True)
subprocess.run(['git','-c','core.whitespace=cr-at-eol,-blank-at-eof','diff','--cached','--check','--',*files],cwd=ROOT,check=True)
for name in files:assert hashlib.sha256(subprocess.check_output(['git','show',':'+name],cwd=ROOT)).hexdigest()==sha(ROOT/name)
print(json.dumps(dict(status='LOCAL_COMPLETE_MATCHED_PAIRS',files=len(files),timing_delta_pct=changes)))

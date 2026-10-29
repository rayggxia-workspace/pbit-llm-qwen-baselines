"""Persist a proposal and scope; never register it as a measured circuit."""
from pathlib import Path
import hashlib,json,math,shutil,subprocess,sys
H=Path(__file__).resolve().parent;R=H.parents[3];W=R.parents[1];A=W/'project_archives/matrix204_dual_plan_20261029';A.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepend(p,n):
 b=p.read_bytes()
 if n.splitlines()[0].encode() in b:return
 dst=A/('preimage_'+sha(p)+'.bin')
 if not dst.exists():dst.write_bytes(b)
 assert p.read_bytes()==b
 p.write_bytes(n.encode()+b)
def main():
 reg=R/'digital_circuit_simulation_registry';mirror=W/'digital_circuit_simulation_registry';before=[{p.name:sha(p) for p in (q/'records').glob('*.json')} for q in [reg,mirror]]
 names=['12_双随机分层矩阵架构评估计划.md','references/dual_stochastic_20261029/SOURCES.json']
 for n in names:
  src=reg/n;dst=mirror/n;dst.parent.mkdir(parents=True,exist_ok=True)
  if dst.exists() and sha(src)!=sha(dst):shutil.copyfile(dst,A/(sha(dst)+'_'+dst.name))
  shutil.copyfile(src,dst);assert sha(src)==sha(dst)
 # Small mathematical examples; not RTL, not a model test or new PPA run.
 events=[int((a+.5)/8<.5 and (b+.5)/4<.5) for a in range(8) for b in range(4)]
 assert sum(events)==8 and sum(4*z for z in events)==32
 assert (2048).bit_length()+1==13 and (512).bit_length()+1==11
 note='''## 2026-10-29 Issue204：双随机双轴分层架构分析（未启动EDA）

用户要求保持输入及权重各自共享尺度，思考两侧随机比特流、双分层（非DS-CIM互斥映射）及待评估模块。已只读核实PR207@05d7d986的尺度合同/dual_gu数值参考：x每64共享原四档PoT、W每64×64共享PoT LSB，码[-127,127]不变、pW=abs(q)/128；T32沿已有8×4联合格，非32²拍。原数值参考W按连接独立，硬件分组/列共享改变协方差，不能继承PPL。未修改Issue201/206源码、模型/尺度默认或运行其他任务。

方案入口digital_circuit_simulation_registry/12_双随机分层矩阵架构评估计划.md，论文与项目Git blob在references/dual_stochastic_20261029/SOURCES.json，根镜像两文件同字节。主候选一套signed popcount64+13位累计，OR4近似分支popdiff16+11位累计，均为每输出一个状态而非每权重位平面一套；9/10位饱和另验。双分层不会消除OR碰撞：4个相同pX=pW=.5共用二维点时，精确和1、OR4仅.25，手算/32格枚举一致，非新电路仿真。两侧SNG可拆高层判断/低5位边界比较；收益待测。必须计2D调度/真实抖动分发、X8/W7比较、驻留SRAM/ICG DFF、符号AND、归约/累计、组间PoT对齐舍入及M扩展广播，不能把旧69pJ除6当新功耗。

DS-CIM、DATE2017 Sobol、ICCAD2018 LD、uGEMM及Frontiers2023一手正文已读；原生方案与论文映射/条件推进不同。当前仅分析建议，不预设T32精度/能效，不新增run、无新RTL/PPA/模型/PPL，全部旧record字节不改。建议先同尺度/同事件数数值与共享拓扑消融、再功能和同PVT集成PPA；未自动启动这些后续实验。rayggxia，继续Issue204/PR209/task/204-bf16-baseline、复用原checkout；文稿本地完成，实际发布见DUAL_PLAN_PUBLICATION.json；PR待审未合并，Projects沿既有限制待维护者同步。

'''
 for p in [R/'PROJECT_MEMORY_ZH.md',W/'PROJECT_MEMORY_ZH.md',W/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md',R/'progress/rayggxia/STATUS.md',R/'work/rayggxia/204/HANDOFF.md',H/'HANDOFF.md']:prepend(p,note)
 nav='## 2026-10-29双随机分层架构讨论\n\n新增[12方案页](12_双随机分层矩阵架构评估计划.md)：保持共享尺度，T32/8×4，精确计数与OR4分开、共享相关性与前端/存储成本分开。仅方案、无新PPA/模型结果，不新增run。已测价格仍见11索引。\n\n'
 for q in [reg,mirror]:prepend(q/'README_ZH.md',nav)
 p=R/'architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md';n='\n\n## 2026-10-29 双随机双轴分层矩阵方案分析\n\nIssue204/PR209，[方案](../digital_circuit_simulation_registry/12_双随机分层矩阵架构评估计划.md)。保持现有共享尺度，双SNG/AND/单套累计；T32=8×4而非1024拍。精确signed popcount64+13位累计为参考，OR4+11位为独立近似；分层覆盖不提供OR互斥保证，连接独立与广播共享不等价。须计权重比较器、随机分发、SRAM读/保持、符号与尺度恢复；只读引用Issue201/206已有数值，不继承其模型精度。无新RTL/EDA/PPL、不新增run，后续实验未启动。\n'
 if n.splitlines()[2].encode() not in p.read_bytes():p.write_bytes(p.read_bytes()+n.encode())
 checks=[]
 for i,q in enumerate([reg,mirror]):
  result=subprocess.run([sys.executable,str(q/'registry.py'),'check'],capture_output=True,text=True,check=True);checks.append(json.loads(result.stdout))
  assert before[i]=={p.name:sha(p) for p in (q/'records').glob('*.json')}
 out=dict(date='2026-10-29',scope='Architecture analysis only; no new circuit/model execution or run',new_EDA=0,new_PPL=0,analytical_example=dict(T=32,grid=[8,4],products=4,each_pA=.5,each_pW=.5,single_product_count=sum(events),exact_sum_count=32,OR4_count=sum(events),exact_value=1,OR4_value=.25,direct_exact_state_bits=13,OR4_exact_state_bits=11),files=[dict(path=n,sha256=sha(reg/n),mirror_equal=sha(reg/n)==sha(mirror/n)) for n in names],records_unchanged=[len(x) for x in before],registry_checks=checks)
 (H/'DUAL_PLAN_VALIDATION.json').write_bytes((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())
 print(json.dumps(dict(mirror_files=2,records_unchanged=out['records_unchanged'],new_EDA=0,new_PPL=0)))
if __name__=='__main__':main()

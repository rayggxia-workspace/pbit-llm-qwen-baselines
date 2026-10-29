"""Persist SRAM-local comparison as primary architecture; no new PPA run."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
H=Path(__file__).resolve().parent;R=H.parents[3];W=R.parents[1];A=W/'project_archives/matrix204_dual_plan_20261029/sram_cim';A.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepend(p,n):
 b=p.read_bytes()
 if n.splitlines()[0].encode() in b:return
 d=A/('preimage_'+sha(p)+'.bin')
 if not d.exists():d.write_bytes(b)
 assert p.read_bytes()==b;p.write_bytes(n.encode()+b)
def main():
 names=['12_双随机分层矩阵架构评估计划.md','13_SRAM存内比较估算口径与证据.md'];mirrors=[]
 for n in names:
  p=R/'digital_circuit_simulation_registry'/n;q=W/'digital_circuit_simulation_registry'/n
  if q.exists():shutil.copyfile(q,A/(sha(q)+'_'+q.name))
  shutil.copyfile(p,q);assert sha(p)==sha(q);mirrors.append(dict(path=n,sha256=sha(p),mirror_equal=True))
 nav='## 2026-10-29 SRAM存内比较估算延续\n\n[13口径与证据](13_SRAM存内比较估算口径与证据.md)说明SRAM驻留/局部比较主架构及旧宏库、数字前端、带载接口三层估算；[12](12_双随机分层矩阵架构评估计划.md)同步主方案。只核对已有证据，无新CIM PPA或新增run。\n\n'
 for root in [R,W]:prepend(root/'digital_circuit_simulation_registry/README_ZH.md',nav)
 note='''## 2026-10-29 Issue204：用户要求继续SRAM存内比较主架构

双随机结构继续SRAM驻留、本地SNG并行比较，阵列输出随机权重bit；不默认搬整组权重到DFF，不默认每采样走普通窄口完整读。两颗全局LFSR32（输入一颗/权重一颗）、T32/8×4与原共享尺度保持；P8输入/P7权重各需5位抖动。ICG DFF及普通宏预读保持仅作对照。已更新12方案页，新增13_SRAM存内比较估算口径与证据.md并同字节同步根阅读镜像。

历史框架可以延续：真实宏库/尺寸/面积/保持与装载＋SRAM邻近标准单元SNG/驱动表征＋存储节点带载接口增量。旧四32×144宏2.25KiB、576bit预读Q保持不是完整64×64存内比较；S0–S5保持/读写有原件但CE关闭动态缺表/hold/XZ边界限制保留。Issue146实际N64/M1/seed17/T32数字前端SS100MHz115.3µW、340ns/39.202pJ，含一颗LFSR/输入比较/固定W门控，不含物理SRAM，功耗表告警保留；不可直接当新W-SNG价格。真实定制存储位/位线比较尚未表征；新最小探针应是7幅值存储位+W7比较/必要隔离，旧模板只有bitcell/AND/BUF。不能将缺接口能量填0，或每拍重复收费全普通读；按真实本地模式收费。普通宏外围也不能任意扣除成裸cell成本。

只读核实Issue146与本机原件；旧source508bdaa4当前workspace GitHub ref404，未伪造远端可见、不重跑/接管其任务。源码/证据阅读SHA见SRAM_CIM_VALIDATION.json。rayggxia继续Issue204/PR209/task/204-bf16-baseline，源基线06b14a96fef58533c5af85851a2a6eae17d07aee；本轮仅合同/历史证据整理，无新RTL/EDA/SPICE/PPL，不新增run，完整根union保留。实际发布见SRAM_CIM_PUBLICATION.json，PR待审未合并、Projects待维护者同步。

'''
 for p in [R/'PROJECT_MEMORY_ZH.md',W/'PROJECT_MEMORY_ZH.md',W/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md',R/'progress/rayggxia/STATUS.md',R/'work/rayggxia/204/HANDOFF.md',H/'HANDOFF.md']:prepend(p,note)
 old=W/'tmp/cim-frontend-issue146-20261023';paths=[old/'architecture_tlm/sc_cim_frontend_20261023/README_ZH.md',old/'architecture_tlm/sc_cim_frontend_20261023/sram_probe/cell_load.sp.template',old/'work/jieruiz/146/HANDOFF.md',W/'architecture_tlm/SRAM_PT_CHARACTERIZATION_ANSWERS_ZH_20261016.txt']
 reads=[dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size,access='read_only_local_historical_evidence') for p in paths]
 checks=[]
 for root in [R,W]:
  reg=root/'digital_circuit_simulation_registry';before={p.name:sha(p) for p in (reg/'records').glob('*.json')}
  x=subprocess.run([sys.executable,str(reg/'registry.py'),'check'],capture_output=True,text=True,check=True)
  assert before=={p.name:sha(p) for p in (reg/'records').glob('*.json')};checks.append(dict(records_unchanged=len(before),check=json.loads(x.stdout)))
 out=dict(date='2026-10-29',owner='rayggxia',issue=204,source_base='06b14a96fef58533c5af85851a2a6eae17d07aee',user_selected_architecture='SRAM-resident binary weights/local parallel SNG comparison primary; ICG DFF only comparison',read_only_sources=reads,mirror_files=mirrors,registry=checks,new_EDA=0,new_SPICE=0,new_PPL=0,old_source_ref_access='workspace GitHub508bdaa4 not found; local archive evidence retained',limits='No new SRAM-CIM physical validation; old scalar front-end and ordinary macro prices retain original boundary and warnings')
 (H/'SRAM_CIM_VALIDATION.json').write_bytes((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())
 print(json.dumps(dict(mirror_files=2,records_unchanged=[r['records_unchanged'] for r in checks],new_EDA=0)))
if __name__=='__main__':main()

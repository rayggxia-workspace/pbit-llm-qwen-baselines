"""Preserve memory history and publish the INT8 result plus area audit."""
from pathlib import Path
import hashlib,json,shutil
HERE=Path(__file__).resolve().parent;R=HERE.parents[3];W=R.parents[1];A=W/'project_archives/matrix204_int8_classic_ppa_20261028'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 s=json.loads((R/'architecture_tlm/int8_classic_ppa_20261028/results/FINAL_SUMMARY.json').read_text(encoding='utf-8'));by={x['case']['AW']:x for x in s['PPA']};x=by[32];y=by[22]
 note='''## 2026-10-28 Issue204：经典INT8本工艺结果及SC面积质疑复核

rayggxia，task/204-bf16-baseline / PR209接续，基线6435de8854d8ddb93375e03085ed1eea9c3f9002，复用tmp/matrix-t32-issue204-20261028。用户明确要求按成熟参考计算INT8，随后质疑“无论怎样SC面积肯定更小”；已核查源/映射库存，不根据期待反改结果。入口architecture_tlm/int8_classic_ppa_20261028/results/REPORT_ZH.md、AREA_EXPLANATION_ZH.md及完整SUMMARY。

经典四lane signed8×8→16位乘积寄存→17/18位平衡归约→输出驻留累加；INT32主参考和固定N64无bias精确INT22。一帧64项点积一个输出，不是64×64全矩阵。三seed216完整帧+6 reset中断功能与对应门级通过，18PT窗口全映射leaf/端口活动核验；matched48帧来自BF16原INT8派生数据，整数结果/128与BF16/FP32逐位同值。无新模型/PPL。

SS1.08V125℃100MHz：INT32 raw3825.36µm²、等效0.003098542mm²、0.2151mW、40.869pJ/帧；INT22 raw3621.96µm²、等效0.002933788mm²、0.207mW、39.330pJ。正常18拍valid/19拍帧间隔=180/190ns；位宽收缩省5.32%面积/3.77%能量，不截断有效结果。setup/hold分别3.082494/.082897ns与3.299786/.082897ns，parser未列警告。前布局无CTS/SDF/SPEF，不是物理签核。

面积复核：SC54寄存器77个/449.064µm²，组合1860个/5075.006µm²，总5524.070µm²；INT32寄存器109个/785.279µm²，组合793个/2313.263µm²，总3098.542µm²，全部已乘.81一次。SC寄存器更小但六平面并行符号/OR/计数/累加/恢复组合网络更大；整数只4个乘法器复用16拍。两核都未放整组权重/概率存储，未发现因漏权重DFF或双乘.81导致排序。旧64路全并行INT8约0.04621mm²确实比SC大，但20ns帧间隔不同；N64问题长度不等于物理并行度，不能宣布SC所有实现必然更小，也不把当前SC54称面积下界。

当前粗比SC54相对四路INT32面积1.78倍、能量1.70倍、帧间隔1.84倍，不能支持相对INT8已有巨大优势。对同批数值BF16556.2pJ参考，INT32能量低13.61倍、面积低14.50倍。SC输入/近似精度不同；SRAM、供数、随机源、格式与广播/时钟边界未闭合，不宣布整片胜负。未来可优化SC符号/计数路径，但需独立质量与PPA，不因用户直觉覆盖负结果。

v1/v2门级X失败保留，v2去重定时仍失败，故不能归因于重定时本身。波形定位同步reset时控制计数LSB停留X；v3真实异步控制reset、同步sum、valid保护无reset产品寄存，v4相同电路强化四态ready/valid拒收后完成门级/PPA。数据delay1/.02ns、slew.05、load20fF、uncertainty.5/.05；reset下降沿附近4.5..5.5ns释放与BF16补充契约相同，未加false/multicycle、未force初值、未改库模型。最终set_fix_hold core后compile_ultra，不重定时。

4执行ZIP/14报告/42传输文件和成员SHA核验，配置/SDC/库模型指纹单列EXECUTION_FINGERPRINTS；准确作业见RUN_LEDGER。v4 manifest6523fbde32b9d8cad460f09f1ccf9892466788071fc20aa37a931d86d507255f。实际执行为base6435de88+未提交冻结快照，不伪造执行提交。原件project_archives/matrix204_int8_classic_ppa_20261028，本轮无运行作业；私有控制器不发布。

中央run matrix-int8-classic-204-20261028，任务/完整根镜像各自增量union check/render，准确数见REGISTRY_CHECK。旧record字节保留，不用任务子集覆盖全镜像；本run所有产物可访问，旧94路径仍不可访问。源码/报告已准备，实际发布提交/回读和PR状态查同目录PUBLICATION.json；待审未合并、Issue保持open，Projects工具不支持写待维护者同步。

'''
 pre=[]
 for p in [R/'PROJECT_MEMORY_ZH.md',W/'PROJECT_MEMORY_ZH.md',W/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md',R/'progress/rayggxia/STATUS.md',R/'work/rayggxia/204/HANDOFF.md']:
  raw=p.read_bytes()
  if note.splitlines()[0].encode() in raw:continue
  h=hashlib.sha256(raw).hexdigest();dst=A/('preimage_'+h+'.bin')
  if dst.exists():assert dst.read_bytes()==raw
  else:dst.write_bytes(raw)
  assert p.read_bytes()==raw,'Concurrent memory edit'
  p.write_bytes(note.encode()+raw);pre.append(dict(path=str(p),previous_sha256=h,archive=str(dst)))
 p=HERE/'HANDOFF.md';raw=p.read_bytes();(A/('preimage_'+hashlib.sha256(raw).hexdigest()+'.bin')).write_bytes(raw)
 p.write_bytes((note+'恢复先核实Issue204/PR209最新head和本目录PUBLICATION，再读RESULTS及RUN_LEDGER。所有EDA已结束，不重交；init.py为v1历史引导，不在冻结树重跑。新实验必须新目录快照，保留旧失败。源模型/语料N/A。下一步是审核、匹配存储/精度/并行度及SC逻辑优化，不自动启动模型或额外EDA。\n').encode())
 regnote='## 2026-10-28 Issue204：经典INT8 DOT4与面积复核\n\n新增run matrix-int8-classic-204-20261028：2配置/18PT窗口，INT32主参考40.869pJ/190ns/等效0.003098542mm²，INT22为39.330pJ/0.002933788mm²；时序均非负。SC54与四路整数的映射单元面积复核见architecture_tlm/int8_classic_ppa_20261028/results/AREA_EXPLANATION_ZH.md。任务分支66、当前完整根镜像87条，原65/86个record字节保留；无模型/PPL或物理签核。\n\n'
 for p in [R/'digital_circuit_simulation_registry/README_ZH.md',W/'digital_circuit_simulation_registry/README_ZH.md']:
  if regnote.splitlines()[0].encode() not in p.read_bytes():p.write_bytes(regnote.encode()+p.read_bytes())
 p=R/'architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md';addition='\n\n## 2026-10-28 经典INT8折叠DOT4与SC面积审计\n\nIssue204/PR209；[正式结果](int8_classic_ppa_20261028/results/REPORT_ZH.md)、[面积复核](int8_classic_ppa_20261028/results/AREA_EXPLANATION_ZH.md)。2配置/18窗口，INT32与N64精确INT22；同BF16派生数值比较，SC当前核更大的组合逻辑与四路数字时分复用均明确，不按AND直觉改面积。中央run matrix-int8-classic-204-20261028；v1/v2映射X失败保留、v4真实控制reset验证。无新模型/PPL、存储与物理签核。\n'
 if addition.splitlines()[2].encode() not in p.read_bytes():p.write_bytes(p.read_bytes()+addition.encode())
 private=A/'private_control';private.mkdir(exist_ok=True)
 for n in ['int8_server.py','debug_int8_vcd.py']:
  src=R/'work/rayggxia/204/private'/n;shutil.copyfile(src,private/n)
 validation=dict(owner='rayggxia',issue=204,source_base=s['source_base'],source_manifest_sha256=s['execution_source_manifest_sha256'],memory_preimages=pre,model_corpus='N/A, synthetic circuit-only; no inference or training',source_packages=4,report_archives=14,transfers_verified=42,PT_windows=18,RTL_frames=216,gate_frames=216,reset_aborts_per_stage=6,new_run_artifacts_unavailable=0,private_control_archive=[dict(path=str(private/n),sha256=sha(private/n)) for n in ['int8_server.py','debug_int8_vcd.py']],configuration_and_library_fingerprints=dict(path=str(A/'EXECUTION_FINGERPRINTS.json'),sha256=sha(A/'EXECUTION_FINGERPRINTS.json')),publication='Read PUBLICATION.json for actual remote receipt')
 (HERE/'VALIDATION.json').write_bytes((json.dumps(validation,ensure_ascii=False,indent=2)+'\n').encode())
 print('DELIVERY_READY',len(pre),'preimages')
if __name__=='__main__':main()

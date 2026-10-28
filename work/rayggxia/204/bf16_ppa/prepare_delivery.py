"""Update own progress/memory by prepend; archive each distinct preimage."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;R=HERE.parents[3];W=R.parents[1];A=W/'project_archives/matrix204_bf16_ppa_20261028'
def main():
 s=json.loads((R/'architecture_tlm/bf16_ppa_20261028/results/FINAL_SUMMARY.json').read_text(encoding='utf-8'));d=next(x for x in s['PPA'] if x['case']['name']=='dot64_4');p=d['profiles']['normal'];z=d['reset_contract_sta']
 note='''## 2026-10-28 Issue204：成熟BF16本工艺N64 PPA完成，INT8经典划分已核对

rayggxia，task/204-bf16-baseline / PR209接续，源起点99bf019c。用户明确要求按经典流水划分做本工艺PPA，再查INT8；这是新授权，已实际运行EDA，不沿用上轮“无EDA”的历史结论。复用tmp/matrix-t32-issue204-20261028，未接管Issue107。结果入口architecture_tlm/bf16_ppa_20261028/results/REPORT_ZH.md、FINAL_SUMMARY.json及INT8_CLASSIC_ZH.md。

CVFPU77811635/common_cells9afda9ab精确上游，BF16×BF16/FP32乘加及独立乘/加；四lane非融合DOT4树+四FP32交错上下文，N64正常29拍valid、帧间隔30拍=300ns。五top45个三seed窗口、27696标量+108整帧功能比较及对应门级回放已完成；48个INT8派生帧另用Fraction精确点积核验。合成数据，无模型/PPL；不称单轮舍入fusedDOT4或最佳生产矩阵引擎。

N64原始面积%.2fµm²，raw×0.81等效%.6fmm²，normal平均%.6fmW、%.3fpJ/完整64项点积；INT8派生输入%.3fpJ。相对SC54(0.005524mm²/69.4633pJ/350ns)约%.2f倍面积、%.2f倍能量，SC帧间隔长16.67%%。这是异精度/不同合成激励的计算核对照，不能宣称整片或同质量优势；既有INT822.19/38.80pJ仍比SC省能。

原共享reset0.02..1ns约束导致async removal负余量。相同SHA网表补充STA明示下降沿附近4.5..5.5ns释放，数据约束不变、无false/multicycle，N64setup/hold %.6f/%.6fns；四独立标量en→valid仍−0.061165ns hold，未修复。功耗表范围、高扇出和极小setup余量保留；无CTS/SDF/SPEF或复位分配实装，不称物理签核。

v1..v7负结果/源包/原始报告保留，原字节、远端SHA和全部报告成员核验。v6标量完整，v6 N64仅TB time变量裁剪失败；v7只修波形裁剪并核验全部RTL/bench/fixture/库绑定/约束后复用相同网表，未重综合。补充STA独立冻结。执行是base99bf019c+uncommitted快照，后续源码提交需按ZIP逐字绑定，不伪造执行提交。准确批次见work/rayggxia/204/bf16_ppa/RUN_LEDGER.json；本轮作业已结束，不重交。

中央run matrix-bf16-204-20261028；分支与根镜像分别向各自最新record集合增量登记，旧record字节均保留，绝不用分支子集覆盖完整镜像。准确数量、check/render及原件校验见REGISTRY_CHECK.json。源码/报告准备完毕；实际推送提交和PR状态以同目录PUBLICATION.json为准，PR待审未合并、Issue不关闭，Projects沿既有限制待维护者同步。

INT8经典实现采用signed8×8→16位积，output-stationary INT32反馈累加，或DOT4/8平衡树后累加；固定N64无bias最坏范围可用22位精确，但可复用长K/带bias经典基线应保留32位，再把22位列独立消融。Gemmini/NVDLA一手源码/文档已核查；推荐100MHz先用乘法级+累加级，是否树内增级交STA决定，无新INT8 PPA冒称。

'''%(d['raw_area_um2'],d['area_55eq_um2']/1e6,p['total_W']*1000,p['energy_pJ'],d['profiles']['int8']['energy_pJ'],d['area_55eq_um2']/5524.0704,p['energy_pJ']/69.4633333333,z['setup_slack_ns'],z['hold_slack_ns'])
 pre=[]
 paths=[R/'PROJECT_MEMORY_ZH.md',W/'PROJECT_MEMORY_ZH.md',W/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md',R/'progress/rayggxia/STATUS.md',R/'work/rayggxia/204/HANDOFF.md']
 for path in paths:
  raw=path.read_bytes()
  if note.splitlines()[0].encode() in raw:continue
  h=hashlib.sha256(raw).hexdigest();dst=A/('preimage_'+h+'.bin')
  if dst.exists():assert dst.read_bytes()==raw
  else:dst.write_bytes(raw)
  path.write_bytes(note.encode()+raw);pre.append(dict(path=str(path),previous_sha256=h,archive=str(dst)))
 handoff=note+'''恢复：先核实Issue204/PR209最新状态与身份/分支，再读本目录PUBLICATION、RUN_LEDGER和architecture_tlm/bf16_ppa_20261028/results。所有原件在project_archives/matrix204_bf16_ppa_20261028，中央record指稳定归档。私有连接/控制器在work/rayggxia/204/private，不能发布。不得重复已完成EDA；若做算术或约束变化必须新快照。无遗留健康作业待取消。下一步是评审结果、匹配精度/供数INT8对照及真实时钟/复位/存储成本，不自动运行新模型。
'''
 old=HERE/'HANDOFF.md';raw=old.read_bytes();h=hashlib.sha256(raw).hexdigest();(A/('preimage_'+h+'.bin')).write_bytes(raw);old.write_bytes(handoff.encode())
 log=R/'architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md';addition='\n\n## 2026-10-28 成熟BF16本工艺表征与INT8经典划分\n\nIssue204/PR209；[完整结果](bf16_ppa_20261028/results/REPORT_ZH.md)、[INT8划分](bf16_ppa_20261028/INT8_CLASSIC_ZH.md)。五top/45PT窗口；N64四lane非融合DOT4实际计入启动/反馈/收尾，classic FMA流水参数不代替完整帧验证。源与原件统一登记matrix-bf16-204-20261028。复位释放契约另做同网表STA，原始失败与标量hold负余量保留；不称物理签核或同质量全芯片优势。无新模型/PPL。\n'
 if addition.splitlines()[2].encode() not in log.read_bytes():log.write_bytes(log.read_bytes()+addition.encode())
 save=dict(owner='rayggxia',issue=204,source_base=s['source_base'],source_manifest_sha256=s['execution_source_manifest_sha256'],memory_preimages=pre,model_corpus='N/A synthetic circuit-only, no model inference',validation=['VCS RTL and mapped replay','45 strict full-mapped PT windows','independent exact48 INT8-derived frame check','source/report remote/local and member SHA','registry task/full-union check/render, exact counts in REGISTRY_CHECK.json'],publication='pending; read PUBLICATION.json for actual receipt',primary_gemmini_sources=[dict(path=str(A/n),sha256=hashlib.sha256((A/n).read_bytes()).hexdigest(),commit='8c3f9923a44a2fe2c7930587be297d6d4f8c09ca') for n in ['Gemmini_PE.scala','Gemmini_README.md']])
 (HERE/'VALIDATION.json').write_bytes((json.dumps(save,ensure_ascii=False,indent=2)+'\n').encode())
 print('PREPARED_DELIVERY',len(pre),'preimages')
if __name__=='__main__':main()

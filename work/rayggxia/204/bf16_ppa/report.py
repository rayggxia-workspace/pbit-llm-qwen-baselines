"""Render verified PPA and interpretation; no raw result rewriting."""
from pathlib import Path
import json
R=Path(__file__).resolve().parents[4];P=R/'architecture_tlm/bf16_ppa_20261028'
def main():
 s=json.loads((P/'results/FINAL_SUMMARY.json').read_text(encoding='utf-8'));by={r['case']['name']:r for r in s['PPA']};dot=by['dot64_4'];p=dot['profiles']['normal'];pi=dot['profiles']['int8']
 lines=['# 成熟BF16本工艺前布局PPA', '',
 'Issue204 / PR209；rayggxia，2026-10-28。用户明确授权按经典划分表征成熟BF16，再核对INT8经典结构。本轮实际完成CVFPU/FPnew四个算术top及常规四lane N64整核的综合、门级逐结果回放和45个PT窗口。执行的源码、配置和合成激励由不可覆盖ZIP及manifest绑定，不将后续Git提交伪称执行时提交。', '',
 '统一SS1.08V/125℃/100MHz，数据I/O最大/最小延迟1/0.02ns，输出负载20fF，setup/hold uncertainty0.5/0.05ns。下列面积已按用户约定只乘一次0.81，原始库面积另列；功耗、能量和时间不缩放。前布局无CTS/SDF/SPEF。', '',
 '| 单元 | 原始面积 µm² | 55nm等效面积 µm² | normal功率 mW | normal能量 pJ/次 | int8命名窗口 pJ/次 |', '|---|---:|---:|---:|---:|---:|']
 for n in ['mul1','add2','fma2','fma3','dot64_4']:
  x=by[n];q=x['profiles']['normal'];iq=x['profiles']['int8'];lines.append('| %s | %.2f | %.2f | %.6f | %.5f | %.5f |'%(n,x['raw_area_um2'],x['area_55eq_um2'],q['total_W']*1000,q['energy_pJ'],iq['energy_pJ']))
 lines+=['', '**操作单位不同：前四项为一次标量运算，dot64_4为64对输入的完整点积。** 标量一窗1024操作加12拍排空；N64一窗16帧，逐帧真实启动、输入、排空、最终归约和间隔均计入，300ns/帧。功率是该完整窗口均值，能量=P×窗口时长÷完成次数，含泄漏及自由时钟成本。不是把标量结果乘64。idle和三seed结果见FINAL_SUMMARY.json；idle功耗不从主表扣除。', '',
 '成熟算术源来自openhwfoundation/cvfpu@77811635、pulp-platform/common_cells@9afda9ab(v1.38.0)，随附许可证。BF16对应FP16ALT，乘法输入BF16，乘积/累加/输出FP32，round-to-nearest-even；NaN按类别检查，不规定payload，异常状态旗未接出。使用原生FMA多格式单元并常量专用化；DC compile_ultra -retime。PIPES2/3是上游流水寄存器配置，不声称手工均分后的每段物理结构或生产最佳矩阵引擎。', '',
 '经典划分可按“分类/指数与8×8有效数乘积→对齐与加减→前导零检测、规格化和舍入”理解，但具体级边界以综合与STA为准。BF16乘积最多16位有效数，FP32加法仍要支持24位有效数及指数对齐；因此FP32 add成本明显，不能只以8×8整数乘法估BF16累加成本。', '',
 'N64整核为4个BF16乘法器、两级平衡FP32归约树、一个FP32反馈加法器和4×32位交错部分和上下文；每拍接收4对数，共16拍。四上下文轮转避开流水反馈相关，随后复用树做最终归约，启动到valid正常29拍=290ns，连续帧间隔30拍=300ns；4个带输入间隙的定向帧为35拍。**这是一套非融合DOT4，每个FP32加法都独立舍入，不是一次舍入的fused DOT4。** 权重和输入作为外部流每拍送4对，本核没有假定免费64组寄存器或已测SRAM。', '',
 '| 单元 | 原始setup ns | 原始min ns（含复位） | 下降沿释放契约setup ns | 契约min ns |', '|---|---:|---:|---:|---:|']
 for n in ['mul1','add2','fma2','fma3','dot64_4']:
  x=by[n];z=x['reset_contract_sta'];lines.append('| %s | %.6f | %.6f | %.6f | %.6f |'%(n,x['raw_setup_slack_ns'],x['raw_hold_slack_ns'],z['setup_slack_ns'],z['hold_slack_ns']))
 lines+=['', '原统一约束把rst_n也设为上升沿后0.02..1ns变化。最差min路径实际是异步复位释放的removal check，不应含糊称为正常数据hold失败，更不能删除原失败。补充STA对**相同SHA网表**明示rst_n在上升沿后4.5..5.5ns释放（对应测试台下降沿），其余数据/负载/时钟约束不变；未加false path或multicycle，recovery/removal仍检查。这是外部复位释放要求；复位同步器/分配网络未实现，不能宣称签核完成。N64契约下setup/hold非负，但setup余量只有0.000027ns，不能外推布局后频率。四个独立标量仍有en输入直达valid DFF的−0.061165ns hold，不把它们写成完整时序通过。', '',
 'FP32 add及N64保留checks.rpt中的功耗表输入slew范围警告；原报告打印精度会将边缘值同显为0.02ns，不据此忽略警告。N64综合另有clk/rst高扇出提示（1763 loads），尚未插入真实时钟/复位网络。能耗仍属有上述限制的前布局估算。', '',
 'N64三seed normal %.3f±%.3fpJ/帧，INT8派生输入%.3f±%.3fpJ/帧；面积%.6fmm²。SC54历史核为%.6fmm²、69.4633pJ/35拍350ns。就这些计算核粗比，BF16面积为SC的%.2f倍、normal能量为%.2f倍，SC帧间隔比BF16长%.2f%%。'%(p['energy_pJ'],p['energy_std_pJ'],pi['energy_pJ'],pi['energy_std_pJ'],dot['area_55eq_um2']/1e6,.0055240704,dot['area_55eq_um2']/5524.0704,p['energy_pJ']/69.4633333333,(350/300-1)*100), '',
 '这支持“相对本BF16参考，SC计算核有面积/能量优势且速度同量级”的有限结论；不能当同精度全芯片优势。两侧激励不同，SC含T32/OR4近似、7位幅值及预解码边界；BF16的指数范围/舍入精度明显更高。SRAM、随机源、格式/量化前后端、广播线和真实Instruct质量均未闭合。此DOT4封装也未穷尽融合点积、共享对齐、CSA/kulisch、输出驻留和时钟门控优化。与28nm MFSA的异工艺文献结果保留独立，不能挑本参考较高的能耗宣称所有成熟数字电路都有同样差距。', '',
 '尤其不能忽略既有INT8：全并行22.1867pJ/20ns、位串行38.7967pJ/100ns，都低于SC54的69.4633pJ。它们接口/激励仍有差别，下一步应建立精度与数据供应匹配的经典INT8对照，而不是把BF16优势直接外推到INT8。', '',
 '功能：冻结v6四标量×3seed×2308=27696次输出比较，N64三seed×36=108帧；相同门级再回放上述事务/帧。包含特殊值、非正规数、随机有效数、间隙和N64收尾。另独立Fraction检查48帧INT8派生输入，完整N64结果与数学精确点积逐位相等；不是模型精度验证。全45窗口映射leaf/端口活动严格核验100%，不采用未知活动默认值补叶子引脚。', '',
 '历史失败均保留：v1默认Python2；v2 VCS timescale；v3模板替换污染成功标记；v4 DC不支持常量函数clog2形参；v5 DC不支持宏默认参数；v6只显式化33个寄存器宏的原默认clk/reset，未改浮点算法。常量函数等价循环已用65536值对照。COMPATIBILITY_PATCHES.json绑定原/补丁SHA，UPSTREAM.json绑定精确版本。旧限制许可的common_cells下载仅保留本地历史，不发布该版本源码。', '',
 '源码包/原始报告在授权project_archives/matrix204_bf16_ppa_20261028，FINAL_SUMMARY列原字节与成员SHA；中央记录matrix-bf16-204-20261028。失败版本、多副本和重复功能回放不重复算作新架构实验。驱动内dot64_4的operation_definition文字误写scalar，派生摘要明确更正为一整帧，数值单位/能量未受影响。无新模型/语料/PPL，相关字段N/A。', '',
 'INT8经典划分的独立核查见[INT8_CLASSIC_ZH.md](../INT8_CLASSIC_ZH.md)，流程与恢复见work/rayggxia/204/bf16_ppa/HANDOFF.md。']
 lines+=['','标量活动说明：FMA/mul的int8窗口仅A/B为INT8派生BF16，FMA的C仍为随机FP32；add2的A未使用，其B/C在两个活动窗口都为随机FP32，所以int8只是该加法窗口的名字，不能作为INT8整数加法或精度切换消融。N64的int8窗口另为明确的INT8派生输入，48帧精确点积核验有效。见METADATA_CLARIFICATIONS.json；原始数值和归档字节未改。']
 (P/'results/REPORT_ZH.md').write_bytes(('\n'.join(lines)+'\n').encode())
 (P/'README_ZH.md').write_bytes(('# BF16成熟算术与N64本工艺结果\n\n最新入口：[结果与口径](results/REPORT_ZH.md)、[完整数值与原件索引](results/FINAL_SUMMARY.json)、[INT8经典划分](INT8_CLASSIC_ZH.md)。\n\nCVFPU与common_cells精确提交及许可见UPSTREAM.json、vendor/；两处DC2018等价兼容改动见COMPATIBILITY_PATCHES.json。冻结执行manifest保留原字节。fixtures由prepare.py、work/rayggxia/204/bf16_ppa/prepare_matrix.py生成并存在源ZIP；重新生成后必须重施记录的兼容补丁，不能把原冻结目录当可变实验目录。\n\n本轮为前布局综合/门级/PT及单独复位契约STA，不是布局签核或芯片实测；未运行模型推理/PPL。\n').encode())
 print('REPORT_WRITTEN')
if __name__=='__main__':main()

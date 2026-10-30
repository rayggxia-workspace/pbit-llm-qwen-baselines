"""Render verified classic INT8 metrics and matched BF16 comparison."""
from pathlib import Path
import json
R=Path(__file__).resolve().parents[4];P=R/'architecture_tlm/int8_classic_ppa_20261028'
def main():
 s=json.loads((P/'results/FINAL_SUMMARY.json').read_text(encoding='utf-8'));b=s['BF16_reference'];by={x['case']['AW']:x for x in s['PPA']};a=by[32];n=by[22]
 lines=['# 经典INT8 DOT4的本工艺结果','',
 'Issue204/PR209；rayggxia，2026-10-28。用户要求在成熟结构参考下实际计算INT8，接续已完成BF16的同工艺表征。这里参考Gemmini的局部输出驻留、NVDLA的乘法归约与部分和分离原则，实现小型N64/M1核心；不是完整移植两套系统，也未声称最佳整数引擎。', '',
 '统一SS1.08V125℃100MHz，input delay max/min1/.02ns、input slew.05ns、output load20fF、setup/hold uncertainty.5/.05ns。下表面积已单次乘0.81，原始库面积另列；功率、能量和时间不缩放。**一帧=64项点积、产生一个输出，不是完整64×64矩阵。**', '',
 '| 核心 | raw面积 µm² | 55nm等效面积 mm² | matched平均功率 mW | matched能量 pJ/帧 | fullrange pJ/帧 | 结果延迟/帧间隔 ns |', '|---|---:|---:|---:|---:|---:|---:|']
 for aw in [32,22]:
  x=by[aw];p=x['profiles']['matched'];lines.append('| INT8 DOT4 / INT%d | %.2f | %.6f | %.6f | %.4f | %.4f | %.0f / %.0f |'%(aw,x['raw_area_um2'],x['area_55eq_um2']/1e6,p['total_W']*1000,p['energy_pJ'],x['profiles']['fullrange']['energy_pJ'],x['normal_latency_cycles']*10,p['cycles_per_operation']*10))
 lines+=['| BF16/FP32同数据历史核 | 55454.76 | %.6f | %.6f | %.4f | 未测同批fullrange | 290 / 300 |'%(b['area_55eq_um2']/1e6,b['matched_BF16_power_W']*1000,b['matched_BF16_energy_pJ']), '',
 'matched每seed16帧，三seed48帧，逐元素来自BF16 v7的INT8派生输入：x=整数X/128、W∈[-127,127]。整数核计算ΣXW，其结果除128与旧BF16/FP32结果逐位相同。输入映射与原始stim/expect SHA见INPUT_REFERENCE.json，matched_inputs.json使本次生成不再依赖旧checkout的临时fixture。此比较是同一批数值在两种表示下的计算核成本，不是完整模型重新量化质量验收。', '',
 'fullrange是另外每seed16帧signedINT8均匀合成数据，并在活动窗口强制含−128×−128。4个定向极值帧另验证最大/最小/全127/零，不混进功耗窗口。主能量按P×窗口时长÷完成帧数计算，含启动、16拍输入、排空、帧间隔、泄漏和自由时钟；idle功耗不从主表扣除。三seed误差和分量见FINAL_SUMMARY.json。', '',
 '数据通路：四个signed8×8乘法器→64位乘积寄存器组→两两17位和→18位组和→AW位部分和反馈。输出直接来自部分和寄存器，22位版本对外符号扩展成32位，不另放结果副本。控制为异步reset，累加器为同步reset；乘积寄存器由valid保护、无reset；CE保持不等于ICG。复位释放要求上升沿后4.5..5.5ns，对应测试台下降沿，与BF16补充STA契约一致；数据约束不变，无false/multicycle路径，recovery/removal正常检查。编译优化保留所描述算术功能，RTL与映射后逐帧验证周期/输出。', '',
 '完整signed8乘积范围−16256..16384，64项和范围−1040384..1048576。21位正最大1048575，无法覆盖后一极值，因此固定N64无bias的精确最小通用宽度为22位。INT32保留经典长K/跨tile/bias扩展余量；本模块仍固定N64，不把它宣称已经验证任意K。两个版本都不截断、饱和或回绕有效N64结果。', '',
 '| 核心 | setup slack ns | hold slack ns | 活动覆盖 | 保留告警 |', '|---|---:|---:|---|---|']
 for aw in [32,22]:
  x=by[aw];lines.append('| INT%d | %.6f | %.6f | 所有映射端口/leaf100%% | %s |'%(aw,x['setup_slack_ns'],x['hold_slack_ns'],','.join(x['review_flags']) or '无parser所列告警'))
 lines+=['',
 'v1启用重定时后首帧门级产生X，两个版本均拒收；v2取消重定时仍同样失败，因此重定时不是充分解释。波形显示accepted/returned最低位在同步reset有效期间仍为X，随后污染握手；数据部分和能归零、乘积也能采到已知值。v3将控制状态改为真正异步复位，累加器仍同步reset；v4使用相同电路并严格拒收未知ready/valid，完成全部门级/STA/PT。没有强制初始化、忽略X或修改库模型。原失败均保留；最终命令为set_fix_hold core后compile_ultra、不重定时，源码以v4冻结manifest为准。', '',
 '相对经典32位主参考，22位固定N64版本的面积变化%+.2f%%、matched帧能量变化%+.2f%%。这只是累加位宽消融，不改变输入精度、极值正确性或采样数。'%(100*(n['area_55eq_um2']/a['area_55eq_um2']-1),100*(n['profiles']['matched']['energy_pJ']/a['profiles']['matched']['energy_pJ']-1)), '',
 '对同批数值的BF16/FP32参考，INT32整数核能量低%.2f倍、面积低%.2f倍、帧间隔短%.2f倍。BF16旧normal577pJ使用不同Gaussian数据，主对照应选同批INT8派生556.2pJ，而不是混用窗口。'%(a['ratio_BF16_to_INT8']['energy'],a['ratio_BF16_to_INT8']['area'],a['ratio_BF16_to_INT8']['interval']), '',
 'SC54历史计算核0.005524mm²、69.4633pJ/350ns，与本次INT32主参考粗比：SC面积为%.2f倍、帧能量为%.2f倍、帧间隔为%.2f倍。这里SC激励/近似精度未匹配，不能当最终整机比值；但此小规模计算核结果不能支持“SC相对经典INT8已有巨大优势”。已有INT8全并行22.1867pJ/20ns、位串行38.7967pJ/100ns也保留，不把新折叠核与不同吞吐的旧核混称。'%(5524.0704/a['area_55eq_um2'],69.4633333333/a['profiles']['matched']['energy_pJ'],350/(10*a['profiles']['matched']['cycles_per_operation'])), '',
 '均为前布局门级活动/PT，不是芯片实测或物理签核。未计权重/输入SRAM、供数/广播/互连、格式转换、真实ICG/CTS/SDF/SPEF。整数核每拍读4个权重而SC并行权重驻留，存储接口成本不能仅由计算核表推断。M>1/大矩阵的输入复用、权重带宽、部分和驻留与满阵列利用率需单独验证。无新模型/PPL，模型/语料哈希字段N/A。', '',
 '结构来源：[Gemmini固定提交README](https://github.com/ucb-bar/gemmini/blob/8c3f9923a44a2fe2c7930587be297d6d4f8c09ca/README.md#generator-parameters)、[PE源码](https://github.com/ucb-bar/gemmini/blob/8c3f9923a44a2fe2c7930587be297d6d4f8c09ca/src/main/scala/gemmini/PE.scala)、[NVDLA官方单元划分](https://nvdla.org/hw/v1/ias/unit_description.html#convolution-mac)。该来源解释经典结构，不将其公开PPA当本项目实测。原件与负结果在project_archives/matrix204_int8_classic_ppa_20261028；中央run matrix-int8-classic-204-20261028。']
 lines+=['','用户面积质疑的逐单元复核与并行度解释见[AREA_EXPLANATION_ZH.md](AREA_EXPLANATION_ZH.md)，不将AND面积直觉当成整个核必然更小的证明。']
 (P/'results/REPORT_ZH.md').write_bytes(('\n'.join(lines)+'\n').encode())
 (P/'README_ZH.md').write_bytes(('# 经典INT8 DOT4本工艺表征\n\n最新结果：[REPORT_ZH.md](results/REPORT_ZH.md)、[完整数值与原件SHA](results/FINAL_SUMMARY.json)。\n\n两配置：四lane INT8乘法、平衡整数归约、输出驻留INT32/INT22累加，固定N64一个输出。精确经典结构主参考为INT32，22位为N64无bias专用消融。源/输入以冻结manifest与ZIP为准，不覆盖v1失败或其他BF16源。\n\n复现生成：python prepare.py；EDA入口flow/run_int8.py。本次已冻结源码，重跑或修改必须新建执行版本；model/corpus N/A，全部为合成事务。恢复看work/rayggxia/204/int8_classic_ppa/HANDOFF.md。\n').encode())
 print('REPORT_WRITTEN')
if __name__=='__main__':main()

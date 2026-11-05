"""Render user-facing locality findings from SHA-verified completed cases."""
import json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[3]
out=ROOT/'architecture_tlm/unified_v6/results/locality_20261025'
a=json.loads((out/'AGGREGATE.json').read_text());rows=a['rows'];by={r['name']:r for r in rows}
labels={
 'old8_exact':'原PR190：8×64，每块写回',
 'digital_w8_exact':'数字W8参考（相同Attention）',
 't64_e8_r1_s1':'8×64，新随机重放宏，每块写回',
 't64_e8_r8_s1':'8×64，本地保留8块',
 't64_e8_r16_s1':'8×64，本地保留16块',
 't64_e8_r256_s1':'8×64，保留全部K块',
 't64_e16_r8_s1':'16×64，保留8块',
 't128_e2_r2_s1':'2×128，每2块写回，单组随机供给',
 't128_e2_r8_s1':'2×128，保留8块，单组供给',
 't128_e2_r8_s2':'2×128，保留8块，双组供给',
 't128_e8_r8_s1':'8×128，保留8块，单组供给',
 't128_e8_r8_s2':'8×128，保留8块，双组供给',
 't128_e8_r256_s2':'8×128，全K块，双组供给'}
s=['# FFN部分和本地驻留与128阵列：面积、流量、时间对照','',
 'Issue186 / PR190；2026-10-25；负责人jieruiz。首轮13项＋修正后11项，共24项完整36层合成事务全部完成并核SHA。最终13组对照采用修正后11候选与未改动的2控制。候选执行源`'+a['source_commit']+'`，Slurm3008；控制及首轮源b1df81d2，Slurm2995。默认路径未替换，候选为显式可选模式。', '',
 '**建议先采用R8局部驻留作为后续验证候选。** 原阵列从509.471降至503.639ms/token，时间减少1.14%；同一新接口的R1→R8减少1.64%。R16和全K时间与R8完全相同，额外状态尚未换来提速。8×128＋双组随机供给＋R8为434.075ms/token，比原版少14.80%，但计算/权重位置约4倍；当前数字W8参考仍更快。','',
 '范围：Qwen3-4B后训练版形状，D=2560、F=9728、36层，batch1、2K上下文、1次decode，准确Attention；GU T64/K64，非线性/Wd T64、联合32格，固定W8。100MHz核心，8MiB/64bank共享SRAM，双通道DDR4-1866真实DRAMSys。没有prefill、真实权重载荷或PPL；下表不是芯片实测。','',
 '| 方案 | FFN时间 ms | 整机 ms/token | 整机比原PR190少 | 部分和读写 MiB/层 | 阵列权重/计算位置数量比 |',
 '|---|---:|---:|---:|---:|---:|']
for r in rows:
 p='—' if r['SC_partial_MiB_per_layer'] is None else f"{r['SC_partial_MiB_per_layer']:.3f}"
 ratio='—' if 'weight_cells_relative_to_8x64' not in r else f"{r['weight_cells_relative_to_8x64']:.1f}×"
 s.append(f"| {labels[r['name']]} | {r['FFN_ms']:.3f} | {r['TPOT_ms']:.3f} | {r['TPOT_reduction_vs_native_old_percent']:.2f}% | {p} | {ratio} |")
s += ['', 'FFN时间含GU、非线性编码、Wd、最终转换与FFN残差；不含FFN前的归一化。其余模块的动作保持一致，但DRAM时刻/行状态可以改变等待。面积比一栏只表示计算/权重位置数量，**不是整块FFN或全芯片面积比**。数字W8仍用同一共同存储调度，但数字算子内部还没有加入对应的新本地驻留优化，因此不能据此宣称对最优数字硬件的优势。', '',
 '## 为什么流量下降很多，时间只下降一部分', '',
 '| 方案 | 阵列采样忙时 ms | 本地权重装入忙时 ms | 桶归约＋系数恢复忙时 ms |', '|---|---:|---:|---:|']
for n in ('old8_exact','t64_e8_r8_s1','t128_e8_r8_s2'):
 r=by[n];s.append(f"| {labels[n]} | {r['array_busy_ms']:.3f} | {r['local_weight_program_busy_ms']:.3f} | {r['bucket_and_restore_busy_ms']:.3f} |")
s += ['', '以上是不同资源的忙时，存在重叠，不能直接相加当总时长。R8不减少数学运算或总权重；每层权重共享SRAM写入＋读出约142.5MiB，而原部分和只有17.64MiB。后者降低88%不等于全部SRAM流量降低88%。扩大阵列明显减少采样忙时，但固定宽度的恢复通路和权重装入不会按4倍同步加速。', '',
 '## 改了什么，计数器为什么不用每拍写SRAM', '',
 '原模型采样期间已经使用本地计数寄存器：同一块权重在64拍里产生事件、精确压缩和累计，帧结束才恢复尺度。反复写SRAM的是**跨K64输入块的宽部分和**，不是每一拍的随机0/1结果。', '',
 '本次新增一个本地宽累加区。先选512个输出，依次计算8块输入；每个块仍按原有K64系数恢复，再按原顺序累加。8块结束后写回，换下一批512个输出。完成所有输出后，再处理下一个8块窗口。这样保持现有精确计数、缩放分组和舍入边界。', '',
 '```text\n随机流 → 固定W8阵列 → 本地时间计数器\n                         ↓ 每K64块恢复尺度\n                  本地64位部分和（跨R块保留）\n                         ↓ 每R块一次\n                    共享SRAM / 后续模块\n```', '',
 'R是“跨多少个K64输入块再写回”，不是采样次数。GU共有40个K64块，Wd共有152个；R=256在本模型中即全K驻留。保留的是计数/部分和和PRNG起始状态，不存64拍完整随机流。', '',
 '## 流量账：哪些少了，哪些没少', '',
 '| R | GU＋Wd部分和读写 MiB/层 | 相对每块写回减少 |', '|---:|---:|---:|']
for n in ('t64_e8_r1_s1','t64_e8_r8_s1','t64_e8_r16_s1','t64_e8_r256_s1'):
 r=by[n];s.append(f"| {r['retain']} | {r['SC_partial_MiB_per_layer']:.6f} | {r['partial_traffic_reduction_percent']:.2f}% |")
s += ['', '计算口径：输出数×8字节×(2×写回窗口数−1)。GU输出19456个，Wd输出2560个；初始全零无需读，最后一次写回仍计入。这里只算`SC_wide_partial`，后续非线性/转换的读取仍然收费。', '',
 '每层W8权重仍为71.25MiB，全模型每token约2.505GiB；不会因为本地驻留而消失。本实现将离线权重按窗口/输出/输入块重新排布，按真实连续DMA读取，每个K64/O64权重块和系数恰好访问一次。真实权重文件重排器与完整数值编译器尚待实现；当前只有地址/覆盖与归约测试。', '',
 '输入x先编码到共享SRAM（5KiB），非线性编码约38KiB；每个窗口读入本地，随输出波复用。当前代码按一次“窗口装入”计共享读取，窗口内部读取属于本地端口动作。并非把每次输入重读偷偷算成零，也没有把全g/u中间张量容量删除。', '',
 '## 面积账：小累加区和大阵列是两种代价', '',
 '| 方案 | 本地W8权重 KiB | 跨块部分和 KiB | 输入码窗口 KiB | PRNG起点银行 KiB | 时间计数器 KiB | 归约流水寄存器 KiB |',
 '|---|---:|---:|---:|---:|---:|---:|']
for n in ('t64_e8_r8_s1','t64_e8_r16_s1','t64_e8_r256_s1','t128_e2_r8_s2','t128_e8_r8_s2'):
 r=by[n];s.append(f"| {labels[n]} | {r['local_weight_KiB']:.1f} | {r['resident_partial_KiB']:.1f} | {r['code_window_KiB']:.1f} | {r['context_bank_KiB']:.2f} | {r['temporal_counters_KiB']:.2f} | {r['reduction_pipeline_KiB']:.1f} |")
s += ['', '这些是容量/状态位代理，不是综合面积。4KiB=32768个状态位，DFF/RF、端口、地址译码、时钟树的面积密度不同；不能按SRAM每bit面积替代寄存器。128的更多并行工作锁存/布线、检查点银行端口/仲裁尚未综合。已有宽加法器可复用；若要求更多路并行，则需额外增加加法器/恢复单元。共享8MiB SRAM配置没有缩小，腾出流量不等于宏面积自动减少。', '',
 'R8相对原路径主要新增4KiB部分和＋2KiB码窗口＋约1.76KiB随机起点银行；另有5KiB共享x编码空间和端口控制。全K方案则需要38KiB码窗口和约33.44KiB起点银行，远非只加4KiB。起点银行保存PRNG状态以重放相同帧，不是新增概率参数阵列，更不是存整段随机流。', '',
 '此外，8×128配置的共同DMA响应容量从64增到128KiB，共享SRAM中的两个权重暂存槽合计从128增到256KiB。前者是额外待表征缓冲；后者占用已有8MiB的更多空间，并未另增共享SRAM宏。局部状态字段的prefetch字节只是SC波大小，整机响应容量应以`tile_pipeline.shared_response_capacity_bytes`为准，不能遗漏，也不能当两份独立响应缓存重复相加。', '',
 '## 128是否降低带宽限制', '',
 '将单阵列64×64改为128×128，两个维度各翻倍，单阵列权重/乘法位置为原来的4倍。这里按四个64×64象限组合，保留每64路缩放和共享，不引入K128量化。', '',
 '- **8×64换成2×128**：总权重/计算位置不变，输出并行从512降到256，输入维并行从64增到128。总物理波数仍是2280/层；只换形状不保证更快。',
 '- **8×64换成8×128**：计算/权重位置约4倍，输出并行1024，物理波数2280→608/层；尾波使它不是严格4倍加速。局部权重32→128KiB、对应计数/流水状态也约4倍。',
 '- 若只利用每次同时处理两个K64块，部分和写回可约减半；但采用R8后，64与128都可以每8块写一次，**128不会再自动将同R的字节数减少**。它主要改善并行度与每波固定开销。',
 '- 128还需要两组K64随机事件并行供给。单组供给方案明确串行服务两组，II翻倍；双组方案付出额外端点状态、种子需求和输出带宽。表中分别运行，不假设随机源无限快。', '',
 '## 已知宏动态能量：只说明被省掉的SRAM访问', '',
 '| 方案 | 全token部分和SRAM内部动态能量 mJ | 相对原值少 mJ |', '|---|---:|---:|']
base=by['old8_exact']['partial_macro_internal_dynamic_mJ_per_token']
for n in ('old8_exact','t64_e8_r8_s1','t64_e8_r16_s1','t64_e8_r256_s1'):
 r=by[n];v=r['partial_macro_internal_dynamic_mJ_per_token'];s.append(f"| {labels[n]} | {v:.4f} | {base-v:.4f} |")
s += ['', '按已校准SRAM的每16B读/写内部能量乘次数计算，不包括新寄存器/RF及端口动态功耗、时钟树、布线和总漏电变化。**不是净节能或整机能效**；物理总能量/总面积仍为空。DS-CIM的缓存累加节能倍率没有直接套用。', '',
 '## 验证、剩余假设和可恢复入口', '',
 '- 本地101项unified_v6测试通过，包括10项新增：精确动作/权重覆盖、R窗口字节公式、同资源128对照、随机有限供给、Attention不变、容量及tile退役、资源无重叠、跨窗口预取和15种有符号缩放归约顺序检查。归约验证不是完整LLM PPL。',
 '- 24项远端完整事务均由Slurm执行，CPU-only；MANIFEST必须completed，远端原RESULT和本地小汇总的SHA都检查。原PR190的45项结果未覆盖。',
 '- 首轮局部窗口没有继承原跨组DMA预取，R1比旧实现慢。核对后补回窗口边界预取并重新冻结源码、重跑11候选；首轮保留为STAGE1表，不挑选旧的乐观结果。最终R1/R8等都采用相同的跨窗口预取。',
 '- 原路径控制与新宏R1控制分开，驻留收益优先比较同新宏的R1/R8/R16，避免把随机接口更改混入收益。实际Attention随机服务不改；本轮准确Attention无需采样。',
 '- 新FFN检查点银行为有界宏，尚不是Issue95真实端点执行：GU32bit状态、NL每组10×177bit，局部32bit端口；NL十端点并行搬运。保存/恢复、启动和换种延迟均有参数和动作；不存随机bit流。跨组独立性、广播扇出与完整端点映射仍待验证。此重放机制面向本地PRNG；直接物理p-bit不能仅凭保存一个种子重放相同随机流，不能继承本方案的重放成本。',
 '- 现有GU T64计算服务约74周期，NL/Wd T64约137周期；128单组源服务两组会变慢。系数恢复16路/L6、宽加法32路/L2、64GB/s fabric、检查点端口及阵列100MHz仍是时序宏假设，没有匹配完整RTL/STA。',
 '- 不把零缺失单价当零功耗。未验证连续跨token的源相关性/训练适配。原有数制宏和新重排编译器没有闭环前，不把旧质量结果写为新结构结果。', '',
 '源、矩阵、提交和结果：`work/jieruiz/186/LOCALITY_SOURCE_b1df81d2.json`、`LOCALITY_SOURCE_829559dc.json`、`LOCALITY_MATRIX.json`以及LOCALITY/PREFETCH的SUBMISSION/COLLECTION；小结果在本目录`results/locality_20261025/`和`window_prefetch/`。远端原始数据为`/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/locality_b1df81d2/`与`locality_829559dc/`。`analyze_locality.py`（--stage1保留首轮）与`make_locality_report.py`可重建表格。', '',
 '长期改进索引：[架构优化记录本](../ARCHITECTURE_OPTIMIZATION_LOG_ZH.md)。文献与机制归属见记录本；本轮没有新增RTL/PT，因此未伪造数字电路已测PPA记录。','']
(ROOT/'architecture_tlm/unified_v6/FFN_LOCALITY_ZH.md').write_text('\n'.join(s),encoding='utf-8',newline='\n')
print('rendered FFN_LOCALITY_ZH.md from 13 sealed cases')

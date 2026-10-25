"""Build the report from sealed results, retaining both schedule revisions."""
import json,pathlib,statistics
ROOT=pathlib.Path(__file__).resolve().parents[3]
rows=json.loads((ROOT/'architecture_tlm/unified_v6/results/memory_20261025/SUMMARY.json').read_text())['rows']
by={r['case']:r for r in rows if r['seed']==0}
base=['legacy_link','ddr4_old','ddr4_wide','balanced_e8','cross_group_e8','cross_group_e16','cross_group_e32','cross_group_e64','balanced_bf16','balanced_w8']
if any(k not in by for k in base):raise ValueError('final comparison not complete')
labels={'legacy_link':'旧Link、旧SRAM/调度','prefetch_link':'旧Link，仅组内预取','sram64_link':'旧Link，仅SRAM加宽','ddr4_old':'标准DDR4，旧SRAM/调度','ddr4_wide':'标准DDR4，仅SRAM加宽','balanced_e8':'标准DDR4＋加宽＋仅组内预取，8阵列','balanced_e16':'仅组内预取，16阵列','balanced_e32':'仅组内预取，32阵列','balanced_e64':'仅组内预取，64阵列','balanced_single':'8阵列、全局关闭双缓冲重叠','cross_group_e8':'完整跨组预取，8阵列','cross_group_e16':'完整跨组预取，16阵列','cross_group_e32':'完整跨组预取，32阵列','cross_group_e64':'完整跨组预取，64阵列','balanced_bf16':'同存储BF16数字参考','balanced_w8':'同存储W8数字参考','balanced_screen_pv':'SC＋筛选/PV','balanced_screen_rejection':'SC＋筛选/校正拒绝'}
lines=['# 标准DRAM、分层SRAM与阵列规模：完整TLM结果','',
'全部为Qwen3-4B后训练版形状、36层、batch1、2K上下文、一个decode token；SC FFN采用W8、x四档T64/K64、随机非线性T64。时间是模拟硬件时间，非运行模拟器的CPU墙钟。数字参考保留原非线性；本轮没有模型权重/语料输入，不是PPL或同质量芯片性能验证。','',
'## 一眼看懂主要变化','',
'| 配置 | 模拟ms/token | 核心周期（100MHz） | DRAM core J/token |','|---|---:|---:|---:|']
def table(keys):
 for k in keys:
  r=by[k];e='—（旧代理口径）' if r['DRAM_core_J'] is None else f"{r['DRAM_core_J']:.4f}"
  lines.append(f"| {labels[k]} | {r['TPOT_ms']:.3f} | {r['cycles']:,.0f} | {e} |")
table(base)
old=by['ddr4_old'];new=by['cross_group_e8'];e16=by['cross_group_e16'];e64=by['cross_group_e64'];w8=by['balanced_w8'];bf16=by['balanced_bf16']
def reduction(a,b):return 100*(1-b['TPOT_ms']/a['TPOT_ms'])
lines += ['',f"固定同一真实DDR4与8阵列，SRAM加宽和完整跨组预取把{old['TPOT_ms']:.3f}ms降到{new['TPOT_ms']:.3f}ms，缩短{reduction(old,new):.2f}%。完整预取下8→16阵列再缩短{reduction(new,e16):.2f}%，16→64再缩短{reduction(e16,e64):.2f}%。这些是给定宏延迟与端口假设下的架构结果，不等于实测芯片加速。",'',
f"16阵列SC相对BF16数字参考时间变化为{100*(e16['TPOT_ms']/bf16['TPOT_ms']-1):+.2f}%，相对W8数字参考为{100*(e16['TPOT_ms']/w8['TPOT_ms']-1):+.2f}%。BF16比较包含权重字节数变化，不能全归因于随机计算；W8参考主要改变权重格式，计算仍是当前512 MAC/拍宏假设，不是优化INT8 ASIC。这里同外存/共享SRAM配置，不是同总存储、同面积。",'',
'保留8阵列作为资源较小的默认，16阵列作为下一步PPA候选。32/64的速度变化见表；未获得增量面积、计数器/互连功耗之前，不能判定哪个规模能效最优。扩大阵列不会减少每token的权重载荷，也不会把整个模型装入SRAM。','',
'## 为什么要保留两轮结果','',
'第一轮只在同一输入组内预取下一输出波；当64阵列的Wd每组只需一波时，组间预取机会完全消失。因此第一轮16→64收益小，不能据此断言大阵列无价值。第二轮修复跨输入组的预取边界，仍只占一波响应缓存；下一组编码、SRAM fill、权重program和系数读取继续等待依赖就绪，未覆盖当前计算使用的状态。','',
'| 第一轮/消融配置 | ms/token | 核心周期 | DRAM core J/token |','|---|---:|---:|---:|']
table(['prefetch_link','sram64_link','balanced_e8','balanced_e16','balanced_e32','balanced_e64','balanced_single'])
lines += ['',
'“全局关闭双缓冲重叠”还关闭数字QKV/O/lm_head的预取，不能将它的全部差值归因于SC缓存。两块SRAM地址仍分配，不能声称减少一半SRAM容量。两轮封存源码和结果分别保留，不能混成一次相同代码实验。','',
'## 分批数与供数瓶颈','',
'| SC阵列 | 本地单份权重 | GU波/层 | Wd波/层 | 总波/层 | 36层总波 |','|---:|---:|---:|---:|---:|---:|',
'| 8 | 32KiB | 1520 | 760 | 2280 | 82080 |','| 16 | 64KiB | 760 | 456 | 1216 | 43776 |','| 32 | 128KiB | 400 | 304 | 704 | 25344 |','| 64 | 256KiB | 200 | 152 | 352 | 12672 |','',
'每个64×64 W8 tile为4KiB；所有规模都完成656640个tile。每层FFN权重71.25MiB、全36层2,689,597,440B/token。片上8MiB不够保存一整层，因此分块不可避免。每块权重在本地保持并重复使用64次采样，不是每个采样拍重新从DRAM搬一次。数字QKV/O/lm_head的64KiB分块保持不变。','',
'| 配置 | DRAM物理GB/token | SRAM读写GB/token | SRAM busy ms | DRAM busy ms |','|---|---:|---:|---:|---:|']
for k in ['legacy_link','ddr4_old','ddr4_wide','cross_group_e8','cross_group_e16','cross_group_e64']:
 r=by[k];lines.append(f"| {labels[k]} | {r['DRAM_bytes']/1e9:.6f} | {r['SRAM_bytes']/1e9:.6f} | {r['SRAM_busy_ms']:.3f} | {r['DRAM_busy_ms']:.3f} |")
lines += ['',
'各资源busy允许重叠，不能相加当作整机时间。同8阵列新旧调度不减少数学工作或权重载荷；扩大阵列后的元数据突发对齐略变。DRAM宏DMA之间仍有完成屏障，尚未声称跨全部算子全局最优调度。','',
'## 功耗、面积与接口假设','',
f"8阵列同DDR4比较，DRAM core能量{old['DRAM_core_J']:.4f}→{new['DRAM_core_J']:.4f}J/token（减少{100*(1-new['DRAM_core_J']/old['DRAM_core_J']):.2f}%）；平均core功率{old['DRAM_core_J']/(old['TPOT_ms']/1000):.3f}→{new['DRAM_core_J']/(new['TPOT_ms']/1000):.3f}W。更短时间完成更多活跃访问，可使能量下降而平均W上升。",'',
'注意：保留的DRAMPower结果含负ACT分项。8阵列首轮两通道合计−0.00138109J，占core总能量0.0934%；实际6.3.1源码与ACT命令数代数复算吻合，来源是独立数据手册上限组合I0<I3N与默认rho/iBeta。该比例仅描述这个异常分项，不是整体功耗误差上界。它不反馈时序，TPOT仍有效；J值仅为未校准模型诊断，不可作为精确芯片节能证据。原件没有改零或删项，审计在work/jieruiz/182/ACT_*。','',
'这是DRAMPower在NoPowerDown、厂家core电流限值下的结果；不含I/O/PHY/控制器，不是实测。16GiB双rank是兼容性基准，不是本2K场景的最小容量；旧64pJ/B代理不能和它直接做同口径能耗比较。','',
f"SRAM仍8MiB、128个55nm SS宏、80MHz，宏面积合计{new['SRAM_macro_area_mm2']:.4f}mm²。16→64bank是同容量重排，读写共用fabric16→64GB/s；宏端峰值81.92GB/s；64GB/s系统接口尚未通过STA/布线验证。SS宏频率没有提高，没有免费双端口。",'',
'本地权重接收256→1024B/核心周期、一波有界DMA响应缓存32/64/128/256KiB、bank选择/CDC/布线、额外缓存读写、本地权重保持以及新FFN算子的PPA尚未完整表征。相同SRAM宏面积不等于相同整机面积。SRAM内部动态能量来自既有表征，漏电随时间改变；整机面积/能量保持null。','',
'## Attention三seed补充','',
'下表沿用第一轮“仅组内预取、8阵列”执行快照，核对Attention/随机服务未被接口修改破坏；不能把其时间当作第二轮跨组预取结果，也不代表真实模型准确率。','',
'| 模式 | seed | ms/token | DRAM core J/token |','|---|---|---:|---:|']
for case in ['balanced_screen_pv','balanced_screen_rejection']:
 rr=sorted([r for r in rows if r['case']==case],key=lambda r:r['seed'])
 for r in rr:lines.append(f"| {labels[case]} | {r['seed']} | {r['TPOT_ms']:.3f} | {r['DRAM_core_J']:.4f} |")
 if len(rr)==3:
  lines.append(f"| {labels[case]}均值±样本标准差 | 0/1/2 | {statistics.mean(x['TPOT_ms'] for x in rr):.3f} ± {statistics.stdev(x['TPOT_ms'] for x in rr):.3f} | {statistics.mean(x['DRAM_core_J'] for x in rr):.4f} ± {statistics.stdev(x['DRAM_core_J'] for x in rr):.4f} |")
 else:raise ValueError('three seeds not complete: '+case)
lines += ['',
'## 验证和复现','',
'- 93项机制/回归通过；18个独立小形状案例覆盖输入组、尾波、单波组、不同随机服务和关闭重叠，完整事件检查无状态覆盖/遗留预取。不是对全模型所有事件的独立重放；调度可改变随机源推进/重播种，合同不变不保证逐位输出相同。',
'- 8个真实DRAMSys吞吐小基准、首轮2个和跨组版本2个tiny集成门禁通过。大模型结果以status=completed的manifest、DRAMSys退出、突发守恒及原字节SHA核验；sacct不可用未被当作完成证据。',
'- 本地Link源码0855eab4；第一轮完整DRAMSys源码7e44b6a4；种子补充fe3fc20f只改runner，51个TLM模块字节一致；跨组修复baf0aab1。Slurm2913、2925、2931分别对应三批完整执行。实际Linux环境/argv与本地打包环境单独记录。',
'- 封存EXECUTION/MANIFEST、派生RESULT_SUMMARY及其来源SHA在results/memory_20261025；19份DRAMSys完整RESULT原件随大trace保留远端。远端大trace位置、脚本、动态库和source manifest在work/jieruiz/182；Git不复制大trace。',
'- [存储结构、参数来源与论文对照](MEMORY_HIERARCHY_ZH.md)。Issue182 / PR183交付，未自动合并。','']
(ROOT/'architecture_tlm/unified_v6/RESULTS_MEMORY_ZH.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')

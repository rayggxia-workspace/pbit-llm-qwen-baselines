"""Write the user-facing comparison only after all sealed cases pass audit."""
import json,pathlib,statistics
R=pathlib.Path(__file__).resolve().parents[3];O=R/'architecture_tlm/unified_v6/results/hbm_20261025'
a=json.loads((O/'AGGREGATE.json').read_text(encoding='utf-8'));assert a['status']=='completed' and a['cases']==25
rows=a['rows']
def select(profile,ffn,att):return [x for x in rows if (x['profile'],x['ffn'],x['attention'])==(profile,ffn,att)]
def mean(profile,ffn,att,key='TPOT_ms'):
 r=select(profile,ffn,att);assert r;return statistics.mean(x[key] for x in r)
lines=['# 换用HBM后，每个token需要多久？','',
'结论来自完整36层Qwen3-4B、batch=1、2K上下文的真实DRAMSys闭环TLM运行；不是按带宽比例折算。计算核心100MHz、片上SRAM8MiB/64GB/s、矩阵吞吐和采样次数保持不变。以下数字是架构时序估计，尚不是芯片实测。','',
'| 计算方案 | 原双通道DDR4 ms/token | HBM2＋流水请求入口 ms/token | 时间减少 | HBM token/s |',
'|---|---:|---:|---:|---:|']
for ffn,att,label in [('bf16','exact','原BF16数字算术＋准确注意力'),('w8','exact','W8数字FFN＋准确注意力'),('sc','exact','随机FFN R8＋准确注意力'),('sc','screen_pv','随机FFN R8＋筛选/PV采样')]:
 d=mean('mature_ddr4',ffn,att);h=mean('mature_hbm2_pipelined',ffn,att)
 lines.append(f'| {label} | {d:.3f} | {h:.3f} | {(1-h/d)*100:.1f}% | {1000/h:.2f} |')
lines += ['', '概率方案主要HBM配置各3个seed；筛选/PV的DDR对照也3个seed。准确注意力下DDR的SC本轮1个seed（旧版本已有相同合同结果），其余种子不冒充本轮新跑。这里只比较运行时间，没有新PPL结果。W8指FFN权重，QKV/O及词表等仍按BF16合同。', '',
'**HBM可以用于ASIC。** 例如[Google TPU v5e](https://docs.cloud.google.com/tpu/docs/v5e)公开使用HBM。它需要相应控制器、PHY和封装；这些硬件成本不会因为在TLM里换配置就消失。','',
'**为什么实得带宽不是标签上的256GB/s？** 我们先保留旧接口，再逐项打开能力：','',
'| 外存/入口 | 连续读取实得GB/s | 作用 |','|---|---:|---|']
probe=json.loads((O/'pipelined/probe/RESULTS.json').read_text(encoding='utf-8'))['rows']
for p,label,why in [('mature_ddr4','原DDR4','旧/新bridge时延和能量逐值回归相同'),('mature_hbm2_narrow','HBM＋旧64B入口','先隔离只换DRAM的效果'),('mature_hbm2_wide','HBM＋256B入口','span内合并，原2ns响应间隔'),('mature_hbm2_pipelined','HBM＋256B流水入口','去掉1ps跨时钟取整，响应最短间隔1ns')]:
 value=next(x['effective_GBs'] for x in probe if x['profile']==p and x['pattern']=='read')
 lines.append(f'| {label} | {value:.2f} | {why} |')
lines+=['','HBM2采用DRAMSys公开配置的原时序，扩到8通道×2伪通道，16GiB、理论256GB/s；与DDR容量相同。宽入口在64B计费不变的情况下合并自然对齐256B事务，由DRAMSys拆成32B原生突发。桥接最多128条，但控制器实际接收上限64条，实测峰值65含1条等待。没有跨不连续V地址合并，没有降低模型真实读取字节。现PV调度会随max_pending把V分批上限从32改为128，减少描述符和批启动次数；该接口收益已包含于宽入口方案，不能全算给HBM器件。','',
'**HBM解决外存等待，但当前片上吞吐仍限制速度。** 下表是独立资源忙碌时间，部分会重叠，不能把各列直接相加或当作串行占比。','',
'| HBM流水配置 | 外存服务ms | SRAM共享口忙碌ms | 数字MAC忙碌ms | 整机ms |','|---|---:|---:|---:|---:|']
for ffn,att,label in [('bf16','exact','BF16准确'),('w8','exact','W8准确'),('sc','exact','SC准确'),('sc','screen_pv','SC筛选PV')]:
 vals=[mean('mature_hbm2_pipelined',ffn,att,k) for k in ('dram_service_ms','sram_busy_ms','mac_busy_ms','TPOT_ms')]
 lines.append('| '+label+' | '+' | '.join(f'{v:.3f}' for v in vals)+' |')
lines += ['', '**更换后剩下的时间主要在哪里？** 以随机FFN＋准确注意力的seed0为例，各阶段来自同次完整运行，单位ms：', '', '| 阶段 | DDR4 | HBM流水 |', '|---|---:|---:|']
aa=json.loads((O/'results/case_2/RESULT_SUMMARY.json').read_text(encoding='utf-8'))
bb=json.loads((O/'pipelined/results/case_2/RESULT_SUMMARY.json').read_text(encoding='utf-8'))
for keys,label in [(['FFN_gate_up','FFN_AND_direct_down'],'FFN两个矩阵阶段'),(['QKV_projection','O_projection'],'QKV及输出投影'),(['lm_head_and_argmax'],'词表读出'),(['attention_core'],'注意力核心')]:
 lines.append(f"| {label} | {sum(aa['phase_ns'][k] for k in keys)/1e6:.3f} | {sum(bb['phase_ns'][k] for k in keys)/1e6:.3f} |")
lines += ['', 'FFN预取已覆盖多数外存等待，所以提升主要来自其他投影和读出。继续把微基准读带宽从112提高到186GB/s，SC准确整机仅439.166→438.038ms（约0.26%）；这直接说明当前主要瓶颈已不在外存峰值。', '', '注意力当前逐KV组执行，token-major KV步长2048B与HBM channel bit8..10使同组集中一通道，因而不能获得全8通道带宽，甚至有少量阶段退化。未来可单独验证XOR通道映射（channel = 原低位 XOR token低位）或多KV组并行；本轮未混入这些布局/调度改动。']
lines += ['', '外存交换后数学工作量、权重/激活字节数、阵列和SRAM容量逐项核对不变。只靠HBM无法突破固定MAC吞吐和SRAM忙碌时间；当前模型还存在tile退休后才填充下一SRAM tile的调度约束。本结果不能说明ASIC只能达到该速度，也不能等同大型GPU/TPU的带宽与算力配置。下一步若要继续缩短延迟，应优先评估片上数据通路及tile加载/计算重叠，并向数字对照提供同等资源。','',
'**能量暂不下结论。** HBM例子的电流参数是零占位，本轮显式关闭功耗计算；HBM、PHY、控制器增量的能量/面积仍未知。完整物理能量与面积保留null，禁止把已定价小计解释成节能。','',
'验证：104项TLM回归；两批共36项真实读写微基准（含重复DDR不变验证）；25项完整decode封存结果；36层执行覆盖，输入矩阵/代码/配置/bridge/结果SHA与控制器服务字节、父事务、容量核验。Slurm3019/3020、3037/3038；没有GPU训练或质量实验。','',
'细节和原始证据索引：`HBM_TIMING_ZH.md`、`results/hbm_20261025/AGGREGATE.json`、`COMPARISON.csv`及每case的MANIFEST/EXECUTION/RESULT_SUMMARY。原始大结果和trace保留在个人远端`pbit-scheduling-issue186-20261025/hbm_<执行提交>/`，本地只保留小汇总。']
(R/'architecture_tlm/unified_v6/HBM_RESULTS_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
print('\n'.join(lines[:15]))

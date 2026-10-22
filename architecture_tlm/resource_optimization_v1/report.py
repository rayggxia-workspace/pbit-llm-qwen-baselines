"""Render result tables directly from verified immutable search summaries."""
import argparse
import json
from pathlib import Path

from .search import generate_candidates
from .summarize import ROOT, read


def main():
    p=argparse.ArgumentParser();p.add_argument('--summary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    d=read(a.summary);rows=d['rows'];aggregates=d['aggregates']
    means={(x['candidate'],x['method'],x['context']):x for x in aggregates}
    cases={(x['candidate'],x['method'],x['context'],x['seed']):x for x in rows}
    methods=['bf16_exact','w8_exact','sc_exact','sc_screen_pv'];labels=['BF16准确','W8数字准确','SC准确','SC筛选/PV']
    representative=['baseline_1m','mapped_1m','vector_128','balanced_2m','wide_4m']
    lines=['# ASIC资源优化首轮结果（Issue117）','',
        '**128项共同候选粗筛＋64项预声明代表点补充＋16项vector128跟进，共208项新完整decode TLM执行。** 五个代表点每种方法/上下文均有seed0/1/2；另外11候选只做seed0粗筛。全部是合成路由事务估计，不是GPU速度、模型质量或物理芯片测试。','',
        '主要结果：当前映射下只扩2/4/8MiB容量没有时延收益；同1MiB重新分块只有小幅收益。向量恢复资源加倍后，SC筛选/PV在8K出现相对同配置W8的条件时延收益，2K没有。继续扩带宽/算术时数字W8也显著受益，不能宣布SC普遍更优。完整面积/能量/A0仍null，暂不建立完整同面积Pareto排名。','',
        '## 当前项目与执行版本','',
        '- 开始时实时核验集成`46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d`。PR103/105/106/108/109/111/113/114均已合并，不能沿用原计划中的“待合并”状态。Issue116独立推进周期级执行后端，本任务不修改其实现。',
        '- 发布期间新增[PR120](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/120)（Issue118），提供独立FFN供数合同和逐档整数状态模型，尚未合并，也未纳入本轮执行；不可把本轮旧v6的局部状态缺项表理解为该并行任务没有工作。后续优先对接其已提供接口，与Issue116协作验证。',
        '- 粗筛执行`44dbbbdbc2720963b2b24bf03cdf7582a2d97075`；首批补充执行`315862412e15695c3fa21e6c573d9e5f3547e70d`；vector128跟进执行`b1b4d18`。十份执行清单的数值/调度源SHA集合相同；提交差异仅P0文档/结果或后处理工具。运行时源码、配置和各case原字节均绑定。',
        '- Qwen2.5-0.5B，24层、batch1、2K/8K、单decode token；固定W8/B4/T32/K32，PV预算L/16，真实有限随机服务。100MHz核心/源，80MHz SRAM；只改变白名单中的资源和分块字段。',
        '- 所有52旧＋40已集成随机服务原件保持不变；145payload SHA审计通过。没有新模型/分词器/语料推理、PPL、GPU/Slurm、RTL/EDA/STA或真实DRAMSys运行。','',
        '## 三seed代表点（ms/token，均值±样本标准差）','']
    for context in [2048,8192]:
        lines += [f'### 上下文{context}','','| 配置 | '+' | '.join(labels)+' |','|---|'+'---:|'*4]
        for candidate in representative:
            cells=[]
            for method in methods:
                x=means[(candidate,method,context)];assert x['seeds']==[0,1,2]
                cells.append(f"{x['TPOT_mean_ms']:.5f} ± {x['TPOT_stdev_ms']:.5f}")
            lines.append('| '+candidate+' | '+' | '.join(cells)+' |')
        lines.append('')
    lines+=['`mapped_1m`保留原1MiB/16bank/fabric16GB/s、DRAM16GB/s/窗口32、512MAC/64vector/8SC，只增加权重slot到256KiB并将Attention tile改256。`balanced_2m`为2MiB/32bank/fabric32、DRAM32/窗口64、512MAC/128vector/8SC。`wide_4m`为4MiB/64bank/fabric64、DRAM64/窗口128、1024MAC/128vector/16SC；后两者的新增接口/算术成本尚未物理标定。','',
        '![条件时间](figures/latency.png)','',
        '## 具体收益与负结果','',
        '| 上下文/方法 | 同1MiB映射时间下降 | 2MiB联合时间下降 | 4MiB高资源时间下降 |','|---|---:|---:|---:|']
    for context in [2048,8192]:
        for method,label in zip(methods,labels):
            b=means[('baseline_1m',method,context)]['TPOT_mean_ms']
            values=[100*(1-means[(c,method,context)]['TPOT_mean_ms']/b) for c in ['mapped_1m','balanced_2m','wide_4m']]
            lines.append(f'| {context} / {label} | '+' | '.join(f'{x:.3f}%' for x in values)+' |')
    lines+=['','1. **容量only 24组配对全部无收益。** 2/4/8MiB保持旧分配时，四方法×两上下文的时间、物理流量、Arena布局及全部候选/采样地址摘要与1MiB相同；只有宏数量、面积和泄漏增加。它不证明新KV缓存/驻留策略也无收益。',
        '2. **1MiB还有可用映射空间。** mapped_1m在8K筛选PV下Arena峰值979,136B，低于1,048,576B；没有新增跨token权重驻留，SC波次不随普通权重chunk扩大而自动变化。',
        '3. **vector128确认共享向量资源的敏感性。** B4/T32计数恢复353,009,664个代理op，64/128lane服务分别55.15776/27.57888ms。恢复服务减少27.57888ms，整机还受其他向量阶段和调度影响，不能只按恢复服务从墙钟相减。这不是专用恢复RTL或已通过STA的吞吐。',
        '4. **DRAM候选联合改变带宽和在途窗口。** 16/32/64GB/s与窗口32/64/128对应原Link满窗口持续率9.846/19.692/39.385GB/s。收益不能归因于带宽单项，更不证明控制器/PHY已实现。',
        '5. **数字对照必须共同优化。** vector128在8K的正向结果触发了另外两seed的明确跟进，未更改算法或预算；它不是盲测质量结果。下面列出同配置SC筛选/PV相对W8数字的时间比；大于1表示SC较慢。','',
        '| 配置 | 2K SC筛选/PV ÷ W8 | 8K SC筛选/PV ÷ W8 |','|---|---:|---:|']
    for c in representative:
        ratio=[means[(c,'sc_screen_pv',ctx)]['TPOT_mean_ms']/means[(c,'w8_exact',ctx)]['TPOT_mean_ms'] for ctx in [2048,8192]]
        lines.append('| '+c+' | '+' | '.join(f'{v:.4f}' for v in ratio)+' |')
    lines+=['','## 随机路径与质量边界','',
        '逐query记录全部候选绝对token ID和全部抽样绝对token ID摘要；样本行覆盖24×14=336，每行输出2K128/8K512。每个新资源配置均与相同seed基线比较；源总摘要还包含FFN重放，不能仅因总摘要变化就断言Attention样本变化。','',
        '| 相对相同seed基线（所有非基线case） | 相同 | 不同 |','|---|---:|---:|']
    nonbase=[r for r in rows if r['candidate']!='baseline_1m']
    for key,label in [('same_recorded_routing_as_baseline','候选token序列'),('same_sample_addresses_as_baseline','抽样token序列'),('same_source_output_as_baseline','所有源输出记录')]:
        vals=[r[key] for r in nonbase];assert all(v is not None for v in vals)
        lines.append(f'| {label} | {sum(v is True for v in vals)} | {sum(v is False for v in vals)} |')
    lines+=['','地址相同只证明本次合成事务可配对，不证明完整LLM质量。改变分块可能改变真实有限精度在线Softmax的结合顺序；TLM没有执行这些张量运算。用户尚未指定可接受PPL损失，不能以任意质量阈值完成架构验收。','',
        '## 全部16候选（seed0）','',
        '| 候选 | 容量/组织与覆盖参数 |','|---|---|']
    for c in generate_candidates():lines.append('| '+c['id']+' | `'+json.dumps(c['overrides'],ensure_ascii=False,sort_keys=True)+'` |')
    for context in [2048,8192]:
        lines += ['',f'### 上下文{context}粗筛时间，ms/token','','| 候选 | '+' | '.join(labels)+' |','|---|'+'---:|'*4]
        for c in generate_candidates():lines.append('| '+c['id']+' | '+' | '.join(f"{cases[(c['id'],m,context,0)]['TPOT_ms']:.5f}" for m in methods)+' |')
    lines+=['','![SRAM局部面积与时间](figures/partial_area.png)','',
        '这只是SRAM宏面积与时间散点。1/2/4/8MiB为4.994613/9.989226/19.978452/39.956904mm²宏面积，未含wrapper/CTS/互连等；同一横坐标仍可能有不同MAC/SC/向量/外存资源，不能读成完整芯片Pareto前沿。','',
        '## 下界、缺项与下一步优化','',
        '![固定流量与固定服务下界](figures/bounds.png)','',
        '下界跨资源取max；固定busy含原保守资源占用，不能当作任意新架构的理论下界。每个新映射都用本case物理流量重算，详见SUMMARY.json各行lower_bounds及P0_RESULTS_ZH.md。','',
        '优先落实两项P1接口：专用恢复/计数归约的真实latency、II与有限出口，及SC权重并行供给/保持和局部计数物理归属。E4/8/16当前计数表示为24/48/96KiB，权重波次为16/32/64KiB；它们尚未计入Arena宏面积，不能把SC引擎扩展视作免费。替换代理后要删除旧恢复收费。','',
        '其次实现真实驻留/KV组缓存和有限队列，比较同带宽/同窗口的持续在途DRAM后端；允许数字和SC共同使用这些调度。2MiB作为带宽/组织折中候选、4MiB作为高资源参考，当前证据不支持“仅容量2/4MiB最优”。Issue116的新周期后端可消费本轮配置及缺项接口，后续仍需按其完成状态独立验收。','',
        '面积账本闭合后才建立数字A0及同总面积前沿；用少数代表点做SRAM外围/恢复RTL STA-PPA和真实DRAM trace校准。prefill/TTFT、batch4/8、Llama规模外推、新算法PPL均未在本轮实现，不能从本表直接外推。','',
        '## 验证与制品','',
        '- 71项单元/机制测试通过（28新增＋43原v6）；128配置容量/组织检查包含于机制测试，不包装成128个电路测试。',
        '- 208case完整键集合、配置/执行源/receipt散列、336query覆盖、相位时长、资源与容量守恒、24容量对照及7个新基线锚点由verify.py独立核验。',
        '- 每份EXECUTION.json记录Python/系统/命令、执行提交、源文件SHA；RUN_MANIFEST.json冻结候选和种子，case及receipt保存原结果字节。原件未覆盖，失败/中断不能按complete计数。',
        '- [机器汇总](results/analysis_20261023/SUMMARY.json)、[独立验收](results/analysis_20261023/VALIDATION.json)、[P0账本](results/p0_20261023/RESOURCE_LEDGER.json)；任务辅助证据与独立审阅见work/amlink1219/117。',
        '- 结果与代码先通过workspace任务分支/PR119交付，待审、未自动合并。Projects缺read:project，Issue/PR/STATUS已同步时不等于看板已同步。','']
    with a.output.open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines))


if __name__=='__main__':main()

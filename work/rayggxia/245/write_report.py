from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[3]
P=ROOT/'architecture_tlm/model_scaling_20261106'
d=json.loads((P/'ESTIMATE.json').read_bytes());rows=d['models']
names={'qwen3_4b':'Qwen3-4B，原生锚点重建','llama32_3b':'Llama-3.2-3B-Instruct，初估','deepseek_7b':'DeepSeek-LLM-7B-Chat，初估'}
text='''# 固定硬件下的跨模型概率方案初步估计（Issue245）

结论：沿用当前一套硬件，Llama约40ms、160mJ/token；DeepSeek约83ms、334mJ/token。两者已覆盖面积均约67.5mm²、已计平均功率约4W。这里是**已有电路价格＋逐类动作/流量＋Qwen调度效率的解析预算**，不是新模型完整原生TLM、PPL或芯片实测。

## 1. 总表

同100MHz、2.5MiB SRAM、12核C20、共享1024路数字FMA、8个物理Attention组、约136.46GB/s峰值LPDDR5-derived8533、B1/2K；包含embedding和完整lm_head。FFN固定W8，数字投影/lm_head接口BF16，FP32反馈；Attention使用SparQ r32/K128及Ising赢家保持S64。硬件FFN仍按当前T64/66周期价格，不将另一路T32质量结果配给T64硬件能量。外存4pJ/bit为主。

|模型|时间ms/token|片上mJ/token|外存mJ/token|已计总mJ/token|已计平均W|覆盖mm²|
|---|---:|---:|---:|---:|---:|---:|
'''
for k,row in rows.items():
    s=row['scenarios']['reference_efficiency']
    text+=f"|{names[k]}|{s['time_ms']:.2f}|{s['onchip_mJ']:.2f}|{s['external_mJ_by_pJ_per_bit']['4']:.2f}|{s['covered_system_mJ_at4pJ']:.2f}|{s['covered_system_average_W_at4pJ']:.2f}|{s['covered_area55_mm2']:.2f}|\n"
text+='''
面积相同是因为复用同一芯片，层数和逻辑头数增加体现为执行波数和能量增加，不复制整层电路。项目面积已单次乘0.81，功耗/时间不缩放。平均约4W也不是强行固定：主情景有效搬运约109.17GB/s×32pJ/B≈3.49W外存，加约0.50W片上。大模型主要增加运行时间和每token能量，不要求瞬时功率按参数量倍增。外存以聚合每bit价格收费，未再叠加旧DDR4状态功率。

## 2. 各部分预算

|片上部分|固定覆盖面积mm²|Llama mJ/token|DeepSeek mJ/token|
|---|---:|---:|---:|
'''
groups={
 'FFN计算/跨K/响应':['FFN_common_core','FFN_crossK_state32','FFN_2KiB_state_response_proxy'],
 '共享数字投影/lm_head及归约':['ordinary_BF16_FMA','ordinary_final_reduction'],
 'SRAM':['shared_SRAM'],
 'Attention核心/筛选/采样/V累加':['Attention_QK_FMA','Attention_SparQ','Attention_sampler','Attention_V_accumulate','Attention_V_control','Attention_normalize_output_proxy'],
 'DMA数据保持':['DMA_24KiB_holding'],
 '格式/向量/本地保持代理':['digital_holding_proxy','format_and_vector_proxy']}
area_groups={
 'FFN计算/跨K/响应':['FFN_common_core','FFN_crossK_state32','FFN_2KiB_state_response_proxy'],
 '共享数字投影/lm_head及归约':['ordinary_BF16_FMA','ordinary_final_reduction'],
 'SRAM':['shared_SRAM'],
 'Attention核心/筛选/采样/V累加':['Attention_QK_FMA','Attention_SparQ','Attention_sampler','Attention_V_accumulate_control','Attention_normalize_output_proxy'],
 'DMA数据保持':['DMA_24KiB_holding'],
 '格式/向量/本地保持代理':['digital_holding_proxy','format_and_vector_proxy']}
for title,keys in groups.items():
    a=sum(rows['qwen3_4b']['scenarios']['reference_efficiency']['area_components55_mm2'][k] for k in area_groups[title])
    es=[sum(rows[m]['scenarios']['reference_efficiency']['onchip_components_mJ'][k] for k in keys) for m in ('llama32_3b','deepseek_7b')]
    text+=f'|{title}|{a:.3f}|{es[0]:.3f}|{es[1]:.3f}|\n'
text+='''
FFN比较器、数字GF64随机源及SNG已在集成C20成本内，不额外重复加随机源；Attention采样器也沿集成数字实现价格。本表没有假定物理p-bit或DAC免费，更没有新增其估值。

## 3. 模型、流量和容量

|模型|层/隐藏/FFN|Q/KV头|外存GB/token|整份BF16 KV MiB|权重＋KV及转置视图约GB|片上已分配MiB|
|---|---|---|---:|---:|---:|---:|
'''
for k,row in rows.items():
    q=row['quantities'];m=q['model']
    text+=f"|{k}|{m['layers']}/{m['hidden']}/{m['ffn']}|{m['q_heads']}/{m['kv_heads']}|{q['external_bytes']/1e9:.3f}|{q['logical_full_BF16_KV_bytes']/1024**2:.0f}|{q['weight_plus_KV_storage_bytes']/1e9:.3f}|{q['memory_placement']['physical_allocated_bytes']/1024**2:.3f}|\n"
text+='''
完整KV主要放外存；保留当前K行主序与特征主序两视图，因此存储容量另包含一份转置K。DeepSeek独立embedding权重计入存储容量，但每token只读一个embedding行，不重复扫描整个embedding表；lm_head每token完整读取。Llama tied embedding同样不消除lm_head读取。两模型当前混合数制和2K缓存的容量均低于16GiB。

Llama每KV对应3Q，DeepSeek为1Q，分别映射到现有8物理KV组，后者每层4波。按实际逻辑Q/KV分别统计：QK/输出/采样量按Q头，K/V读取与缓存按KV组。不是把Qwen结果统一乘参数量比例。

容量检查发现：Llama可沿现有bank分区分配；DeepSeek全层norm驻留按旧均匀映射会有192个bank超深度，即使总容量仍小于2.5MiB。初估改用32KiB逐层norm双缓冲，原有DMA预取，每token额外约0.50MB读取已收费；修改后各bank均在容量内。此检查只证明容量，不证明端口仲裁或时序已验证。

另有需适配的固定布局：DeepSeek的64×64权重尺度元数据实际需33024B/层，超过旧固定32768B；动态g/u尺度的旧offset=20000也可能与扩大的元数据重叠。估计使用完整元数据字节并明确要求重排地址，未把旧硬编码直接运行在新模型上。Llama/DeepSeek均不采用Qwen的QK-headnorm。后续完整TLM必须参数化这些差别。

## 4. 时间与功率的不确定范围

中央时间用原Qwen三seed封存流量/时间得到有效带宽109.17GB/s（约80%峰值），并与逐阶段计算服务下限及SRAM总服务下限取最大值。计算下限计入12核66周期FFN、共享1024 FMA、QK、有限物理头槽V累加、采样器和归约；不把权重搬运与可重叠的计算简单相加。

|模型|90%峰值效率时间ms|同Qwen效率时间ms|65%峰值效率时间ms|固定价格下平均功率情景W|
|---|---:|---:|---:|---:|
'''
for k in ('llama32_3b','deepseek_7b'):
    v=rows[k]['scenarios']
    text+=f"|{k}|{v['util90']['time_ms']:.1f}|{v['reference_efficiency']['time_ms']:.1f}|{v['util65']['time_ms']:.1f}|{v['util65']['covered_system_average_W_at4pJ']:.2f}–{v['util90']['covered_system_average_W_at4pJ']:.2f}|\n"
text+='''
65/90%是待验证的调度情景，不是统计置信区间，也不是完整TLM可保证的上下界。新模型的真实QK、候选分布、Ising相关时间尚未捕获；V读取中央值采用均匀有放回占用情景，并另计算1到min(K,Q/KV×S)的唯一地址范围。SparQ按每个逻辑KV组保留原四头模块活动价格作为上侧代理，未给MHA免费筛选。FFN局部输入重装次数采用Qwen已观测比例，后续需要原生调度核验。

外存单价敏感性更大：

|模型|4pJ/bit总mJ/token|6.6pJ/bit总mJ/token|8pJ/bit总mJ/token|
|---|---:|---:|---:|
'''
for k in ('llama32_3b','deepseek_7b'):
    s=rows[k]['scenarios']['reference_efficiency']
    vals=[s['onchip_mJ']+s['external_mJ_by_pJ_per_bit'][str(v)] for v in (4,6.6,8)]
    text+='|'+k+'|'+ '|'.join(f'{v:.1f}' for v in vals)+'|\n'
text+='''
## 5. 可信边界、验证与下一步

脚本已逐项重建原Qwen三seed均值：16个片上分项、总字节、49.56325ms和67.54144608mm²匹配；这是对账门禁，不是新模型预测精度验证。六项CPU检查通过，包含官方参数总数、FFN/矩阵字节与物理头复用、SRAM bank容量、完整embedding存储与逐token读取区别、能量/面积守恒及带宽/V复用敏感性。

Llama官方HF config匿名读取401，未越过访问控制。采用Meta公开SKU解析28层/3072/24Q/8KV，按官方SwiGLU宽度规则得8192，结合官方HF精确总参数3212749824核验tied embedding；记录其官方revision，明确保存的是架构派生配置，不伪称原始config字节。DeepSeek和Qwen已取得固定revision原始config；模型和配置身份/SHA在evidence/MODEL_IDENTITIES.json。没有下载权重、训练、PPL或新的原生Slurm仿真。

后续完整验证分两步：先参数化通用TLM的Q/KV比、8物理通道复用、码/尺度地址、norm流式加载和分块边界，跑首层容量/字节/队列预检，再在EDA CPU跑完整28/30层。随后用各模型自己的权重/文本校准x/g/u与S12-gap-P8分布，捕获真实筛选/赢家保持周期和V重用，测匹配PPL后更新预算。当前T64/K128/S64不是已通过新模型质量验收的推荐配置。

表中是已有校准与明确代理覆盖范围，不含完整PHY/IO/CTS、部分互连/CIM周边/转换增量；C20价格仍带部分PT窗口及面积缩放idle代理限制。覆盖67.5mm²不是最终die面积、约4W不是整板实测。尚未建立这两模型的匹配数字整机对照，不能据此宣称相对数字版节能比例。

重算：`python -B architecture_tlm/model_scaling_20261106/estimate.py`；验证：`python -B -m unittest architecture_tlm.model_scaling_20261106.test_estimate -v`。输出ESTIMATE.json含全部动作、16个能量分项、固定面积、65/90%调度和4/6.6/8pJ外存情景；CALIBRATION.json包含已有封存/价格SHA，不复制原始波形、网表或模型。

来源：[Meta官方架构SKU](https://github.com/meta-llama/llama-models/blob/main/models/sku_list.py)、[Llama3.2 Instruct模型卡](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct)、[DeepSeek官方配置](https://huggingface.co/deepseek-ai/deepseek-llm-7b-chat/blob/main/config.json)、Issue236/PR244原17项封存结果及本项目数字电路统一台账。准确revision、原件SHA和元数据访问范围见两个JSON索引。
'''
(P/'REPORT_ZH.md').write_bytes(text.encode())
(P/'README_ZH.md').write_bytes(('# 两模型固定芯片概率预算\n\n先读[初步报告](REPORT_ZH.md)。这是解析预算适配器，不是新的完整TLM入口。代码和校准可独立离线重算；新模型尚无原生TLM/PPL。\n\n'+
 '运行：`python -B architecture_tlm/model_scaling_20261106/estimate.py`；检查：`python -B -m unittest architecture_tlm.model_scaling_20261106.test_estimate -v`。\n').encode())
print(json.dumps(dict(status='written',report=str(P/'REPORT_ZH.md'),bytes=len(text.encode()))))

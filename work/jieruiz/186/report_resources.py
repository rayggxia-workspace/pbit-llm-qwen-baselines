"""Generate a concise report from sealed full-model timing results."""
import json,pathlib
R=pathlib.Path(__file__).resolve().parents[3];D=R/'architecture_tlm/unified_v6';a=json.loads((D/'results/resources_20261025/ANALYSIS.json').read_text());P={x['profile']:x for x in a['pairs']};F=a['effects']
rows='\n'.join(f"| {p['MAC_per_cycle']} | {p['SRAM_GBs']:.0f} | {p['old_ms']:.3f} | {p['prefill_ms']:.3f} | {p['saved_ms']:.3f}（{p['saved_percent']:.1f}%） |" for p in a['pairs'] if p['profile']!='anchor_F64')
lo=a['phase_ms']['c512_m64_0'];hi=a['phase_ms']['c8192_m512_1'];stages='\n'.join(f'| {label} | {lo[k]:.3f} | {hi[k]:.3f} |' for k,label in [('QKV_projection','Q/K/V投影'),('O_projection','O投影'),('FFN_gate_up','FFN入口两个矩阵'),('FFN_down','FFN输出矩阵'),('lm_head_and_argmax','词表投影和选词'),('attention_core','Attention核心')])
r=next(x for x in a['rows'] if x['profile']=='c8192_m512' and x['prefill']);s=next(x for x in a['rows'] if x['profile']=='c512_m64' and not x['prefill'])
text=f'''# Qwen3-4B：分开检查计算资源、SRAM接口与调度损失

2026-10-25；Issue186 / PR190。执行源码b01058f7e2143e81a602644d3d796768a8d008b5。CPU Slurm3057的8项真实DRAMSys小模型门禁、3058的16项完整模型全部完成，110项功能回归通过。以下是模型预测的每token时间，不是模拟程序运行时间或芯片实测。

**此前的小计算单元来自早期可调默认，不是Qwen要求，也没有经过整机尺寸优化。本轮在同一个模型中，分别测量硬件扩容和一项具体调度改进。**

## 主要结果

Qwen3-4B后训练形状，B1、2K总上下文、36层、单token decode，BF16数字FFN与准确Attention，含词表投影及选词，不计预填充TTFT。核心100MHz、SRAM80MHz、共享容量8MiB、一个64KiB本地操作数缓冲、两个64KiB共享权重槽不变。HBM2保持理论256GB/s的同一DRAMSys配置、地址映射及控制器。

| MAC/周期 | 共享SRAM读写带宽 GB/s | 原调度 ms/token | 加入下一块SRAM预填充 ms/token | 同硬件调度节省 |
|---:|---:|---:|---:|---:|
{rows}

主表使用共同E宏家族。旧F宏64GB/s锚点准确复现 **{P['anchor_F64']['old_ms']:.5f}ms**；只加预填充为 **{P['anchor_F64']['prefill_ms']:.3f}ms**。F64→E64的 **{F['old_macro_to_E_ms']:.3f}ms** 差异单列为宏组织/延迟变化，不算调度收益。

共同E家族中：仅计算资源512→8192省 **{F['compute_only_ms']:.3f}ms**；仅共享SRAM接口与独立bank资源64→512GB/s（宏数和容量不变）省 **{F['SRAM_only_ms']:.3f}ms**；两者一起扩大、保留原调度省 **{F['joint_hardware_ms']:.3f}ms**；在扩大后的硬件上再加预填充，另省 **{F['schedule_large_ms']:.3f}ms**。这些单因素节省不能相加；计算速度也会改变可重叠的时间。所测调度收益不等于全部调度损失，更不代表最优排程。 尤其8192/32768档预填充收益为零，不代表调度已无问题：下一DMA仍在当前MAC开始时才发出，本地load和结果退休仍串行。MAC很短时下一DMA到达太晚，这一开关几乎无重叠窗口；更早发DMA、双本地缓冲及KV通道重排仍需另行对照。

## 512 MAC/拍从哪里来

Git证据在work/jieruiz/186/RESOURCE_DEFAULT_PROVENANCE.json：

- 2026-10-14的34459211已设100MHz、512 MAC/拍、64向量、16非线性；文件明确是可替换的参数模型，并非全芯片实测。
- 2026-10-22的v6（4e0d26b5）为16bank/16GB/s、SRAM80MHz。
- 2026-10-25的0855eab4改为64bank/64GB/s。更早粗模型也有64GB/s，不能说这个数首次来自本次优化。接口带宽仍是设计假设。

后来扩到4B模型时，普通算术资源仍沿用了这组小配置。现有证据不支持把它称为主流LLM加速器的推荐规模。512 MAC/拍×100MHz只有51.2GMAC/s；4.626G MAC/token仅计算就至少90.356ms。原来的结论应理解为小资源情景，而不是ASIC的普遍速度。

## 其他模拟器设置多少

没有统一默认值，应按目标芯片选择资源。

| 配置 | 存储层次 | 全设备接口参数 |
|---|---|---:|
| 我们原配置 | 8MiB共享SRAM、64个1RW bank | 64GB/s，读写共用 |
| LLMCompass A100 | 40MiB L2/global buffer | 5120B/拍×1.41GHz＝7219.2GB/s |
| LLMCompass MI210 | 8MiB L2/global buffer | 4096B/拍×1.4GHz＝5734.4GB/s |

这是[固定公开代码的参数](https://github.com/PrincetonUniversity/LLMCompass/blob/2e015fd2ee750e6cad8d7152df52551e5b41ef20/hardware_model/compute_module.py)，不是本轮实测。[矩阵排程](https://github.com/PrincetonUniversity/LLMCompass/blob/2e015fd2ee750e6cad8d7152df52551e5b41ef20/software_model/matmul.py#L1257-L1274)对读写都使用同一L2带宽，不是读写各自有7.2TB/s；它没有逐bank展开我们的1RW宏。MI210采用代码1.4GHz，不混用论文表1.7GHz。

**纠正早先口头参照：LLMCompass的TPUv3 global buffer为16GiB，承担外存抽象；460.6GB/s不能当片上SRAM带宽。** [外存接口配置](https://github.com/PrincetonUniversity/LLMCompass/blob/2e015fd2ee750e6cad8d7152df52551e5b41ef20/hardware_model/io_module.py)。ONNXim的sram_width=32是访问粒度，Sram::cycle没有展开服务时间，不能据此声称32GB/s。[代码](https://github.com/PSAL-POSTECH/ONNXim/blob/8599bee46b311fb267ac34b0677ad7db3d8a8ccd/src/Sram.cc)

本轮选512GB/s的直接依据是：权重经过共享SRAM写入和读出两遍，HBM连续读微基准约186GB/s，要承接这股权重流，片上接口粗略需要至少 **2×186≈372GB/s**。512GB/s留出一些其他读写余量，256/1024用于扫描。这是目标配置，不是55nm接口已经实现的证明。

## 改了什么调度

原路径已能预取下一块DRAM，但下一块共享SRAM填充等待当前块退休。新增digital_shared_prefill允许当前MAC运行时，把DMA已完成的下一块填入另一个共享槽；当前结果完成后，再读到唯一的本地操作数缓冲。预填充与当前输出仍竞争同一fabric；DMA较晚时当前输出优先。

没有扩大配对实验的本地容量。生命周期pending→staged→active→retired、防覆盖、动作守恒与排空均经测试。请求ready时间不等于实际资源预约start，不用“请求早到”冒充已经覆盖的周期。

16项总MAC恒为4,626,251,776，DRAM物理字节8,347,078,656，共享SRAM读写16,705,296,768。配对tile数量/动作/容量相等。**调度仅改变等待与重叠，没有减少算法操作数和数据流量。**

| 全部36层汇总部分 | 512 MAC/拍＋64GB/s原调度 ms | 8192 MAC/拍＋512GB/s预填充 ms |
|---|---:|---:|
{stages}

MAC理想下界为 {s['MAC_ideal_ms']:.3f}/{r['MAC_ideal_ms']:.3f}ms；SRAM裸传输下界为 {s['SRAM_ideal_ms']:.3f}/{r['SRAM_ideal_ms']:.3f}ms。MAC忙碌时间为 {s['MAC_busy_ms']:.3f}/{r['MAC_busy_ms']:.3f}ms；fabric忙碌时间为 {s['SRAM_fabric_busy_ms']:.3f}/{r['SRAM_fabric_busy_ms']:.3f}ms。忙碌时间可能重叠，不可直接相加。

即便扩大片上资源，HBM仍只有256GB/s理论、连续读约186GB/s；远低于之前LLMCompass A100的2039GB/s。8.347GB/token÷256GB/s就有32.61ms外存下界，不能期待自动达到A100约4.16ms的理想算子服务预测。

## 必须保留的假设

1. 8192/32768 MAC/拍要求本地权重供数16/64KiB每拍，即100MHz下1.6384/6.5536TB/s。单个本地缓冲容量有限，但bank、端口和布线未展开。不能理解为普通单端口64KiB SRAM。激活广播同样未标定。
2. macs_per_cycle同时作用于BF16和FP32 PV。向量64路、非线性16路、每tile启动2拍不变；不是完整复刻A100硬件。
3. E家族2048个已表征256×128bit宏，共8MiB，80MHz/SS不变，bank64/256/512/1024对应每bank32/8/4/2宏。F锚点128个4096×128bit宏。E家族裸宏面积约{s['SRAM_macro_area_mm2']:.3f}mm²，但新增bank选择、mux、fabric、布线和时钟树未标定，不是同面积比较。宏能跑80MHz不能证明整个宽接口达到该频率。
4. 本轮先在数字参考路径拆清因素；没有扩大随机FFN阵列、没有新PPL/RTL/STA/PT。Attention内部KV映射保持不变。HBM功耗参数无效，整机能耗/面积仍为null，不用时延收益代替能效收益。

## 复现和证据

实现resource_sweep.py、tile_pipeline.py、model.py；配置/源码/提交/Slurm回执在work/jieruiz/186/RESOURCE_*。运行submit_resources.py，采集collect_resources.py，校验analyze_resources.py，生成本文report_resources.py。

[16项表](results/resources_20261025/COMPARISON.csv)、[完整核验与阶段数据](results/resources_20261025/ANALYSIS.json)。Git只保留compact派生汇总、原manifest/execution及SHA；大型原RESULT与trace在本人服务器/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/resource_b01058f7/。所有36层、配置/原结果/源码SHA均核验。8项小模型门禁原件也按SHA验证。无真实权重/语料负载，不产生质量结论；已完成任务无需重跑。
'''
(D/'RESOURCE_SCHEDULING_ABLATION_ZH.md').write_text(text,encoding='utf-8',newline='\n')
print('Report generated')

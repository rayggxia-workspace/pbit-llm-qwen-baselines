# 对齐RK3588短输入的P-CIM核数预算

2026-11-27，Issue225/PR266，负责人rayggxia。只做资源选型，不修改decode默认，不启动GPU/EDA，不把新模型的形状估算当PPL或新整机TLM。

## 对齐的参考

[瑞芯微官方表](https://github.com/airockchip/rknn-llm/blob/main/benchmark.md)的RK3588/MiniCPM3-4B为W8A8：主要矩阵权重8位、激活8位；输入128token，生成64token；TTFT 1.40849秒、decode 5.94token/s。表格没有公开准确checkpoint revision、输入文本、各算子数制、板型和功耗。不能将W8A8解释为包括Norm/Softmax/累加器在内的所有状态都是8位。

本轮硬件估算采用同一公开模型的实际62层形状，而不只比较两个都叫4B的模型。[官方配置](https://huggingface.co/openbmb/MiniCPM3-4B/blob/main/config.json)中H2560、I6400、40头，q维度96、v维度64。按照[原始代码](https://huggingface.co/openbmb/MiniCPM3-4B/blob/main/modeling_minicpm.py)的MLA投影，逐层计算q_a 2560×768、q_b 768×3840、kv_a 2560×288、kv_b 256×5120和o 2560×2560。模型是发布的对话模型，不是另选Base。

权重/激活按主要矩阵W8/A8预算，数字累加INT32；P-CIM局部整数计数及64bit跨块状态不改。P8随机阈值、符号、尺度元数据是内部编码，不是额外的8位激活精度。一个signed A8数可将幅值映射为P8比较阈值，例如对称量化时2|a|；-128端点另处理。数值量化的scale/zero point和RKLLM未逐项核对，尚无该模型的概率路径质量结果。

输入长度取128，稠密因果Attention，不凭借K筛选/PV采样减少工作量。128输入的prefill只计算最后位置的全词表head以生成首token；64个生成token属于后续decode，不将192当作prefill长度。

## 外存、计算和缓冲

官方[固定频率脚本](https://github.com/airockchip/rknn-llm/blob/main/scripts/fix_freq_rk3588.sh)设NPU1GHz、DDR2112MHz；[ROCK5B硬件说明](https://wiki.radxa.com/Rock5/hardware/5b)为64bit、LPDDR4X4224MT/s，因此本轮采用33.792GB/s峰值，27GB/s有效情景，并扫描20/30GB/s。板型未披露，该配置是可核对的RK3588平台参考，不声称恢复了官方测试的内存轨迹。我们的片上仍28nm/250MHz，不免费升到1GHz。

- P-CIM：每核K64/M128/W8、8KiB权重、16个32×128bit bank，32拍装载；GU16/Wd32沿用18/34拍服务。每个权重tile处理32个独立token再换权重，128输入需要4轮读权重。
- 数字矩阵：8个已有16×16 WS整数阵列，复用同工艺已测16行任务131072MAC/2376ns的服务价，合计约0.883TOPS。该价格源为P8/符号接口，属于A8预算的已知实现参考，不冒称新INT8综合。数字后端按16行复用、8轮读权重，未额外赠送32行复用。
- 32路向量、2个state32 worker、1套编码服务。状态bank64×4KiB、16B/拍，合计256KiB和256GB/s。主表4–8核的活动状态均能装下；其他更大采样/复用情景按容量显式增加bank。
- 6核保存32行×128输出×64bit的活动状态载荷192KiB；这只是跨块状态，不是全部片上容量。另预算MiniCPM3约1MiB共享激活/数字操作数工作区，容纳32行x/g/u编码、残差、数字双缓冲和16KiB DMA等；Qwen形状需要约1.25MiB。Attention可分块、按阶段复用工作区；完整bank/队列回放尚未执行，不声称已证最小SRAM。

## 核数与时间

MiniCPM3-4B/128输入共31,744,000个GU帧、15,872,000个Wd帧，乘加计数与矩阵形状独立核对一致。单核纯FFN服务为：

`(31,744,000×18 + 15,872,000×34) / 250MHz = 4.44416核秒`

这不是整机时间；还需要权重编程、状态更新、数字投影、因果QK/PV、向量/尺度/编码、动态中间量搬运及最后位置head。

|P-CIM核数|FFN服务|其他服务|128输入首token服务预算|
|---|---:|---:|---:|
|4|1.159s|0.455s|1.614s|
|5|0.927s|0.455s|1.382s|
|6|0.772s|0.455s|1.228s|
|8|0.579s|0.455s|1.035s|

因此本模型下5核是该预算的临界点；建议6核作为候选。6核在20/27/30GB/s有效外存下分别约1.327/1.228/1.219秒。8核若状态读/更新/写不能流水重叠，时间约1.210秒，不能继续按核数线性缩短。6核当前阶段上限不依赖这项理想重叠。

6核的0.455秒包括：数字投影约0.248秒、QK/PV/Softmax约0.028秒、Norm/RoPE/残差代理0.091秒、FFN编码0.053秒，以及动态中间量/最后head等搬运。Norm与Softmax的操作代理、实际矩阵利用率、供数/状态释放仍需代表性prefill回放；当前不是测得的TTFT。

作为独立尺度参考，Qwen3-4B在相同128输入/W8A8/数字后端下，4/5/6/8核分别约1.459/1.254/1.118/0.947秒。不得把它们与MiniCPM3官方结果直接计算加速比。

## 采样数改变时

沿相同其他资源和1.40849秒目标，条件最小P-CIM核数为：GU8/Wd32约4核，16/32约5核，32/64约10核，64/128约18核。核数增加时活动状态容量/端口同样显式增加。这些是硬件服务预算，不证明MiniCPM3在任一采样预算下达到原模型质量；推荐6核的前提是16/32质量可接受。

本轮建议是6个P-CIM核+8个小型INT8 WS阵列的短输入候选，而不是原2048输入、1–2秒目标的96/192核配置。没有改当前decode/RTL默认，没有新PPA、真实输入推理或64-token生成测试；当前21bit局部价仍需标定，旧19bit面积只保留参考。官方协议没有披露的模型/文本/内存细节，不补造为已对齐。

复算：`python -B architecture_tlm/process_28nm/prefill_core_sizing_20261127/rockchip_match.py`。依赖同目录AREA_REVIEW_INPUTS.json，原estimate/RESULTS/INT8_AREA_REVIEW不改。结果ROCKCHIP_MATCH_RESULTS.json/sha包含模型形状、分项、带宽和采样灵敏度；没有权重/数据集身份，因为没有运行模型数值评测，模型配置按本日公开结构读取。

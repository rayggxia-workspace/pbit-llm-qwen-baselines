# 解码速度与带宽口径核对：我们的17.4 token/s为什么较低

日期2026-10-30；Issue212 / PR214补充。复用封存结果及公开一手文献，没有新GPU、TLM、RTL、EDA或PPL实验，不改变现有默认和他人调度实现。

**结论：不能把差距主要解释成batch或55nm。相关FPGA工作中多项明确是B1；我们当前主要受外存供数、片上搬运/有限调度以及随机FFN处理链影响。工艺关系到实际可达时钟和PPA，但现有500MHz是尚未全面STA的目标，本结果没有额外施加一个“55nm慢若干倍”的惩罚。**

## 1. 先将能比较的指标分开

|对象|模型与权重|batch / 上下文|主要外存带宽|速度 / 证据|
|---|---|---|---|---|
|当前TLM封存候选|Qwen3-4B，FFN W8，其余矩阵BF16|B1 / 2K|HBM2峰值256GB/s|17.41token/s、57.445ms；合成事务模型，500MHz目标|
|本项目RTX5090原生连续生成|同后训练Qwen3-4B原BF16|B1 / 从2K开始，生成256步|GDDR7峰值1792GB/s|44.00token/s、22.726ms；已测|
|本项目RTX5090静态KV Graph|同原BF16|B1 / 固定2K|同上|100.57次/s、9.943ms；固定前向，不是连续生成|
|嵌入式LLM加速器[1]|Llama2-7B，W4/KV8|单序列解码，最长1K|单64bit DDR4-2400，19.2GB/s|4.9token/s；真实板卡，300MHz|
|Hummingbird KV260[2]|Llama3-8B，W4/KV8|B1，prefill:decode=32:32|单64bit DDR4-2400，19.2GB/s|4.8token/s；真实板卡，300MHz|
|Hummingbird ZCU104[2]|同上|同上|两个64bit DDR4-2133接口，约34.1GB/s|8.6token/s；真实板卡，266MHz|
|Hummingbird U250[2]|同上|同上|四64bit DDR4-2400接口，76.8GB/s|19.4token/s；真实板卡，300MHz|

此57.45ms封存候选配置为500MHz、32×64×64随机tile、2048MAC/拍、8MiB SRAM；Attention是筛选＋准确Softmax＋PV采样，不是最新赢家保持/校正拒绝Ising，也不是所有新模块接入后的最终时序。

此表是口径核对，不是同模型/质量/面积的性能排名。Hummingbird的短上下文、W4和输入embedding卸载方式，与我们2K及混合位宽不同。它自报的91–94%带宽效率使用其模型大小/权重口径，不能与我们的物理总流量比例直接作同定义排名。

## 2. 带宽数来自哪里

DDR峰值=通道数×数据率(MT/s)×每通道有效数据位宽/8。已是MT/s时不再乘2；rank、bank、DIMM数量不自动等于独立通道。U250为4×2400×8=76.8GB/s；ZCU104使用PS和PL两条独立接口，合计约34GB/s，而不是只靠增加rank。

HBM的460GB/s、256GB/s分别是论文平台规格与我们的DRAMSys配置峰值。DDR与HBM同板并存时不能选较小的DDR数来解释HBM上的推理。RTX5090推理主要读GDDR7，不按主机DDR带宽计。[3][4]

FlightLLM[3]确实B1，U280真实实现225MHz；其HBM为460GB/s，另有38GB/s DDR。权重平均约3.5bit并结合稀疏化。其always-on-chip decode主要保留中间激活，不代表全部7B权重都常驻片上；VHK158部分为模拟器结果，不能混成两平台都已实测。没有从后续论文重列的约55token/s冒充原文单个确定配置的直接数值。

## 3. 我们到底用了多少带宽

三个原封存RESULT_SUMMARY的SHA逐项核验；独立按36层矩阵形状重算，W8 FFN+BF16 QKV/O/lm_head单遍字节数与逻辑/物理权重流量完全相同：5,354,946,560B，即5.355GB。没有因为T64/T128采样而重复读64/128遍权重。三seed平均总外存5.489678GB/token，权重占97.55%。

|诊断量|值|含义|
|---|---:|---|
|配置峰值|256GB/s|DRAMSys HBM2 8通道×2伪通道|
|整token平均有效物理流量速率|95.56GB/s|总物理字节/整token时间，约峰值37.3%|
|纯搬运理想时间下限|21.444ms|总字节/峰值；忽略所有其他限制|
|实际TLM时间|57.445ms|约为上述理想下限2.68倍；不能将差额全算可消除浪费|
|外存DMA资源忙时|39.803ms|约69.3%的整token时长；不是等待在关键路径上的独占比例|
|共享SRAM fabric忙时|15.286ms|可与其他资源重叠，不能与上行相加|
|普通数字MAC资源忙时|1.576ms|配置2048MAC/拍×500MHz，峰值1.024TMAC/s，按2OP/MAC为2.048TOP/s|
|FFN GU采样/计数忙时|2.131ms|受采样、并行度和归约时序影响|
|FFN AND→Wd采样/计数忙时|5.800ms|与其他服务可能重叠|

原审计忙时来自同三seed报告，各行相互重叠；不能相加或直接从TPOT减去某行预测优化。外存/片上事务调度中仍有有限DMA响应槽、tile驻留与退休、共享端口、编程/恢复及反馈依赖。需要同字节流量的调度消融才能量化哪项可以回收。当前并未证明全局最优，也不能说只剩HBM极限。

## 4. batch、位宽、工艺分别解释什么

- **batch：** 上表涉及的嵌入式结果及FlightLLM是单请求/单batch，不是统一由大batch造成差距。LLMCompass[6]的传统DRAM吞吐方案是另一口径：总带宽1TB/s、尽可能大的batch；报告吞吐提高1.42倍，同时延迟差9.21倍。大batch不等于单用户出词快。
- **权重流量：** 当前混合存储平均约10.65bit/矩阵权重，不是全W8，更不是W4。即使只有4B参数，读取量仍可能大于W4的8B模型。低位是不同协议，不能直接继承其质量。
- **带宽：** 5090为1792GB/s，约是本TLM256GB/s的7倍；核心GHz或工艺节点不能代替这个差异。本项目GPU原生比TLM快2.53倍；固定Graph快5.78倍，后者不是连续生成吞吐。
- **工艺/频率：** 55nm影响500MHz能否落地、单元面积、能量与布线；但本TLM先假定500MHz，不能将其已出现的低吞吐归因为一次尚未建模的工艺降频。FPGA225–300MHz也能靠供数/数据流取得更高吞吐，频率不是充分指标。
- **随机计算：** 64/128采样及恢复/编程确实增加本地服务，不能全说成存储问题；但数字MAC忙时仅1.58ms也说明只扩大MAC并非当前最有依据的提速手段。不能从资源忙时单独证明全部延迟归因。

## 5. 官方GPU表还有一个常见误读

Qwen官方[5]使用B1，但Speed=(输入token+输出token)/总时间，输出2048token。Qwen3-4B/H20输入1时HF45.94、SGLang133.13token/s接近以decode为主的短prompt测试；输入63488时BF16 SGLang1423.98token/s包含大量prefill，绝不能倒数为0.70ms纯decode TPOT。我们的44.0token/s原生HF与官方短prompt HF约45.9处于同一量级，环境/上下文不同，不作为严格复现。

因此既存在batch混用，也存在prefill/decode、每层/整模型、低位/原精度、单芯片/整系统、实测/仿真的混用。逐项核对后，上表DDR结果不构成“5GB权重用20GB/s就能普通B1几十ms”的反例。

## 6. 下一步最有信息量的对照

保持当前模型、字节数、B1、FFN采样及计算资源，用相同标准DRAMSys重放4/8通道DDR4-2400/3200，再与现有HBM比较；优先记录实际各通道利用率、请求连续性、在途数、DMA/片上供数停顿及完整TPOT。只改变存储配置，不能同时更改位宽和batch后归因为DDR优化。

另一条独立消融才是改变tile重叠、局部端口/供数，或更新FFN模块；每次保存实际选择的版本。还需要相同资源/调度/存储的全数字对照，不能将不同频率或早期资源的旧基线混作本轮概率加速倍数。500MHz关键模块STA、PHY/controller、质量匹配仍单列。本次没有执行这些新情景，没有将搬运下限当作已达到的系统速度。

## 来源

[1] [Pushing up to the Limit…，§VII/TableII](https://arxiv.org/html/2502.10659v1)。

[2] [Hummingbird，§V/TableV](https://arxiv.org/html/2507.03308v1)。

[3] [FlightLLM，§4/§6/Table2/5](https://arxiv.org/html/2401.03868v1)。

[4] [NVIDIA RTX50官方规格说明](https://www.nvidia.com/en-us/geforce/news/rtx-50-series-graphics-cards-gpu-laptop-announcements/)。

[5] [Qwen官方速度测试及Notes](https://qwen.readthedocs.io/en/latest/getting_started/speed_benchmark.html)。

[6] [LLMCompass公开v1，§V-B](https://arxiv.org/html/2312.03134)。

自身来源：GPU科学8ea8d0f4，TLM FMA2仅重计价b516e1d9，原时序PR192；旁边GPU_AND_TLM_MODULE_COMPARISON_ZH_20261030.md保留原汇总。各输入原字节SHA及机器可读计算见同目录BANDWIDTH_AND_SPEED_AUDIT_20261030.json。外部来源采用指定版本URL/章节，未保存整篇原件SHA，未声称封存完整PDF。模板/自研宏估计不升级为实测芯片或同质量胜负。

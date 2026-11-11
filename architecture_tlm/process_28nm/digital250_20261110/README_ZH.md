# 28nm250：沿用55nm三组数字基线

2026-11-10，Issue225 / PR249，依赖Issue236/204/198既有模块。此处与概率版独立，不修改已提交概率快照；新增P8/W8全定点数字CIM保留研究参考，不替代这三组。

|方案|FFN|Attention|共享FMA|近等总面积mm²|
|---|---|---|---:|---:|
|BF16_dense|BF16矩阵、FP32反馈、数字SwiGLU|稠密在线Softmax＋完整PV|576路|6.449627|
|W8_dense|A9/W8 GU＋PoT/INT64；BF16非线性；BF16 z×W8PoT Wd|同上|448路＋16个整数GU|6.369820|
|W8_screen|同W8_dense|同概率SparQ r32/K128/local32，数字Softmax＋完整PV|448路＋16个整数GU|6.399385|

共同目标面积6.480303mm²，分别低0.47%/1.70%/1.25%；按合法4片FMA16粒度选择不超预算点，不用空逻辑填面积。数字侧可重排相同SRAM；没有要求FFN、Attention分别等面积，也没有复制共享FMA池。W8路径是历史混合数制，不能称为纯权重量化或全定点数字CIM。

共同条件：Qwen3-4B后训练revision1cfa9a7208912126459214e8b04321603b3df60c，B1/2K/36层/151936词表；28nmTT0.9V25C、250MHz；相同原生LPDDR5-derived8533/136.4606GB/s峰值、DMA16KiB返回保持、256信用。一个确定性seed17；数字输入/计分不需要模型权重，此处不是PPL或文本推理。

## 实际接入

- 复用冻结current_mainline.digital_install、FFN async_adapter、Attention finite onlineSoftmax/PV，以及相同native内存桥；没有按旧结果比例缩放时间。
- BF16与W8双模式FMA、整数GU、BF16非线性、归约、转换和标量Softmax全部绑定已有28nm价卡；旧适配器的area55字段仅保留API拼写，数值是28nm、面积系数1，不乘0.81。FFN_SOURCE_PROFILE绑定原价卡/报告SHA。
- 相同30×8KiB＋148×4KiB共832KiB/178个真实1RW宏。数字Attention每组48KiB、8组384KiB；前端448KiB，82端口；Attention96端口。释放不用的SC跨K96KiB，256KiB原CIM区域复用于数字FFN scratch与投影权重，激活96KiB、norm32KiB、普通槽64KiB。每个物理bank/row逐字穷举无重叠，实际读写沿有限端口仲裁，不保留被删除端口。
- 共享BF16池由投影、FFN、QK/PV、head共同租用。C4反馈、有限输入FIFO/两个结果信用、双缓冲及消费后释放沿既有实现；整数GU使用含PoT/INT64/出口的完整动作价，不重复加state32。
- FP32统计、BF16概率权重、BF16V/FP32累加；概率写入BF16的RNE动作单列。不把FP32乘法免费套BF16 FMA。特征TopK按每Q计，组内四Q的服务与动作均展开。

run.py执行原生或解析后端；层数与完整head实际循环，含/扣head由同一执行final_norm前缀分账。通过完整工作量、字节、SC硬件不活动、共享池/队列排空、面积和能量加和检查后才写SEAL。

## 仍属估计的部分

在线Softmax组合控制、暂存捕获活动、转换wrapper及标量流水沿显式宏合同/原语代理，不是完整新RTL；平台DMA/向量/分发沿概率版40mW和具名DFF/逻辑面积。S2动态为S0测量＋库时钟差估计，非独立PT。控制面积/活动有具名预留，不加全局15%。输入是同一代表性候选和合成max变化，不宣称真实文本PPA或质量匹配。

外存能量按4/6.6/8pJ/bit分开，时序来自native桥；PHY/pads/CPU/package/完整CTS/SPEF等仍在共同边界外。报告是条件架构比较，不是完整物理芯片签核。

## 作业与恢复

提交/输出/SHA、门禁和最新状态见work/rayggxia/225/digital250_20261110/HANDOFF.md、SUBMISSION.json、STATUS.json。每组先原生一层＋384head门禁；aftercorr自动执行36层＋完整词表。无GPU、训练或新增RTL/PT。

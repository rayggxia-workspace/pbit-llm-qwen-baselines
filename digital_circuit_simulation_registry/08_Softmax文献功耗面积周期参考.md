# Softmax文献功耗、面积和周期参考（2026-10-28）

这是文献参考，不是本项目新仿真。负责人rayggxia，Issue198 / 草稿PR199；保留原工艺值，不应用SHARK制造面积×0.81规则。

整行周期表示处理一行输入至输出完成的拍数；时钟周期表示每一拍的ns。未知值写“未核实”，不填0，也不从Fmax或每元素吞吐反推整行延迟。

## 512元素：45nm FreePDK45，布局前综合

| 实现 | 输入/存储 | 整行周期 拍 | 频率 MHz | 时钟周期 ns | 面积 µm² | 功率 mW | 整行时间 µs，cycles/f |
|---|---|---:|---:|---:|---:|---:|---:|
| fixed32 LUT，P1 | 512 / NOREG | 1542 | 250 | 4 | 59000 | 未核实 | 6.168 |
| fixed32 LUT，P2 | 512 / NOREG | 775 | 250 | 4 | 85000 | 未核实 | 3.1 |
| fixed32 LUT，P4 | 512 / NOREG | 392 | 250 | 4 | 138000 | 未核实 | 1.568 |
| FP16 DesignWare，P8 | 512 / NOREG | 199 | 250 | 4 | 283300 | 8.38 | 0.796 |
| FP16 LUT，同频，P8 | 512 / NOREG | 201 | 250 | 4 | 220178 | 6.87 | 0.804 |
| FP16 LUT，最高频，P8 | 512 / NOREG | 201 | 294 | 3.40136 | 279711 | 10.19 | 0.683673 |
| fixed32 LUT，P2，含REG | 512 / REG | 775 | 250 | 4 | 828000 | 未核实 | 3.1 |
| fixed32 LUT，P4，含REG | 512 / REG | 392 | 250 | 4 | 835000 | 未核实 | 1.568 |

fixed32/LUT是定点近似；FP16是IEEE half，非BF16。NOREG依赖外部片上输入存储，不含完整本地输入缓存；REG计内部输入寄存器。fixed32各行未取得总功率，Table IV的“Add.energy”是附加访存/寄存能量，不能填成总能量或功率。工艺电压/温度未核实，不与本项目SS/TT条件等同。

整行时间统一按cycles/f计算；保留原周期与频率。原文延迟小数与该商存在差异，尤其294MHz行，不用印刷小数覆盖周期数据。若只换算到100MHz，上表依次为15.42、7.75、3.92、1.99、2.01、2.01、7.75、3.92µs；这是算术，不是新STA。

来源：[Wei等，ASAP2020，最终PDF第7页Table III/IV](https://utw10244.utweb.utexas.edu/pubs/SoftMax___ASAP2020_June27.pdf)。本机原PDF SHA已保存于REFERENCE.json；原文表格已视觉核验。

## 其他工艺与近似方案

| 方案 | 工艺 | 输入长度N | 整行周期 拍 | 面积 µm² | 面积/时序频率 MHz | 时钟周期 ns | 功率 mW | 功耗测试频率 MHz |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Li2024，α1近似 | 65nm CMOS，厂商/PVT未核实 | 未核实 | 未核实 | 2336 | 200 | 5 | 0.19 | 200 |
| Li2024，α4近似 | 65nm CMOS，厂商/PVT未核实 | 未核实 | 未核实 | 2492.4 | 200 | 5 | 0.19 | 200 |
| Li2024表内对照[30] | 65nm CMOS，厂商/PVT未核实 | 未核实 | 未核实 | 3051.6 | 200 | 5 | 0.23 | 200 |
| ITA整数Softmax | 22nm GF22FDX FD-SOI | 未核实 | 未核实 | ≈5709 | 500 | 2 | ≈0.847 | 500 |
| ConSmax v3内普通Softmax对照 | 16nm，commercial EDA | 256 | 未核实 | 11000 | 909 | 1.10011 | 1.5 | 500 |
| ConSmax v3内普通Softmax对照 | 130nm，commercial EDA | 256 | 未核实 | 180000 | 285.71 | 3.50005 | 51 | 80 |

- Li2024采用定点指数/除法近似。5ns为单拍，不是整行延迟；200MHz由5ns求倒数。当前仅取得出版方PDF索引表5/7，原PDF下载失败；位宽、输入长度、PVT、缓冲范围和整行拍数待核。来源：[Science China原文](https://scis.scichina.com/en/2024/200404.pdf)，[DOI](https://doi.org/10.1007/s11432-024-4137-4)。
- ITA为8bit整数近似。5709µm²由整核0.173mm²×3.3%估算，0.847mW由60.5mW×1.4%估算，两项比例均有取舍误差。论文另报28.7kGE，不能误当µm²。500MHz目标STA为SS/0.72V/125°C；功耗为TT/0.80V/25°C、500MHz。这里不是512元素独立核。来源：[ITA v1，第5页](https://arxiv.org/abs/2307.03493v1)。
- ConSmax表中引用的是普通DesignWare Softmax对照，非ConSmax本体。工作负载256元素；面积在Fmax条件、功耗分别在500MHz/80MHz，不能混配成同频结果；位宽与整行周期待核。来源：[ConSmax v3，表I](https://arxiv.org/html/2402.10930v3)。

## 文件与使用边界

- [REFERENCE.csv](references/softmax_20261028/REFERENCE.csv)：14个点，可直接筛选工艺和周期。
- [REFERENCE.json](references/softmax_20261028/REFERENCE.json)：单位、来源、PDF SHA、功耗频率、推算说明与未知值。
- [完整调研](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/e73e50abc414c7b5ebd442a5c0f515880260236e/architecture_tlm/attention_compare_20261027/SOFTMAX_DIGITAL_SURVEY_ZH_20261028.md)：数字Softmax与Ising采样的比较范围和后续建议。
- 不把文献参考放入records当成本机run，不改既有仿真数值或run总数，不自动改TLM能耗系数；位宽/精度、存储、输入规模、PVT和采样质量需匹配后比较。
- 复现：仓库根运行 `python -B work/rayggxia/198/build_softmax_reference.py`。数据版本来自上轮已发布调研，文献原件仍在授权本机私有归档；本次没有新增EDA或模型实验。

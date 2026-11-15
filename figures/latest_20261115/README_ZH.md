# 论文图稿最新版（2026-11-15）

本目录集中保存本轮核对的可编辑主文件。PPT 与当前本地工作文件逐字节相同；保留主文件内的历史页，**请按下表的“最新版页码”查看**，不要把文件内部旧页当成当前方案。PNG 仅为该页预览。

| 图 | 内容 | 可编辑文件 | 最新版页码 | 预览 |
|---|---|---|---:|---|
| Fig1 | p-bit 与 LLM 概念图 | [Fig1.pptx](Fig1.pptx) | 1 / 71 | [PNG](Fig1.png) |
| Fig2 | 整机硬件架构 | [Fig2.pptx](Fig2.pptx) | 1 / 32 | [PNG](Fig2.png) |
| Fig3 | Attention 结构 | [Fig3.pptx](Fig3.pptx) | 1 / 1 | [PNG](Fig3.png) |
| Fig4 | 采样分布及 Attention 输出误差 | [Fig4.pptx](Fig4.pptx) | 9 / 9 | [PNG](Fig4.png) |
| Fig5 | Attention 质量、PPA 与 KV 流量 | [Fig5.pptx](Fig5.pptx) | 1 / 17 | [PNG](Fig5.png) |
| Fig6 | P-FFN 与 P-CIM 结构 | [Fig6.pptx](Fig6.pptx) | 1 / 29 | [PNG](Fig6.png) |
| Fig7 | FFN 电路对照与能量/面积分解 | [Fig7.pptx](Fig7.pptx) | 1 / 9 | [PNG](Fig7.png) |
| Fig7_16lane | Fig.7 的 16-lane 备选 | [Fig7_16lane.pptx](Fig7_16lane.pptx) | 1 / 9 | [PNG](Fig7_16lane.png) |
| Fig8 | FFN 采样质量 | [Fig8.pptx](Fig8.pptx) | 1 / 1 | [PNG](Fig8.png) |
| Fig8_5 | 后训练结果汇总 | [Fig8_5.pptx](Fig8_5.pptx) | 1 / 3 | [PNG](Fig8_5.png) |
| Attention_training | Attention 训练及联合采样补充结果 | [Attention_training.pptx](Attention_training.pptx) | 1 / 3 | [PNG](Attention_training.png) |

Fig.3 另附 [draw.io 源文件](Fig3.drawio)。主图稿与补充/备选已分开标识；不把 Fig7_16lane 作为另一张主 Fig.7。Attention_training 共三页为不同结果，三页均保留。

## 范围与读图口径

- Fig.5 第1页包含 K64/K128/K256/All keys 四条 PPL 曲线；KV traffic 与 Attention energy 的百分数均以稠密 Attention 为共同分母。
- Fig.4 当前第9页采用同 P8 量化目标；示例分布是选出的展示案例，不能代替全部输入的统计。
- PPA/TLM 数值保持源图的估计、仿真及模块边界；本次只是图稿发布，没有重跑实验或重新验收图中科学结论。
- Fig.9、Fig.10 尚未在项目 figures、Downloads 和 Codex 输出中定位到独立成稿。Fig.11 已有三模型数据说明，尚未定位到独立 PPT；本次不拿早期参考文献图片或白板照片补号。
- 不包含临时锁文件、build/source/before 等备份、他人论文截图合集、模型权重、工艺库、网表、波形或访问凭据。

[SHA-256 清单](MANIFEST.json)。工作文件以后可能继续编辑，本目录是有日期的上传快照。

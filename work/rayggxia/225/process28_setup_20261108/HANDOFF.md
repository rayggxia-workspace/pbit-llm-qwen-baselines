# Issue225：28nm工艺目录准备

2026-11-08，负责人rayggxia；分支task/225-tlm-unified250-20261107，PR249，base task/225-norm-stream-20261106。用户只要求先建目录，不提供完整TLM；沿既有28nm组件消费范围接续，不重复Issue204的电路工作。

本地源码architecture_tlm/process_28nm/六文件、辅助build.py/delivery.py。根工作区同路径已同字节镜像。250包含最新合格A9同步复位以及FFN/BF16；原A9异步和500失败不晋升。来源准确字节SHA与本地路径在SOURCE_INDEX；未复制工艺库、波形、网表、原报告或整个owner源码。四来源SHA/PVT/面积×1、同步A9/空整机值检查通过，无新PT/TLM运行。

28nm SRAM、Attention/Ising/向量/转换/DMA/CIM接口/互连仍待对应工艺模块标定与资源分配；外存可显式复用原LPDDR边界，不随工艺自动加速。500MHz的零setup uncertainty只是条件推算，不是新STA。后续先完善组件，再做时钟/资源/等面积映射与Qwen锚点；不把55nm剩余模块缩放后冒充完整28nm结果。当前full_system_ready=false、整机值null；不改全局默认或55任务。

发布仅本目录、小型索引、当前STATUS及本交接，回执PUBLICATION.json记录准确commit和读回核验；PR保持draft/open/unmerged，Projects待维护者同步。根备忘录/阅读镜像已同步。三模型status属于Issue245，不将其运行结果写成28nm数据。

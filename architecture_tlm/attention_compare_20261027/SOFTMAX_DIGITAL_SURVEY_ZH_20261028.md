# 普通数字Softmax周期与面积调研

2026-10-28；rayggxia；Issue198 / 草稿PR199。文献、开源代码与算术换算；本轮没有新增RTL、EDA或真实模型实验，不新增数字仿真run。入口代码提交e40db25705bd44a2d707ab6aa9f0ac68da843446；本任务已有服务器结果另见control_v2/eda_20261028/RESULTS_ZH.md。

## 可直接用于512元素预算的公开数据

[Wei等，ASAP 2020，Design Space Exploration for Softmax Implementations](https://utw10244.utweb.utexas.edu/pubs/SoftMax___ASAP2020_June27.pdf)，第7页Table III/IV；原文45nm FreePDK45综合，未布局布线。以下均为一行512输入；NOREG依赖外部片上输入存储，不包含完整本地输入寄存器缓存。

|格式/算术|并行路数P|整行周期|原频率MHz|原频率下时间µs，按周期换算|原面积mm²|若100MHz的时间µs，仅周期换算|
|---|---:|---:|---:|---:|---:|---:|
|fixed32 / LUT|1|1542|250|6.168|0.059|15.42|
|fixed32 / LUT|2|775|250|3.100|0.085|7.75|
|fixed32 / LUT|4|392|250|1.568|0.138|3.92|
|FP16 / DesignWare EXP、LOG|8|199|250|0.796|0.283300|1.99|
|FP16 / LUT，同频设计|8|201|250|0.804|0.220178|2.01|

fixed32三行是同一格式的并行度比较；FP16两行独立比较，不能把整表当同精度曲线。FP16是IEEE half，非BF16；DesignWare是有限精度高准确度参考，也不是实数精确计算。论文印刷延迟有小数取舍，本表统一cycles/f。假定外部存储一拍提供P个元素，访问费用需另计。Table IV的P2/P4加入内部寄存器后，面积分别为0.828/0.835mm²；不能把NOREG面积说成完整缓冲模块面积。[来源及DOI](https://doi.org/10.1109/ASAP49362.2020.00017)

## 小面积定点方案与其他锚点

|原论文方案|工艺|原面积|周期证据与限制|
|---|---|---:|---|
|Li等2024，α=1 / α=4；Table5|65nm|2336.00 / 2492.40µm²|时钟周期5ns；未取得可逐页核验的整行周期，不能说512元素只需5ns|
|同表的对照设计[30]|65nm|3051.60µm²|同表5ns时钟；不是FP16高准确度实现|
|ITA整数Softmax|22FDX|28.7kGE；约0.005709mm²|后者由整核0.173mm²×3.3%推算，有比例取舍误差；512整行周期未给出|
|ConSmax v3论文中的普通Softmax对照，非ConSmax本体|16nm / 130nm|0.011 / 0.18mm²|商业EDA表I；Fmax909 / 285.71MHz不是整行吞吐；工作负载256元素，位宽与整行周期未核实|

[Li等，Science China Information Sciences，2024](https://scis.scichina.com/en/2024/200404.pdf)，DOI [10.1007/s11432-024-4137-4](https://doi.org/10.1007/s11432-024-4137-4)。采用指数截断及除法近似；面积仅作定点小算术核锚点，存储边界待核。本机多次下载失败，记录来自出版方PDF的搜索索引Table5/7，未完成原PDF视觉复核；不采纳转载网站补充的位宽/整行延迟作为已验证主证据。

[ITA，arXiv:2307.03493v1](https://arxiv.org/abs/2307.03493v1)，第5页。整数近似，不是浮点Softmax；面积为其特定阵列内模块，不能当一个任意长度独立核。[ConSmax，arXiv:2402.10930v3](https://arxiv.org/html/2402.10930v3)，第7页表I：这里只引用普通Softmax对照。该表功耗测试频率16nm为500MHz、130nm为80MHz，与面积/Fmax条件不同；不用其Fmax反推整行延迟。ConSmax自身改变归一化并训练参数，不能作为普通Softmax精确基线。

## 周期如何随长度、并行度变化

常规三遍结构：找max；求exp与分母；输出归一化结果。每拍P元素、算术可流水、无存储阻塞时，可用 C≈3×ceil(N/P)+流水尾部 作为该类结构的预算式。上表fixed32对应尾部6/7/8拍、FP16 DW为7拍；不是所有结构的统一定律。在线max/分母可合并遍历，倒数延迟及反馈依赖须按实际电路处理。吞吐II、首输出延迟和末输出延迟分别记录。

相同P下，N由512扩大到2048/8192时，扫描主项约增加4/16倍，单核算术面积不必同比增长；缓冲容量/地址位宽/累加位宽与带宽则须重新检查。这是结构推算，不是新增PPA。512×16bit输入容量为8192bit，512×32bit为16384bit；寄存器实现与SRAM宏面积不可混用。

## 与本项目Ising采样比较的含义

当前主候选G16融合控制的SHARK原面积0.044406360mm²，按用户制造规则×0.81为55nm折算0.035969152mm²。它不含完整p-bit源、驱动和全Attention；所有候选的hold违例仍未闭合。之前约6–12µs是N512、S512、B16、100MHz、每拍全p-bit可更新等假设下的条件预算，不是新端到端STA结果。

因此，不能从跨工艺文献算面积倍数胜负，也不能据199拍就断言数字路线端到端更快：数字表是生成概率，Ising预算是生成多次地址，数字采样器/随机源/存储访问及相同质量需要的S还未闭合。现有数据说明“数字Softmax必然很大很慢”不成立；高准确度FP和小面积定点近似都需保留为对手。

只需要采样地址时，还有一个应实现的数字对手：令w_i=exp(x_i−m)、Z=Σw_i，CDF累计w_i并与uZ比较，便可在数学上按softmax分布抽样，无需先逐项形成w_i/Z。有限位宽、随机数离散、CDF和存储成本仍要计入；数学分布等价不保证有限精度下与指定FP概率逐bit一致。此处是推导建议，未实现、未仿真。

后续建议在同一SHARK库比较：①有限精度高准确度FP16/BF16数字参考，明确exp/倒数与累加格式；②ITA类整数近似；③直接未归一化权重CDF采样。固定N、P、输入/输出带宽、存储边界、PVT、S和质量指标后再综合。用户×0.81只用于本项目指定制造流程原面积，不用于上述45/65/22/16/130nm文献，不缩放时间或功耗。本轮未启动这些EDA实验。

## 代码、证据与恢复

- [SoftGen源码](https://github.com/UT-LCA/softmax/tree/8149274c79149a9262c2aa1bd3f04953cf67eded)：锁定8149274c79149a9262c2aa1bd3f04953cf67eded，generator支持P、mem/reg、float16/fixed32、lut/dw；完整430项tree无LICENSE/COPYING命名文件，复用许可待核，不向本库搬运第三方源码或DesignWare库。
- [ITA源码](https://github.com/pulp-platform/ITA/tree/ba96519becce195d64e85eb9a5302e8a1d5487e7)：锁定ba96519becce195d64e85eb9a5302e8a1d5487e7；硬件Solderpad0.51。源码包含近似移位指数和两个串行除法实例，整行时间需按其控制/阵列调度验证。
- 准确原PDF大小、SHA、页码、开源blob与算术表：SOFTMAX_DIGITAL_SOURCES_20261028.json。PDF/阅读渲染与代码阅读快照仅在已有授权本机project_archives/attention_compare_issue198_20261027/softmax_survey_20261028，不在Git公开PDF或第三方代码。下载失败历史保留。
- 辅助下载脚本work/rayggxia/198/research_softmax.py；不是硬件复现实验。模型/文本/seed/精度计分清单对此次纯调研不适用；后续模型比较仍执行Instruct及匹配BF16/语料SHA门禁。Issue/PR待审状态见工作目录SOFTMAX_PUBLICATION.json；Project看板写权限未核验，待维护者同步。

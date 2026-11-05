## 2026-10-28 Issue204：已找到完整28nm BF16数字阵列功耗证据

rayggxia，task/204-bf16-baseline / PR209接续，源起点d6aa128997072acd837508c7703844bf950603ec。用户要求确认是否没有28/55nm BF16数字矩阵依据、缺乏时再自建仿真。二轮已找到MFSA完整正文和FlexBlock作者PDF，纠正首轮检索不足；两原PDF及表II/V原图已下载、SHA绑定、渲染核对。当前入口architecture_tlm/bf16_baseline_20261028/README_ZH.md、LITERATURE_RECHECK_ZH.md及literature_recheck.py。

MFSA2026-10-14预印本：28nm SS0.72V/125℃/1GHz，16×16全格式数字阵列，BF16输入/FP32累加；后布线RC+LLM门级轨迹稳态估算1.85W/1.024TOPS，排除reset/预装/排空。两op/MAC由256PE×两项×1GHz核验，得3.61328pJ/MAC、231.25pJ/64MAC；对SC54核69.4633pJ为3.329倍，仅异工艺/异精度/异边界归一，非N64冷启动延迟或整片节能。原73pJ摘要换算保留低完整度版本，不作为唯一参考。

FlexBlock作者文件头为2203.06673v1：65nm BF16 SA128×128、333MHz、9.84W、1.77TFLOPS；P/T约711.59pJ/64MAC，但吞吐只占乘法器理论峰值16.22%，属含利用率/周期模型的负载归一，不能据此宣布10倍优势；SRAM另CACTI。外部65nm面积不套本项目0.81。55nm严格同PVT/数据/接口仍未找到已核验匹配项，不断言不存在。

有了可用28nm参考，用户“确认没有才自建”的条件未成立，本轮未启动新RTL/EDA/Slurm/GPU/PPL，中央台账84条不变。后续本工艺表征仍是独立工作，不冒称已测。实际追加提交/回读见work/rayggxia/204/bf16_baseline/LITERATURE_PUBLICATION.json；PR209待审不合并，Projects沿既有限制。

# BF16基线研究交接

2026-10-28，rayggxia，接续Issue204 / 已合并PR205；分支task/204-bf16-baseline，目标main@787489192ebfcdb61ad72edde406818f450aa3dc，原调研起点5bfb221544daca8c345773a4741c30d2712f75ba。复用工作目录C:/Users/86134/Documents/a_P_BIT/tmp/matrix-t32-issue204-20261028。

用户授权调研BF16或搭模块估计。本轮已核查GitHub身份/最新PR205/Issue204、原负责人Issue107、main README/AGENTS；没有重复旧作业或接管Issue107。完成一手文献、旧BF16 RTL结构/两角summary核验、SC能耗预算与后续模块合同；正式成果architecture_tlm/bf16_baseline_20261028。

实际验证：estimate.py --workspace C:/Users/86134/Documents/a_P_BIT，核验两份原summary SHA，3seed能量/有效输入单位及旧负时序；SC54/50读取旧封存JSON，公式重现。没有新增BF16 RTL、功能/综合/STA/PT或模型推理，因此不新增电路run，不继承质量；原台账84个record保持。SS/TT旧时序失败和论文摘要合同未知均明确保留。

主要结果：主合同BF16×BF16→FP32累加；28nm论文1761.41GFLOPS/W条件2 FLOPs/MAC约72.67pJ/N64，对SC54算术69.46pJ，不能据此宣布巨大能耗优势。全文FLOP/精度/供数/面积/延迟未核验，能量不按节点缩放。5倍能耗比要求数字>5.43pJ/MAC；10倍>10.85；SC前后端还在外。旧BF16 SS setup−26.219ns/TT−10.538ns，不拿其大面积/能量充当成熟数字基线。

本轮无新增服务器作业。后续可在用户授权范围内补专用BF16乘法、FP32树LZC加法、融合MAC、DOT2/4/8及N64帧封装；先冻结源码/浮点合同和oracle，再跑三seed功能、合法STA与PT，加入新run。100MHz反馈流水需真实上下文/多周期协议。模型精度验收与量化数字控制另计。

MEMORY_PREIMAGES.json归档修改前记忆原字节；共享记忆只加同一段，不用旧副本覆盖新历史。发布时发现PR205于10:51:05Z合并（1a7ef75f），因此改用接续分支；仅对自己未发布提交rebase到最新main，两个共享文档冲突用完整main原字节+本人新增前/后缀解决。原PR205分支及其他任务不改。PUBLICATION.json为新补充PR真实上传回执入口，不自动合并/关闭Issue，Projects既有限制。

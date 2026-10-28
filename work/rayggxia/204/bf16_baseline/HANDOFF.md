# BF16基线研究交接

2026-10-28，rayggxia，接续Issue204 / 已合并PR205；分支task/204-bf16-baseline，目标main@787489192ebfcdb61ad72edde406818f450aa3dc，原调研起点5bfb221544daca8c345773a4741c30d2712f75ba。复用工作目录C:/Users/86134/Documents/a_P_BIT/tmp/matrix-t32-issue204-20261028。

用户授权调研BF16或搭模块估计。本轮已核查GitHub身份/最新PR205/Issue204、原负责人Issue107、main README/AGENTS；没有重复旧作业或接管Issue107。完成一手文献、旧BF16 RTL结构/两角summary核验、SC能耗预算与后续模块合同；正式成果architecture_tlm/bf16_baseline_20261028。

实际验证：estimate.py --workspace C:/Users/86134/Documents/a_P_BIT，核验两份原summary SHA，3seed能量/有效输入单位及旧负时序；SC54/50读取旧封存JSON，公式重现。没有新增BF16 RTL、功能/综合/STA/PT或模型推理，因此不新增电路run，不继承质量；原台账84个record保持。SS/TT旧时序失败和论文摘要合同未知均明确保留。

主要结果：主合同BF16×BF16→FP32累加；28nm论文1761.41GFLOPS/W条件2 FLOPs/MAC约72.67pJ/N64，对SC54算术69.46pJ，不能据此宣布巨大能耗优势。全文FLOP/精度/供数/面积/延迟未核验，能量不按节点缩放。5倍能耗比要求数字>5.43pJ/MAC；10倍>10.85；SC前后端还在外。旧BF16 SS setup−26.219ns/TT−10.538ns，不拿其大面积/能量充当成熟数字基线。

本轮无新增服务器作业。后续可在用户授权范围内补专用BF16乘法、FP32树LZC加法、融合MAC、DOT2/4/8及N64帧封装；先冻结源码/浮点合同和oracle，再跑三seed功能、合法STA与PT，加入新run。100MHz反馈流水需真实上下文/多周期协议。模型精度验收与量化数字控制另计。

MEMORY_PREIMAGES.json归档修改前记忆原字节；共享记忆只加同一段，不用旧副本覆盖新历史。发布时发现PR205于10:51:05Z合并（1a7ef75f），因此改用接续分支；仅对自己未发布提交rebase到最新main，两个共享文档冲突用完整main原字节+本人新增前/后缀解决。原PR205分支及其他任务不改。PUBLICATION.json为新补充PR真实上传回执入口，不自动合并/关闭Issue，Projects既有限制。

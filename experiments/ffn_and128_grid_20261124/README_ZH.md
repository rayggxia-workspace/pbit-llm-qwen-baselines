# 固定FFN 64/128预算：后级联合格32→128

Issue263，负责人rayggxia，2026-11-24；关联Issue254/PR255的已执行联合预算方案。本实验不训练、不改量化、权重、输入分层或Attention，只改变后级联合格的组织。

| 配置 | 前级 | 后级格数 | 每格次数 | 后级总次数 |
|---|---|---|---|---|
| coarse32 | 64区间各1次、共享64输入 | 4g×2sigmoid×4u=32 | 4 | 128 |
| fine128 | 相同 | 8g×2sigmoid×8u=128 | 1 | 128 |

8×2×8嵌套细分了原g/u两个轴，保持sigmoid轴2段。对固定概率输入，均值相同、条件计数方差不增加；最终PPL和任务质量须实测。

模型为Qwen3-4B后训练T64导出，叠加联合适配main的144个QKVO投影。准确版本、导出和overlay SHA见PLAN.json。现有本人服务器保存同一overlay原件，可重新建立同环境coarse32对照，不继承另一环境旧9.451为新对照。

保留原S12/F4→整数max-gap→U8/F4→floor-P8、SparQ r32/K128/recent32、赢家S64。FFN在全部提示和计分位置采样；Attention前缀准确，首个答案token起的每个计分位置均走采样。前后分母分别64与128。原R8/P8有限概率码、符号/尺度恢复、W8/PoT和事件直连Wd保持。

## 验证与运行

`checks.py`本地可运行analytic_checks，无torch依赖；4096组边界三元组检查同均值及嵌套方差。GPU门禁比较原采样器的计数矩与逐格三比较器AND的矩，检查端点、总次数、原前级、native缓存无操作等价、旧coarse路径重复logits一致、36层实际T、权重不变和官方任务覆盖。软件沿用原七类边界区域的精确条件二项计数压缩，不是物理/GF64比特流回放。

运行时依赖必须用确切SHA核对：旧联合参考身份f1612d5cb4e450d80b8497fcef7e61ba8b6e50d2cc2bc772b39cc187da72770f，及其59文件清单；原seven runtime、模型和WT2由冻结prepare/load_model核验；官方任务加载器引用原source-5df53bac765c的manifest807238c8e2d1e995aba9f75eb949899aa63b5178189d9f774ae788560a507d1f。原件从既有授权存储读取，不修改或复制大权重。

runner.py需要显式提供reference-source、runtime、task-source、data-root、output；输出目录必须全新，GPU运行必须有SLURM_JOB_ID。运维命令与私人绝对路径只在work交接/原服务器保存，公开代码通过参数接入。

门禁先重跑未改动BF16及同权重配对pilot；通过后提交完整WT2：coarse/fine各部署seed101/202/303，另同环境原BF16一次。每组按37个八窗口块分4个独立作业，逐目标不重叠，共292窗/299077目标。随机域固定到块，不由Slurm作业号决定。

任务精选PIQA1838、ARC-C1172、WinoGrande1267，官方lm-eval0.4.8 0-shot，首轮部署seed101，两配置各测一遍；每任务4分片，保留原全局doc_id，汇总时按完整逐题记录计分。任务单seed与PPL三seed分开报告。全量任务结果不得用小pilot或部分分片冒充。

当前阶段见work/rayggxia/263/PUBLIC_STATUS_ZH.md和Issue263。没有新RTL/TLM/PPA，不改主线默认、不自动合并。

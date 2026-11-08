## 2026-11-08 22:38：7/36完整结果，跨模型SC100地址绑定修复已恢复

首检三worker进入Llama100 SC时被旧Qwen5KiB残差边界拒绝；并非前端PPA近似问题。真实闭包decoder绑定已修正，不增加SRAM/端口/价格，Qwen4928旧映射字不变，三模型本地内存包装预检通过。独立冻结修复161da0452c99/e0dab7ae；Llama/DeepSeek100冷单层38634043两门禁通过并核SEAL。当前7完整case逐SHA核验、原5健康worker保留，3恢复worker38634114运行，38634115/16/17待原对应worker结束；新汇总38634118。仅取消无效且仍pending的旧聚合38631676，旧源/失败输出/成功结果不改。

正式DECODER_REPAIR_ZH.md与delivery/DECODER_REPAIR_RECEIPT、REPAIR_STATUS。只读恢复用repair_status.py，不再prepare/repair_submit。6个指定SC100使用修复manifest，其他30个保留原源，聚合严格36唯一case；未收齐、未合并，Projects待同步。发布SHA见DECODER_REPAIR_PUBLICATION。前端成本可以先沿旧非零宏预算，不触发健康重跑；A数值证据不能冒充B质量。

---

## 2026-11-08 当前交付已发布，完整任务继续运行

源e6e534d6eb5ecf0d733d38c40383aae99bb00900已发布PR247，33文件逐内容回读一致；Issue245与PR说明已同步。8/8校验通过；full38631668八worker在18:15北京时间仍健康运行，汇总38631676等待afterok，完整结果未收齐，PR未合并。PUBLICATION_CURRENT.json记录源和回读SHA。

CLI git fetch本次无法连接github.com:443；发布使用身份已核验的GitHub连接器完成。当前本地HEAD仍d2b22f7，index/工作文件保留已发布内容，不能把HEAD旧点当未发布，也不要reset覆盖。恢复优先核对远端PR247，再在网络恢复后取回提交与索引做字节核验后同步HEAD。无权限的Projects待维护者同步。

## 当前作业ID补充（2026-11-08）

8/8门禁退出码0:0，full worker38631668_[0-7%8]均已RUNNING；aggregate38631676 afterok等待。最新STATUS及8项单层封存摘要见mainline_20261108/delivery；完整结果尚未收齐。禁止重交或改快照。

## 2026-11-08 当前主线完整评估恢复

本节优先于下方旧阶段。Issue245/PR247，rayggxia，task/245-cross-model-estimate；未合并。完整说明architecture_tlm/model_scaling_20261106/CURRENT_MAINLINE_ZH.md。正式新源码current_mainline.py/current_run.py/current_pricing.py/prepare_current.py/aggregate_current.py；执行源SHA在delivery/SOURCE_INDEX与CHECKS。

本地：C:/Users/86134/Documents/a_P_BIT/tmp/cross-model245-20261106。网络操作用Codex附带Python，系统3.8 SSH依赖不兼容。只执行读状态，不再次prepare/dispatch/finalize_submit：

`python -X utf8 -B work/rayggxia/245/mainline_20261108/launcher_r2.py status`

主root `/public3/home/t6s011227/pbit_chimera_pipeline_20260920/tlm245_current_3a7dd5e0679e`，manifest982f9303785c364ed7c7ac5384927f0a12f98388433708306878e5f14fbae925，zip3a7dd5e0679ed56cdb60e37ef54c3c787d62e4470a7436e414f6348a63ab0bbf。详细8门禁/36full计划、源码SHA与执行环境来自冻结manifest；私有源/fixture仅本地和EDA保留，Git只小索引和本任务胶合，不发布整个快照。

pilot38631497；coordinator38631505及`_dispatch_v3/FULL_SUBMISSION.json`；8worker%8每人4/5case，1逻辑线程12GiB48h，实际CPU看sacct。聚合协调38631640，root`_aggregate_2fe4732df6`，`AGGREGATE_JOB.json`记录依赖full worker的最终汇总ID。full目录sealed JSON+VALIDATION+退出码齐全才计完成。聚合仅接受36个唯一全层含head原生case。绝不能重复提交已健康/完成的case。

revision1 root`tlm245_current_0af9dd179a3c`/pilot38631345保留：100MHz锚点严格相等门禁失败12拍，且后续查出逻辑KV输入偏移/显式输入读取待修。其SEAL不等于driver门禁通过；不用作最终版。旧pending协调38631395已在确认pending/名称后取消，RETIRED_DISPATCH有回执；未启动full。revision2独立修正源并记录锚点0.1%容差，工作量仍严格。原始36数组因AssocMaxSubmitJobLimit未创建，不能当full_job。恢复先看SUBMISSION+DISPATCH+FINALIZER+STATUS，再读各root回执，不重执行prepare。

校验：5项前驱本地冷层；5源AST和36缺项拒绝汇总通过；当前门禁成功数看delivery/STATUS_CURRENT。Qwen解析锚点100MHz实际1.206270 vs本地1.206150（12拍，不归因未验证原因）、2501.085720一致。模型PPL不在范围。100SS/250TT角点不同；SS100控制/格式宏及250标量代理未全片测量；28nm保持候选。

交付/待做：本轮代码、状态、交接已本地整理；上传SHA以PUBLICATION_CURRENT.json为准，未写该回执前不能称远端已完成。收齐full后下载封存小JSON/summary，逐SHA核对，发布同一PR247/Issue245、更新STATUS/HANDOFF及长期备忘录；不合并。Projects待维护者同步。未改owner和默认100/250，不重跑225健康Qwen任务。

---

# Issue245：固定硬件跨模型初步预算

2026-11-06；负责人 rayggxia。Issue245；分支 task/245-cross-model-estimate；base main@8cd4fba009598184bce4f1c806f038299b011ea0。独立最小工作目录 C:/Users/86134/Documents/a_P_BIT/tmp/cross-model245-20261106。实际提交、PR和远端读取回执以 PUBLICATION.json 及 Issue 为准，尚无该文件时只表示本地完成。

## 已完成与范围

正式实现 architecture_tlm/model_scaling_20261106/：estimate.py、六项CPU合同检查、CALIBRATION/ESTIMATE/SUMMARY.json、模型身份 evidence/ 及 REPORT_ZH.md。按当前固定100MHz/2.5MiB/12核C20 T64/共享1024 FMA、8物理KV组、LPDDR-derived8533、B1/2K、SparQ r32/K128、赢家保持S64估算；含embedding及完整lm_head。面积已单次乘0.81，功率/能量/时间不随此系数缩放。

中央Llama-3.2-3B-Instruct约39.92ms/159.50mJ/3.995W；DeepSeek-LLM-7B-Chat约83.45ms/333.76mJ/3.999W；固定覆盖面积均67.541446mm²。外存4pJ/bit；另外提供6.6/8pJ及65/90%峰值效率敏感性。中央继承Qwen有效带宽，不能当作新模型已跑原生TLM。模型质量尚未验证，不能宣称相对数字整机节能比例。

Llama匿名HF原始config不可读，使用官方公开Meta SKU及精确总参数数核验架构；明确保存派生配置。准确模型revision、公开来源、配置SHA在 evidence/MODEL_IDENTITIES.json；DeepSeek/Qwen原始配置已固定revision。没有权重/tokenizer文件和训练/评测数据SHA，因为本次没有下载或执行它们；后续PPL必须补齐授权权重及匹配参考。

## 验证与证据

命令：`python -B architecture_tlm/model_scaling_20261106/estimate.py`；`python -B -m unittest architecture_tlm.model_scaling_20261106.test_estimate -v`。六项全部通过；原Qwen三seed封存的16个能量分项、字节、时间和面积重建一致，这是对账检查，不是新预测精度验证。SOURCE_MANIFEST.json列12份正式文件原字节SHA-256及长度，CALIBRATION.json绑定已有封存和价格来源。根 architecture_tlm/model_scaling_20261106/ 为逐字阅读镜像。

无新RTL/PT/PPA、GPU/PPL、训练或原生Slurm任务；不改变Issue236健康任务、既有代码/默认值，不登记虚构电路run。未复制原始模型/大事务/网表/库。部分价格仍有C20 PT窗口/idle代理等历史边界，报告已保留；67.5mm²不是完整die，4W不是实测整板。

## 完整TLM下一步（本轮未执行）

1. 参数化现有构造器和owner adapter的Qwen硬编码。Llama为24Q/8KV，3Q每KV；DeepSeek为32Q/32KV，1Q每KV，复用8物理KV组分4波，不复制32组硬件。
2. DeepSeek尺度元数据需33024B/层而旧固定32768B；重排旧g/u offset=20000，避免与权重尺度重叠。FFN所有tile边界核验，不静默截断。
3. DeepSeek全norm驻留会造成192个bank超深度。初估提出32KiB逐层双缓冲并已收费约0.50MB额外读取；原生模型要落实预取、仲裁和生命周期。Llama原分区容量通过。容量通过不等于端口时序通过。
4. 单层先检查容量、动作/字节和有限物理头复用，再做完整28/30层EDA CPU任务。不要在未改硬编码前直接变model名提交。
5. 新模型捕获真实候选/赢家保持/唯一V轨迹和x/g/u/S12-gap-P8分布，建立匹配PPL参考；现有均匀V占用、Qwen调度效率和局部重装比例均只是显式代理。

## 发布与待同步

通过独立任务分支和PR交付；PR待审不等于已合并，Issue保持open。Projects连接器无更新接口，待有权限维护者同步；不因此省略Issue/PR/STATUS。保持原始估算及负面检查，不覆盖其他成员的STATUS或Issue28并发备忘录内容。

实际发布：PR247 ready/open待审、未合并；主体1335f69da2a3d014773adecb685ba6bdcfd37400，20文件远端逐内容一致。6项CPU通过；长期备忘录根/Issue28阅读镜像已更新同字节，未混入发布其他任务的备忘录改动。精确回执见PUBLICATION.json。

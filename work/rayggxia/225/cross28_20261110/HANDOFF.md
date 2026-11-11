## 2026-11-11 28nm、250MHz TLM 15/15 已核验

Issue225 / PR249。北京时间 2026-11-11 11:03:50 复核，Qwen 数字 3/3、Llama 6/6、DeepSeek 6/6，全部 Slurm COMPLETED/0:0，封存与账本校验通过。DeepSeek 概率 seed17（38650676）02:05:57 完成，BF16 稠密（38650679）03:10:26 完成。概率三 seed 均值 98.984535 ms/token、片上 26.526532 mJ/token、外存 4pJ/bit 情景共 317.782038 mJ/token；BF16 含 head 207.008152 ms/token。正式结果见 architecture_tlm/process_28nm/results_20261111/REPORT_ZH.md、SUMMARY.json。Slurm 与封存回执 work/rayggxia/225/tlm_status_20261111/RECHECK_REMOTE_20261111.json，SHA-256 5fbfe6c65ec000ade42b00475f466f89d769ba330aa27d153b8dd8292e7fde2f。PR 待审，Projects 待同步。

---

## 2026-11-11 TLM进度：新增15项已封存核验13项，余DeepSeek两项

Issue225/PR249，00:42北京实核。Qwen数字3/3、Llama6/6、DeepSeek4/6；13项均COMPLETED0:0、EXIT0、SEAL原件/源/配置SHA、真实全层/head及能量行加和通过，无失败。Qwen概率3seed为此前参考，不重复计15。QwenBF16/W8dense/W8screen含head111.119648/94.998940/85.450204ms；Qwen概率51.132604ms。Llama三seed概率43.929332ms，BF16/W8dense/W8screen86.102848/74.136052/66.688448ms。面积/片上与外存能量、扣head见process_28nm/results_20261111/REPORT_ZH.md、SUMMARY.json。

DeepSeek38650676概率seed17完成30层，正跑lm_head，余约1h；另两seed已完成但不当最终三seed平均。38650679 BF16已25/30层、正在第26层，预计余2–3h，整批约凌晨3点、保留到4点浮动。没有重启/重交/改冻结源，CPU并行上限保持取消。新报告本地完成，发布看本work/PUBLICATION；PR待审未合并，Projects待同步。

---

## 2026-11-10 CPU仿真耗时诊断（本地记录，待后续PR同步）

Issue225。14:49北京只读sstat：Qwen数字38650229分配3核，墙钟55:37、AveCPU55:33；Llama概率38650670分配6核，墙钟33:52、AveCPU33:51，均约一个活跃CPU。脚本请求1CPU，实际3/6来自12/24GiB内存粒度；当前主事件驱动及nativeDRAM调度没有单case多核并行，增加cpus-per-task不会自动加速。

已完成Qwen seed17完整事务51.136596ms对应CPU墙钟19424.881s；SRAM16B读194019908＋写360003008，共554022916字活动；native32请求169105152（64B逻辑84552576，不重复相加）。单核细粒度SRAM/事件与nativeDRAM循环共同造成大量软件工作；未做逐函数profile，不把某个具体模块CPU占比说成已测。当前不同模型/seed已并行；后续优化应考虑批量访存/原生热点，保持bank冲突、回压、统计和时序回归，不能直接拆层相加替代完整共享状态执行。

DeepSeek BF16 gate的EXIT0/SEAL/SHA已只读确认，Slurm收尾后完整38650679已于14:48:38启动，14:49状态RUNNING，不需解除依赖或重复提交。原冻结源码/硬件时序/作业均未改。原始观测本work/CPU_USAGE_OBSERVATION.json与CPU_USAGE_FOLLOWUP.json，代码cpu_usage.py；本轮诊断辅助文件尚未发布，不把本地记录称远端已更新。

---

## 2026-11-10 用户要求仿真不设人为并行上限；按实际吞吐更新ETA

Issue225/PR249。用户明确本项目CPU TLM后续不人为设置%2等并行上限。已将Qwen数字38650228的ArrayTaskThrottle=0，新两模型12完整任务原本独立无人工上限；保留原生验证afterok依赖，不重启/改源。EDA资源/QOS为实际调度约束，不声称不存在。

北京时间14:37观测：Qwen数字完成5/12/14层（目标36），Llama多为4–5/28，DeepSeek多为1/30；按近期实际层吞吐＋单列完整head预算，Qwen尚5–7h、Llama4–6h、DeepSeek10–13h。整批约11月11日0–4点，最慢DeepSeekBF16，属于粗ETA，非完成回执；负载/后续吞吐/失败会改变。恢复本任务cross28_20261110/ETA_ZH.md、ETA_SUMMARY.json和原始ETA_OBSERVATION。此次无新仿真/重交/取消任务。

---

## 2026-11-10 两模型发布与实际调度回执

PR249源06cb57275c6aca6311f27c3c5082b4ab22d149e6，27文件远端完整回读一致，Issue225评论6760602169、Issue245评论6760604170。8解析单层检查全通过；北京时间14:20核查Llama四原生门禁COMPLETED0:0、六完整任务38650670—38650675全部RUNNING，DeepSeek四门禁运行、38650676—38650681等待对应依赖，无已发现失败。Qwen38650228已调自设%2→3且三项均RUNNING，未重启/改源。实际sacct门禁12GiB分配3CPU，完整24GiB分配6CPU（脚本均请求1CPU、单线程），覆盖早先按旧12GiB粒度写的“实际3CPU”预测。完整跨模型结果尚待收，不能把局部门禁当全模型。PR待审未合并，Projects待同步；恢复cross28_20261110/HANDOFF和ops.py status。

---

# 两模型28nm250 TLM：提交与恢复

2026-11-10，rayggxia；Issue225 / PR249接续28nm，交叉引用245/PR247的55nm模型形状与Fixture，不改其任务。当前工作目录tmp/tlm-unified250-issue225-20261107、分支task/225-tlm-unified250-20261107；没有复制新全量checkout。

用户问Qwen BF16为何等待：原提交--array=0-2%2自设限制，不是EDA仅允许两项。本目录cluster.py已核所属job/name/user后只改38650228的ArrayTaskThrottle=3，THROTTLE_UPDATE.json保留前后命令及回执；随后REMOTE_PREFLIGHT已确认Qwen三项均RUNNING。没有重启/重交/改冻结源码；不推断集群不存在其他QOS或资源约束。

## 已提交

北京时间2026-11-10 14:09:49，原生门禁数组38650669（下标0—7）和12个依赖门禁的完整CPU任务均已提交，准确列表SUBMISSION.json。每项独立CWD防止native统计覆盖；源包不可变，不原地修复。

|模型|概率SC三seed17/503/1009|BF16_dense|W8_dense|W8_screen|
|---|---|---|---|---|
|Llama-3.2-3B-Instruct|38650670 / 38650671 / 38650672|38650673|38650674|38650675|
|DeepSeek-LLM-7B-Chat|38650676 / 38650677 / 38650678|38650679|38650680|38650681|

门禁0—3对应Llama SC/BF16/W8dense/W8screen，4—7对应DeepSeek同顺序。每个完整case依赖对应afterok:38650669_<index>；不设置%2或其他人工完整并行上限，真实资源限制仍由Slurm决定。

门禁请求1CPU12GiB，完整1CPU24GiB；集群按粒度门禁实际分配3CPU、完整24GiB实际6CPU，上限4h/24h不是预计运行时长。无GPU、PPL、训练、额外RTL/PT。

远端根/public3/home/t6s011227/pbit_chimera_pipeline_20260920/tlm28cross250_225_e0291ed6b5a9。包80354B，SHA227f2509a117c4673807074f23b303473dc8aea4065cc9fae905ea0db7ca83b1，manifest874c258f0b87631b386a8567977f43920cf598e77e3336fd96a08191d58dec72。旧runtime/dependencies/snapshot三manifest逐SHA核对，准确路径UPLOAD_PLAN和FROZEN_MANIFEST。

## 验证与边界

本地8构造均通过，包含完整词表/tail工作量。解析一层＋384head局部结果以LOCAL_GATES.json和VALIDATION.json为准，正在运行的局部检查不能写成通过。原生门禁/完整最新状态见STATUS，最初8门禁RUNNING、12完整依赖等待，并非完整评估完成。

正式代码architecture_tlm/process_28nm/cross_models_20261110/，MODELS绑定原configSHA/revision。真实形状、3/1Q每KV、DeepSeek4波KV、元数据>32KiB地址重排和独立embedding均已适配；同832KiB/178宏，不增加额外硬件。固定4Q issue中的无效头按完整FMA16片门控动作代理，仍计物理issue时间、固定状态/面积和idle；物理/有效量分开。结果是代表事务TLM，不是新文本质量或完整芯片PPA。

## 下一步

1. 通过已有EDA helper运行本目录ops.py status；不要再prepare/submit，不重交健康任务。
2. 各门禁通过后完整自动放行；失败则保留EXIT、log和冻结源，修复另冻新包且只补失败case。
3. 完整结果按status=completed/full、真实28/30层、全部词表、SEAL/源/配置SHA/逻辑KV数/物理与有效MAC/权重字节核对；分别列含/扣head的时间、能量、面积。
4. 与Qwen28nm结果及同芯片三数字基线比较；不把55nm旧表混入新结果。PR未合并、Projects待维护者同步；发布状态以PUBLICATION/RECEIPT_PUBLICATION为准。

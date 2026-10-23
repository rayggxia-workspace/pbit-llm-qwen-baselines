## 23:29 更新：批形状候选未通过，正式任务回退逐题

CPU2875 COMPLETED，51项（含真实TF/BF16）和10项benchmark辅助测试全通过。GPU2876在新PPL batch32显存/稀疏门禁通过后，在跨题batch候选的真实BF16分数门禁失败：最大每目标mean logprob差0.043265106636681594，超过预声明0.02。未开始完整质量/benchmark，未放宽阈值。逐题native/dense原门禁和core oracle没有失败。

原作业FAILED/1:0，1m31s；所有报告、终态、失败日志保留在batch_gate_failure/。最初抛错前未完整保存逐候选差异，不据此武断归因为cache错误。新runner把跨题候选保留为显式诊断并先保存完整差异；**正式MC回退逐题原顺序、choice_batch4**。两模式相同。任务分片256仅影响持久化，不代表跨题同时运行。PPL仍可用已通过显存检查的batch32/chunk32。

下一步只提交新冻结串行文档正式源。此前GPU均已终止；新job必须另记ID、不能重放2876或覆盖原快照。仍无完整PPL/准确率/物理PPA结论。

# Issue157 执行交接

唯一目标 rayggxia-workspace/pbit-llm-qwen-baselines；认证 amlink1219。分支task/157-sparq-qwen3，依赖PR147@357db588。Issue157开放；当前准备发布，不等于PR合并或完整实验结束。

## 2026-10-23 23:20 更新：已上传、真实门禁通过

PR163 draft/open/未合并，已核验上传4f381292b011；详见gpu_preflight/PUBLICATION.json。CPU2871 COMPLETED/0:0，10个模型文件+5份语料已验证。GPU2873因srun重设CUDA可见性被CPU门禁立即拒绝，无模型执行；改为`srun env CUDA_VISIBLE_DEVICES="" python ...`，未改冻结模型代码。GPU2874 COMPLETED/0:0、1分33秒；最终CPU46/46+benchmark9/9，真实模型native/dense逐bit一致、检查开关逐bit一致、真正稀疏解码和全部36层计分通过。报告SHA与原件均在gpu_preflight/。

小样本context2048、batch8、128目标的dense/SparQ计分耗时1.358/2.102秒，峰显存约11.82GB；仅门禁不是正式速度实验，PPL也不作完整质量结论。旧GPU作业已完成，无在途。

为完成全量计划，新增exact-context-length多题批处理（每批最多8题/32选项，任务分片256题），PPL计划batch32/chunk32。最终执行前需运行51项CPU门禁、10项benchmark辅助测试，再过真实BF16批形状.02 nats/target门禁、native/wrapped逐bit门禁和batch32峰显存28GiB门槛；任何失败不进入全量。两模式用相同批规则，改变源/协议不复用旧smoke目录。

完整模型任务仍未完成；下一步冻结新执行快照，CPU-only验证后依赖调度单GPU全量作业，并写新job回执。量产式稀疏kernel/ASIC RTL/STA仍未完成。

## 已做与验证

- 原论文/官方代码审计、GQA核心及官方源码oracle、原生Qwen3适配、完整计分规划、官方task loader、分段恢复、硬件事务模型已实现。
- 服务器CPU-only2872（源码cdb1a73）45/45门禁通过，含真实TF4.51.3 tiny非方Q投影和native/wrapped一致性；未初始化CUDA。后续诊断向量与benchmark单测单独重验。
- 硬件20配置+4条件资源示例、15测试；面积/功率/能量/真实延迟null。没有SparQ完整RTL顶层、网表或STA报告。
- 模型固定Qwen/Qwen3-4B@1cfa9a7208912126459214e8b04321603b3df60c，36层/32Q8KV/d128/h2560/FFN9728；所有模型和数据SHA由stage.py验证。

## 在途与未完成

主机 Weican_Chen@10.129.164.156:21570，个人目录 `/home/Weican_Chen/projects/sparq-qwen3-issue157`。新环境env-v2只读复用本人两个旧site-packages，不修改旧环境。CPU作业2871从staging-v3准备模型与本人的已验证任务数据；恢复时先查scontrol与prepared/READY.json。2867/2868为已失败历史，不重复执行。没有本任务GPU作业（本文件首次发布时）；后续提交必须更新job回执。

待做：冻结最终source bundle，GPU真实BF16逐bit门禁与真正稀疏调用/内存烟测；匹配完整WT2和三任务；GPU参考速度/板级功率；结果汇总、SHA和PR更新。TF4.51.3官方任务loader必须通过smoke，不以CPU算法测试代替真实模型质量。全量评测允许分段恢复，先核对快照/配置/模型SHA与结果中的experiment指纹。

运行只能通过Slurm，最多一张GPU，提交前检查三台服务器的本人在途GPU作业。原116/123暂停；他人home、工艺库、系统环境不访问不修改。大权重数据不提交Git。实际ASIC STA/PPA仍需后续实现/库表征，不能用已有FFN物理值代替SparQ。

## 原始证据与本地恢复

本目录cpu_gate/与staging_failures/保存实际终态和日志；outputs/sparq23本地保留提交意图、服务器job ID、下载准备与发布控制脚本。每个快照不可变，不覆盖运行源。后续GPU提交后将把运行命令/manifest/job写入本目录。

SparQ论文已有原PDF和去重待办；Zotero后台API未启动，尚未入库。恢复既有qwen3-gqa-20261023待办，不重复新增，不自动弹出Zotero。阅读审计不是导入回执。

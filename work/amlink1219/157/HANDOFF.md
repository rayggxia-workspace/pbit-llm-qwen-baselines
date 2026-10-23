# Issue157 执行交接

唯一目标 rayggxia-workspace/pbit-llm-qwen-baselines；认证 amlink1219。分支task/157-sparq-qwen3，依赖PR147@357db588。Issue157开放；当前准备发布，不等于PR合并或完整实验结束。

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

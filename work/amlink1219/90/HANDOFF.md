# Issue90：两台 RTX 4090 的隔离 LLM 环境交接

2026-10-22；负责人 `amlink1219`；正式仓库 `rayggxia-workspace/pbit-llm-qwen-baselines`；[Issue90](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/90)。分支 `task/90-4090-llm-environments`，PR base `pbit-tlm-attention-details-20261016`，初始读取提交 `8d4ce51be7ecace716bc83688dc4768eb2574d38`。本任务使用独立最小稀疏目录 `workspace_projects/env90`。真实上传/PR/最终提交以PUBLICATION.json为准，服务器完成与PR待审分别记录，不自动合并或关闭Issue。

## 已完成

两台个人环境Python3.12.3/Torch2.6.0+cu118/Transformers4.45.2/lm_eval0.4.8已安装。备用一9041 CPU/离线闭包/pip/compat、9042 GPU；备用二14101 CPU/compat、14104 GPU；均COMPLETED/0:0，分别19项CPU、6项GPU。94包freeze完全同字节，SHA636ea0599fc983e7c003c3a8881aefa2f05d8167f2877dcab8992dfc3f145ae5；wrapper及预载libgomp SHA两台相同。严格27参数/3buffer逐位一致、logits误差0.0。任务作业均已结束，无需重交。

完整公开入口maintenance/llm_env_4090_20261022/README_ZH.md及pip_freeze.txt；实际执行源/阶段manifest在scripts/llm_env_4090_20261022。SOURCE/COMPAT/GPU_V2/EXPORT/EXPORT_V2/RECOVERY/RECOVERY_V2阶段记录区分原输入和后续修正。固定W8源闭包含来源提交9b43ba0和LICENSE，未替换正式项目源。

13份私有原始小报告/版本/日志manifest经过收集后大小+SHA核验；公开只含exact freeze、脱敏派生报告与原件SHA，RESULT_MANIFEST.json明确映射和变换，不含连接信息或原始pip长报告本体。原失败9038/14099、取消9039、staticTLS14100、GPU14102、导出14103、launcher9040均保留证据，EXECUTION_HISTORY.json及FAILURE_AND_RECOVERY_ZH.md说明后续成功没有改判旧失败。

源端导出14105为70wheel/164065280bytes，archiveSHA1c999138495f92b9e7c5fd2e69a79a6cfcb09b0103f6e025a8f7c110aa27b9aa。仅LLM扩展层，不是完整Torch离线安装包；receiver9041已做固定Torch元数据前后相同与dry-run闭包证明。原offline Python4959eaf...不变，v2 launcher显式用个人Python3.12。根AGENTS仅增保存重载参数及非持久buffer一致性规则，证据14102/14104；全局规则和memory未改。

## 使用与限制

正式个人入口为/home/pwmat/envs/llm-qwen-py312-cu118/bin/llm-python；该进程预载环境内sklearn wheel的唯一libgomp、线程取Slurm分配。登录、canonical个人目录和队列门禁仍须每次核验。CPU显式隐藏GPU，单卡GPU需Slurm分配，本项目跨服务器至多一个GPU作业；选择备用服务器当次对话告知。系统/共享Conda/驱动保持只读，地址/密钥/本机路径只留本机连接上下文。

没有真实权重/语料下载、训练、完整PPL、准确率或PPA；2层tiny Qwen和小型FFN只验证环境连通。Torch2.6cu118与5090的2.7.1cu128不同，后续真实实验须重建匹配数字基线；未验证7B显存容量和完整Attention采样路径。

## 恢复与发布

先读Issue90、当前远端规则/双方STATUS和本PUBLICATION，再按需要使用已完成环境，不能根据旧失败记录重复安装。发布前核验GCM实际身份amlink1219/id75301230、repo1420564659权限、所有解析push URL、最新base及明确文件清单；稳定输入/结果须核Git blob SHA。STATUS只更新本人，其他成员成果与任务不接管。

本次交付验证见VALIDATION.json和validate_delivery.py；发布回执PUBLICATION.json区分结果提交/元数据提交与PR状态。Projects按实际GraphQL能力同步，权限不足明确待同步；Issue保持open至审阅验收。后续模型质量研究另开或接续对应Issue，环境完成不表示相关研究已完成。

已推送结果提交`2b0fb4c6a85759bc4ee4adbbd9d0540847a0041f`，PR#93（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/93）开放待审、未合并；远端ref、PR head、60项文件范围和55个稳定blob SHA已核验。Projects：pending_permission。

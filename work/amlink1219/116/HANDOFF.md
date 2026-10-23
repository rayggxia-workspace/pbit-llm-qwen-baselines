# Issue116 交接

## 当前权威状态：paused

用户在2026-10-22 19:42 UTC提前暂停本轮目标；已通过目标工具设置`paused`，**不是complete，不自动恢复**。此后只完成状态核验、既有制品归档、GitHub上传和交接。完整A–G状态、验证证据、已知问题、工作树/进程/作业清单见[暂停总结](PAUSE_REPORT_ZH.md)。

正式工作入口仍为下述cycle23，分支`task/116-cycle-execution`、[PR126](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/126)开放待审/未合并。暂停前已推送`3347bd8a0a46ad2533298d680d8a6800ad9fa8d4`；收尾提交、远端对象与原始blob核验以`PUBLICATION.json`为准。当前主树没有未提交生产改动；原未跟踪诊断仍保留，现有公开结果已另封存上传。各工作树精确清单见`PAUSE_WORKTREE_INVENTORY.json`，不能reset/clean。

本次2K仅建图后按用户指令中止：worker290792、monitor251584、launcher274768均已停止；无2K完成/数值/轨迹结论、无2K成功台账记录。原运行器及暂停回执在`active_gqa_2k_paused/`，其档案副本不能直接执行。三名子代理均停止。服务器暂停快照队列为空；并行Issue123作业2783为CANCELLED/0:15，本任务未取消它，不自动重交。

### 仅在用户明确恢复后进行

1. 先核最新Issue116、PR126、PR125及成员STATUS。PR125最终head见PAUSE_GITHUB_STATE（09dc2f90，base本任务分支），候选兼容验证只绑定d944081a；其全形状作业已取消，先与该工作线核是否已有后续结果，不能重复提交。
2. 阅读本目录PAUSE_REPORT、PLAN_COVERAGE与cycle_v1的AGENTS/FULL_MODEL_TODO。优先确定完整FFN/真实单层接合边界，再考虑规模；没有完整层/质量和物理表征前不作架构排名。
3. 若继续采用ActiveMemory候选，固定公开版本和本地Kernel SHA，重核其私有接口与完整trace/状态等价；默认Kernel目前未替换。2K草稿只有只读审核和建图记录，需先重建可复现运行器、有限资源与足够时间预算，不能直接续接已终止进程。
4. 真正的在线DRAM/互连、统一格式schema、在线摘要筛选与资源因果报告按原方案覆盖表另行验收；实际STA/PPA继续依赖jieruiz的既有分工，缺失物理数字保持null。

恢复时的必要检查命令如下，**本轮暂停收尾没有执行这些新验证或作业**：

```powershell
Set-Location -LiteralPath 'E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/workspace_projects/cycle23'
git status --short
git remote get-url --all --push origin
git log -5 --oneline
# 用户明确恢复后才刷新远端；保留当前dirty/未跟踪证据。
git -c credential.username=amlink1219 fetch origin
# 只在需要复验源码变更时，指定全新的输出目录：
python -X utf8 -m architecture_tlm.cycle_v1.validate_release --output work/amlink1219/116/resumed-validation-NEW
python -X utf8 -m architecture_tlm.cycle_v1.audit.run_audit --output work/amlink1219/116/resumed-audit-NEW
```

远程入口为原5090 SSH通道，个人根`/home/Weican_Chen/projects/tlm-cycle-issue116-20261023`。恢复前重新核身份/个人路径/Slurm队列；CPU作业隐藏GPU，禁止登录节点计算。已有终态/成果先读取，**本交接没有提供自动sbatch或自动恢复命令**。

## 以下保留暂停前的技术基线和历史说明

下文的运行中描述属于其记录时点，当前终态以本页顶部和PAUSE_REPORT为准。

负责人 amlink1219；唯一目标 `rayggxia-workspace/pbit-llm-qwen-baselines`，任务分支 `task/116-cycle-execution`，base `pbit-tlm-attention-details-20261016@46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d`。本机专用目录 `E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/workspace_projects/cycle23`；不要切换、清理或重置其他任务工作树。

科学入口 `architecture_tlm/cycle_v1/IMPLEMENTATION_ZH.md`，运行说明同目录README，独立检查 `audit/REVIEW_ZH.md`。已完成有限周期原型、68真实片段+8synthetic用例、真实context64共享KV的7query GQA分组、缩小单层、native随机协议、协议RTL、ONNXim试验、v6桥、PR122兼容复验和条件敏感性；不把这些称为原A–G全完成。最终81实现/71独立/43旧回归通过。未做完整Qwen/Llama、真实全维整层、多token/2K/8K、在线DRAM命令后端、全局容量/随机网络及物理PPA闭合；具体门禁在 `FULL_MODEL_TODO_ZH.md`。

关键执行：2776 real68+smoke8 COMPLETED/0:0；2764 RTL9case252握手；2772 ONNXim2官方/4自定义场景；2759 GPU14秒fixture；2781 GPU9秒GQA capture；2782 CPU2/8GiB、2分57秒GQA验证COMPLETED/0:0。没有遗留本任务运行作业。2775首轮62pass/6死锁、2766/2774启动失败以及外部构建恢复均保留；最终通过不抹去失败记录。并行Issue123作业2780不属本任务，不取消、不代为宣布结果。

完整矩阵原始结果：`/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/matrix-v5-results.tar.gz`，SHA-256 `82319f0d95054149e7d3dbeba5248648d461fe91539107aaa85e83fd44429ee5`。本机 `outputs/tlm_cycle_20261023/matrix-v5-results.tar.gz`（相对DAC根，非相对此checkout）；compact正式成果及原始manifest在 `architecture_tlm/cycle_v1/results/matrix_20261023`。实际执行快照 `cycle-source-v5.tar.gz` SHA `f6c596f3d772dee19bea1d85badb25fe0088aefaaae70ab959555b68daf96cbf`，同任务服务器根。完整source manifest在 `server/matrix_source_v5.json`。

Qwen权重和语料在本人原项目 `/home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/`；不得复制到Git。私有冻结片段在本人任务根 `real_fixtures_v1`，本机ignored `work/amlink1219/116/private_fixtures`；MANIFEST列出model/config/text/token和逐fixture SHA。删除/覆盖仍需要用户明确授权，本轮没有清理任何历史数据。

后续恢复：先读取远端Issue116/本PR、最新集成入口、PR119/120/122/125及成员STATUS。PR122兼容性复验针对固定8007d98，不等于合并；新的来源提交要重新核接口。PR125最新d944081a22dc346a3a50d505633e5d15c857ba78（19:31 UTC核验）已公开完整FFN接合/活动内存调度，base改为task116；完整FFN fixture抓取（2777）、编码恢复45场景（2778）、28软件测试及120次独立随机复核为其回执。完整形状作业2783仍在运行；不要重复抓取或接管，未终态不得声称完成。实际STA/PPA按其交接由jieruiz执行，EDA尚未运行。中央台账目前新增独立record，多个并行PR集成时合并record_ids后重建总览，不能直接覆盖其他人的catalog。

最小命令（新输出路径；服务器上必须Slurm CPU allocation）：

```bash
python -m architecture_tlm.cycle_v1.run --operator ffn --output /personal/new-ffn
python -m architecture_tlm.cycle_v1.run_layer --output /personal/new-layer
python -m architecture_tlm.cycle_v1.v6_adapter --operator ffn --smoke --output /personal/new-bridge
python -m architecture_tlm.cycle_v1.audit.run_audit --output /personal/new-audit
```

基础版本ddd2e3406caac5075689f9388a041603e17d2b19已上传[PR126](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/126)，开放待审、未合并。该基础版本438个任务Git对象和8项原始blob远端核验通过；包含GQA的最终发布版本、远端对象数量与原始blob散列以同目录 `PUBLICATION.json` 为准。后续发布元数据提交不改写固定实验来源。Projects实测缺read:project，记录在PROJECTS_CHECK.json，待有权限者同步，不修改权限或自动关闭Issue。

GQA增量已验收并整合：`gqa.py`/`run_gqa.py`，具体契约见 `GQA_GROUP_ZH.md`。生产执行固定f94c9db，独审服务器4文件固定9f1122e；74源文件验证，5个S32 CLI与6个S16独审配置全部双模式通过，独审42个case/head逐bit相等。原始GQA fixture SHA为ee5722b38a1acb94daf4d09e49651c9a4610dbc9a9b0ac444b29bb1ef2280080，留服务器 `gqa_capture_v1/private_fixture/qwen_layer12_gqa7_context64.json`；完整结果留 `gqa_validation_v1`，均相对本人任务根。自动审批拒绝私有激活下载后没有尝试绕过，公开结果仅白名单计数/误差/时间/散列，位于 `results/gqa_real_20261023`，服务器/本机/Git字节由独审复核。旧v5矩阵来源与回执未改。

下一步先核PR125完整FFN和调度优化的最新公开版本；保留全trace/动作/字节等价门，再按 `gqa_scaling/ASSESSMENT_ZH.md` 配容量跑2K。N64/128仅为event-only受限小probe，约93分钟是外推而非实跑。Ramulator在线后端的异步时序/写可见性改造见 `RAMULATOR_ONLINE_FEASIBILITY_ZH.md`；当前banked内存不能冒称DRAM命令执行。新增维护规则要求共享cache同时约束union扫描、metadata和operand生命周期，已放在cycle_v1/AGENTS.md。

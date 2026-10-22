# Issue116 交接

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

# Issue116 交接

负责人 amlink1219；唯一目标 `rayggxia-workspace/pbit-llm-qwen-baselines`，任务分支 `task/116-cycle-execution`，base `pbit-tlm-attention-details-20261016@46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d`。本机专用目录 `E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/workspace_projects/cycle23`；不要切换、清理或重置其他任务工作树。

科学入口 `architecture_tlm/cycle_v1/IMPLEMENTATION_ZH.md`，运行说明同目录README，独立检查 `audit/REVIEW_ZH.md`。已完成有限周期原型、68真实片段+8synthetic用例、缩小单层、native随机协议、协议RTL、ONNXim试验、v6桥、PR122兼容复验和条件敏感性；不把这些称为原A–G全完成。未做完整Qwen/Llama、真实全维多头/GQA层、在线DRAM命令后端、全局容量/随机网络及物理PPA闭合；具体门禁在 `FULL_MODEL_TODO_ZH.md`。

关键执行：2776 real68+smoke8 COMPLETED/0:0；2764 RTL9case252握手；2772 ONNXim2官方/4自定义场景；2759 GPU14秒fixture。没有遗留本任务运行作业，发布前还要再核一次调度。2775首轮62pass/6死锁、2766/2774启动失败以及外部构建恢复均保留；最终通过不抹去失败记录。

完整矩阵原始结果：`/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/matrix-v5-results.tar.gz`，SHA-256 `82319f0d95054149e7d3dbeba5248648d461fe91539107aaa85e83fd44429ee5`。本机 `outputs/tlm_cycle_20261023/matrix-v5-results.tar.gz`（相对DAC根，非相对此checkout）；compact正式成果及原始manifest在 `architecture_tlm/cycle_v1/results/matrix_20261023`。实际执行快照 `cycle-source-v5.tar.gz` SHA `f6c596f3d772dee19bea1d85badb25fe0088aefaaae70ab959555b68daf96cbf`，同任务服务器根。完整source manifest在 `server/matrix_source_v5.json`。

Qwen权重和语料在本人原项目 `/home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/`；不得复制到Git。私有冻结片段在本人任务根 `real_fixtures_v1`，本机ignored `work/amlink1219/116/private_fixtures`；MANIFEST列出model/config/text/token和逐fixture SHA。删除/覆盖仍需要用户明确授权，本轮没有清理任何历史数据。

后续恢复：先读取远端Issue116/本PR、最新集成入口、PR119/120/122/125及成员STATUS。PR122兼容性复验针对固定8007d98，不等于合并；新的来源提交要重新核接口。PR125在a9c0031d4b4f45697f6b52144948d6ac084df2f4已经记录完整FFN fixture抓取（2777）和编码恢复45场景（2778），接合仍在独立工作树进行，依赖本后端正式发布；不要重复抓取或接管。实际STA/PPA按其交接由jieruiz执行，EDA尚未运行。中央台账目前新增独立record，多个并行PR集成时合并record_ids后重建总览，不能直接覆盖其他人的catalog。

最小命令（新输出路径；服务器上必须Slurm CPU allocation）：

```bash
python -m architecture_tlm.cycle_v1.run --operator ffn --output /personal/new-ffn
python -m architecture_tlm.cycle_v1.run_layer --output /personal/new-layer
python -m architecture_tlm.cycle_v1.v6_adapter --operator ffn --smoke --output /personal/new-bridge
python -m architecture_tlm.cycle_v1.audit.run_audit --output /personal/new-audit
```

发布阶段最初为prepared；实际远端ref、PR head、文件blob核验及看板结果以同目录 `PUBLICATION.json` 为准。不得自动合并或关闭Issue116。若无Projects权限，明确保留待同步，不把看板更新写成完成。

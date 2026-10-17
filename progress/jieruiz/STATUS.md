# jieruiz 项目进度

更新时间：2026-10-17（Asia/Shanghai）；本机 Git 凭据实际身份：jieruiz。

| 项目 | 当前状态 |
|---|---|
| 本任务 / 负责人 | [Issue #7](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/7)，FFN 调度与数字 CIM 仿真；@jieruiz |
| 目标仓库 | rayggxia-workspace/pbit-llm-qwen-baselines |
| 分支 / PR base | task/7-ffn-cim-scheduling → pbit-tlm-attention-details-20261016 |
| 基线提交 | 9608c0d06cf8b421cbbd348aca4fc84c5990aae7 |
| 独立目录 | a_P_BIT/tmp/ffn-cim-issue-7-20261017/ |
| 成果 | [报告与仿真清单](../../architecture_tlm/FFN_CIM_SCHEDULING_AND_SIMULATION_ZH_20261017.md)、计数工具、源摘录及审计 JSON |
| 当前阶段 | 本地完成并验证通过；任务分支提交待上传，尚未合并 |
| 实际验证 | 已执行归档循环服务回放，独立公式与历史 tile 数/部分和字节数核对通过；最终范围和 manifest 验证见 work/jieruiz/7/ |
| 不适用/未运行 | 没有数值推理或新编码质量对比，未运行新 BF16/PPL；没有新 RTL/DC/PT、版图或 DRAMSys |
| 限制 | 非线性、格式转换和权重驻留仍有参数代理；本地完整 v5/v6 未在本任务集成发布 |
| 待同步 | Projects 缺 read:project，看板待补权限；Issue/PR 正常同步 |
| 接续 | [HANDOFF](../../work/jieruiz/7/HANDOFF.md)，先冻结 tile 的存储/格式接口，再按报告仿真 |

先前 Issue #1/PR #2 治理、#3/PR #4 架构审计、#5/PR #6 DRAM/DS-CIM 均保持各自分支、待审未合并。本任务未覆盖其文件或把 PR 创建说成合并。

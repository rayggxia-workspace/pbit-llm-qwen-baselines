# jieruiz 项目进度

## Issue #7 工艺表征续接（2026-10-17）

- 负责人：核验 GitHub 登录 `jieruiz`；目标 `rayggxia-workspace/pbit-llm-qwen-baselines`。
- 本地目录 `tmp/ffn-epilogue-ppa-20261017/`，独立分支 `task/7-epilogue-ppa100`，PR base `task/7-ffn-cim-scheduling` @ `dac6e0426da6421ccc62077275e236532ca3c3da`；依赖原 PR #8（待审未合并）。
- 范围：SwiGLU Q10 单通道 100MHz TT/SS DC→端口校验门级 VCS→PT PX。保留原算术 RTL；不是完整 FFN/BF16/PPL。
- 实际验证：18 个窗口、每窗口 4096+8 测量拍，三种子/两分布/三模式，Icarus 端口逐周期值/valid/flags 全通过，测量 VCD 无 X/Z；功耗单位、逐单元汇总、负 slack 标记、截断/X拒绝、断点文件校验测试通过；Bash 语法和 Tcl 词法完整性检查通过。
- 当前阶段：已推送；[PR #11](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/11) 待审、未合并，依赖原 PR #8。工艺运行未执行，工艺库、DC/VCS/PT 由用户服务器提供；没有伪造 PPA 数值。
- 成果：[PPA说明](../../architecture_tlm/rtl/ffn_epilogue_20261017/ppa/README_ZH.md)，辅助材料/验证位于 `work/jieruiz/7/epilogue_ppa/`。
- 待同步：项目看板缺 `read:project`；原 Issue #7 已记录本次分工。下一步上传脚本包并执行 `bash ppa/submit.sh all`，下载 TT/SS 报告包审查。
- 交接：[PPA_HANDOFF](../../work/jieruiz/7/epilogue_ppa/HANDOFF.md)。下方历史状态保留，不把旧验证当本次 DC/PT 结果。

## 原任务记录

更新时间：2026-10-17（Asia/Shanghai；经典结构与 RTL 补充）；本机 Git 凭据实际身份：jieruiz。

| 项目 | 当前状态 |
|---|---|
| 本任务 / 负责人 | [Issue #7](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/7)，FFN 调度与数字 CIM 仿真；@jieruiz |
| 目标仓库 | rayggxia-workspace/pbit-llm-qwen-baselines |
| 分支 / PR base | task/7-ffn-cim-scheduling → pbit-tlm-attention-details-20261016 |
| 基线提交 | 9608c0d06cf8b421cbbd348aca4fc84c5990aae7 |
| 独立目录 | a_P_BIT/tmp/ffn-cim-issue-7-20261017/ |
| 成果 | [报告与仿真清单](../../architecture_tlm/FFN_CIM_SCHEDULING_AND_SIMULATION_ZH_20261017.md)、[经典结构与选型](../../architecture_tlm/CLASSIC_AND_PROBABILISTIC_FFN_ARCHITECTURE_ZH_20261017.md)、服务计数工具、[后处理 RTL](../../architecture_tlm/rtl/ffn_epilogue_20261017/README_ZH.md) |
| 当前阶段 | 已推送；[PR #8](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/8) 待审，未合并 |
| 实际验证 | 归档循环与公式核对；12 个资源/采样服务场景；新 RTL 经 Icarus 三种子各 12295 周期、双输出位宽验证；active/burst/idle 计数通过。最终范围与散列见 work/jieruiz/7/ |
| 不适用/未运行 | 没有模型数值推理/新 BF16/PPL；没有 DC/PT、版图或新 DRAMSys。RTL 是定点近似候选，不是 BF16 等价实现 |
| 限制 | 新后处理尚无工艺 PPA/模型回归，未启用到现有模型；原非线性、格式转换和权重驻留代理未擅自改值；完整 v5/v6 未在本任务集成发布 |
| 待同步 | Projects 缺 read:project，看板待补权限；Issue/PR 正常同步 |
| 接续 | [HANDOFF](../../work/jieruiz/7/HANDOFF.md)，先冻结 tile 的存储/格式接口，再按报告仿真 |

先前 Issue #1/PR #2 治理、#3/PR #4 架构审计、#5/PR #6 DRAM/DS-CIM 均保持各自分支、待审未合并。本任务未覆盖其文件或把 PR 创建说成合并。

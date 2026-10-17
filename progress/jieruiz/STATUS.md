# jieruiz 项目进度

更新时间：2026-10-18T00:05:44+08:00（Asia/Shanghai）。负责人 @jieruiz，正式仓库 `rayggxia-workspace/pbit-llm-qwen-baselines`；实际GitHub登录已核验。

## 当前交付：Llama 2 7B（Issue #14）

| 项目 | 实际状态 |
|---|---|
| Issue / PR | [#14](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/14) / [#15](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/15)，Issue待评审验收，不自动关闭 |
| 分支 / base | `task/14-llama2-baseline-tlm` → `pbit-tlm-attention-details-20261016` @07d03385a3b16b1f81a987c031f667c13876edf1 |
| 独立工作目录 | `C:/Users/86134/Documents/a_P_BIT/tmp/llama2-7b-issue14-20261017` |
| 当前阶段 | 全部116项本地汇总完成，准备推送并转PR #15待审 |
| 原BF16实际基线 | Slurm1961完成，完整WT2 PPL2K **4.9795028452** / 4K **4.8958312205**；stride512、335686个target各计一次 |
| 其他作业 | 下载1960、捕获1963、Link1964、Staggered1965、NoPowerDown1966、后处理2069均完成；旧pending1962已取消；当前无本任务运行中作业 |
| 实际验证 | 11模型文件匹配官方；4上下文捕获前后逐bit相同；9＋7＋11=27本地检查；116项及时间/能量/访存守恒；57冻结输入、原始SHA及发布Git字节检查 |
| 正式成果 | [完整中文表](../../architecture_tlm/llama2_7b/results/current/RESULTS_ZH.md)、[入口](../../architecture_tlm/llama2_7b/RESULTS_INDEX_ZH.md)、[交接](../../work/jieruiz/14/HANDOFF.md) |
| 远端项目 | `/home/Hongjie_Zeng/projects/pbit-llama2-7b-20261017-issue14`，大型原始成果按索引访问 |
| 版本 | BF16源9ee1ab47d0317430212364e75adb78abec9797fb；capture/TLM源b5964b165dfead06676580029235bf5e952b5dad；report源358d8b8f943f60986f86362f7bc7aacfca531adc |
| 限制 | 原BF16 PPL独立于单查询/上下文地址oracle；无联合替换PPL或芯片/GPU能效实测；Ising物理混合/部分算子PPA未标定 |
| 下一步 | 评审PR15；新优化/联合质量实验另建Issue、分支及不可变快照，不重复已完成作业 |

待同步：上传最终成果、更新PR/Issue；Projects缺read:project

镜像是用户明确授权的ModelScope `shakechen/Llama-2-7b-hf` @e61a2c602c83286a3ffbadaa29c20ad1160a8c4e，11文件匹配官方 `meta-llama/Llama-2-7b-hf` @01c7f73d771dfac7d292323805ebc428287df4f9；不发送token/cookies。权重不上传Git。

## 已合并：LLaMA-1 7B（Issue #12）

PR #13已按用户授权合入TLM分支，merge `07d03385a3b16b1f81a987c031f667c13876edf1`，Issue #12已关闭。82项结果、源84c131951b9ce69a52778e8725d62a21ab9cc40f与服务器 `/home/Hongjie_Zeng/projects/pbit-llama7b-tlm-20261017-issue12/` 保留。无本任务运行中作业；Llama2没有覆盖Llama1/Qwen。

此前治理#1/PR#2、架构审计#3/PR#4、DRAM#5/PR#6、FFN#7/PR#8及#11、筛选K流量#9/PR#10仍为独立待审分支。本任务没有覆盖其工作树；看板权限待补齐。

# jieruiz 项目进度

更新 2026-10-18T12:58:30+08:00（Asia/Shanghai）；实际登录@jieruiz，正式仓库rayggxia-workspace/pbit-llm-qwen-baselines。

## 当前：Issue16 三模型目录

| 项目 | 实际状态 |
|---|---|
| 分支/base | task/16-model-folders → pbit-tlm-attention-details-20261016 @7a506365cce42fd257f2645aa589b624e7d77116 |
| 独立目录 | C:/Users/86134/Documents/a_P_BIT/tmp/model-folders-issue16-20261018 |
| 当前阶段 | 三个模型目录及本地验证已完成，准备上传独立PR |
| 范围 | qwen/、llama1/、llama2/统一运行、配置、基线和结果入口，共享模块与历史路径不动 |
| 验证 | 24次命令检查、17个源码/结果SHA锚点、93链接、119冻结输入通过；3模型参数/退出码透传和4类越界路径检查通过 |
| 成果/交接 | work/jieruiz/16/；三个目录的README/project.json；根README |
| 阻塞/待同步 | Projects缺read:project；无模型/数据阻塞，本次无远端计算作业 |
| 下一步 | 上传已验证代码与目录索引，通过独立PR交付，再同步实际状态 |

## 已合并任务

- Llama2 Issue14 / PR15已按用户2026-10-18授权合并，merge 7a506365cce42fd257f2645aa589b624e7d77116，Issue14已关闭。完整BF16 WT2 PPL2K4.9795028452 / 4K4.8958312205、116项TLM保留；本次没有联合替换PPL或芯片/GPU实测。
- LLaMA1 Issue12 / PR13已合并，merge07d03385a3b16b1f81a987c031f667c13876edf1，Issue12关闭，82项TLM保留。

此前治理#1/PR#2、架构审计#3/PR#4、DRAM#5/PR#6、FFN#7/PR#8及#11、筛选K流量#9/PR#10仍为独立待审分支，本次未覆盖其改动。其他成员STATUS只读。

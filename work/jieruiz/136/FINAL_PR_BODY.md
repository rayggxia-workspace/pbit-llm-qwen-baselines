关联 #136，负责人 @jieruiz。用户要求使用镜像在服务器建立Qwen3-1.7B与4B基线，本PR采用此前讨论的Base版本。

## 已完成结果

| 模型 | 原始BF16完整WT2 PPL | 目标token | GPU评测秒 |
|---|---:|---:|---:|
| Qwen3-1.7B-Base | 8.3673395166 | 299077 | 16.9192 |
| Qwen3-4B-Base | 7.0386116013 | 299077 | 32.9219 |

均292窗口，window2048/stride1024，seed0，无chat/BOS/cache；同token序列SHA，全部位置1..N-1恰好计分一次。原生BF16 SDPA/FFN不变，FP32交叉熵、逐窗口NLL总和计算PPL。RTX5090；下载/模型加载/排队不计入GPU评测秒。

正式报告：qwen3/results/bf16_20261023/REPORT_ZH.md；原始JSON、模型/分词器/数据清单、成功/失败日志、11文件服务器SHA和VALIDATION.json同目录归档。大权重只留服务器。

## 实现与验证

- 固定hf-mirror模型revision并验证LFS SHA/普通Git blob，独立Transformers4.51.3环境；旧4.45.2环境不变。
- 冻结执行968046f9346258029192983000b4def643667cca；CPU计分覆盖和原生tiny Qwen3 GQA/QK-Norm/save-reload通过。
- python qwen3/baselines/test_baseline.py：2组覆盖/非法参数检查通过。
- python qwen3/validate_baseline_results.py：11原文件SHA、源码/模型/配置/数据绑定、完整覆盖与NLL/PPL重放通过，10损坏负例均被拒绝。重放仅审计存储数值，没有第二次GPU推理。
- Git原件使用-text保护，日志binary避免换行/进度控制字符被转换；上传按原blob/tree/commit SHA核对。

## 失败与限制

CPU2797在校验1.7B后遇4B镜像连接中断，GPU2798依赖取消；CPU2799有限重试后4B全部10文件通过，GPU2800_0/2801_1产出完整结果。原日志保留，未修改原快照。Slurm accounting关闭、完成job已过scontrol保留期，不伪造sacct回执。

仅建立未修改模型基线，无随机FFN/Attention、训练、PPA或任务准确率测试。模型间PPL差不是随机替换收益；后续随机候选须匹配模型/语料/协议，至少3seed。Projects缺read:project仍待同步。

STATUS/HANDOFF/长期记忆已更新。本PR转待审，不自动合并；Issue136保持open至评审验收。用户定时检查目的已完成，按实际停表回执结束。

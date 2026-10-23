# 结果回传与验收

请先交付小型结果与可恢复索引，20层权重/基模型/数据不上传Git。保留服务器完整run原件。归档写在run目录之外，显式列regular files，不把正在增长的日志或归档自身加进去；压缩完成后检查退出状态及SHA-256。

## 必须给出的信息

- 实际操作者GitHub登录名、服务器OS用户/canonical home、host、CPU/GPU Slurm job ID、分配节点/GPU型号、首次终态/ExitCode/AllocTRES、完整执行命令及UTC时间。
- 代码准确commit、包外部SHA/BUNDLE_MANIFEST、自己额外补丁/新commit（若有）、config与源码manifest；`site.env`可提供脱敏版本，禁止凭据。
- 模型/tokenizer/20份checkpoint实际位置、大小、SHA；原始版本/phase/step。数据来源revision/parquet SHA、固定题目ID/tokenized SHA、harness版本与源码SHA、环境包版本/pip freeze。
- CPU strict PREFLIGHT_READY、GPU SMOKE_READY及各门禁真实记录，stdout/stderr和异常。只有实际通过才标完成；失败也保留负结果/阻塞。
- 12个完整case：BF16的PIQA/ARC-Easy/HellaSwag各一个，20层P-DNN每任务seed0/1/2；每个case的metadata、逐题JSONL、进度、summary和SHA。逐题logprob/greedy/tokens与原始题号必须完整，不能只交截图或总百分比。
- 最终每任务 BF16 acc/acc_norm、20层三seed值、均值和样本标准差、相对BF16百分点差。明确0-shot、PIQA1838、ARC-Easy2376、HellaSwag固定1000/10042、N4完整路径；不要把三seed标准差写成置信区间或训练波动。
- 归档文件位置、大小、SHA-256、文件成员manifest；记录谁有读取权限/如何取得。若存储未获授权，不擅自公开，列待同步项。

## 在workspace交付

核对正式仓库和本人认证身份/权限/push URL；自己独立任务分支和PR关联Issue151，结果放`qwen/results/pdnn20_task_accuracy_20261023/<本人用户名>/<run>/`或已有正式结果目录；辅助材料放`work/<本人用户名>/151/`，更新自己的`progress/<本人用户名>/STATUS.md`。不要写移交人的STATUS，不覆盖原件/历史结果，不自动合并/关闭Issue。

在Issue151评论本次run、PR、源码commit、验证、12case是否完整、实际阻塞与下一步；有权限才同步看板。不将本地完成写成已上传。若GPU未完成，返回job ID、当前阶段、真实已完成case、终态或是否仍运行、partial位置和后续命令。

## 可直接填写的回传摘要

```text
Issue151 / 接手者：
PR（待审/已合并）：
源码commit / 交接包SHA：
服务器账号、canonical home、节点/GPU：
CPU job / State / ExitCode：
GPU job / State / ExitCode：
严格checkpoint/SHA检查：
真实GPU smoke：
BF16完成数： /3；20层完成数： /9
PIQA BF16 acc / acc_norm；PDNN三seed均值±样本std；百分点差：
ARC-Easy ...：
HellaSwag固定1000 ...：
完整run / 归档 / SHA-256 / 访问方式：
未完成、阻塞、待同步、下一步：
```

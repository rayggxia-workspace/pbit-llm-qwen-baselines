# 发给师弟的20层 P-DNN 评测交接包

可以由你在自己的服务器账号下提交任务。目标是把已有**联合训练20层 P-DNN**测完 PIQA、ARC-Easy、HellaSwag 的准确率，沿用两层/四层评测协议；不用重新训练，也不用先把权重传给移交人。

## 先把这段发给你的 agent

> 请接手续做 rayggxia-workspace/pbit-llm-qwen-baselines 的 Issue151。先校验交接 ZIP 的外部 SHA，再读包内 BUNDLE_MANIFEST.json、根 AGENTS.md、experiments/pdnn20_task_accuracy_20261023/handoff/AGENTS.md、START_HERE_ZH.md、SERVER_RUN_ZH.md 和 RETURN_CHECKLIST_ZH.md，并查看远端最新 Issue151、PR155、Issue145/PR149 及相关 STATUS/HANDOFF。使用我自己的服务器/GitHub账号和个人目录，先确认现有作业与分工；不要冒用 amlink1219/Weican_Chen。定位我已有的 joint20 step1000 原始20份权重，通过固定 SHA/payload CPU 预检后，按 portable_runner.py 流程执行真实 GPU smoke、三任务本机 BF16 和20层三seed评测。提交前保留 intent，提交后立即保存 job ID，不重复开工、不改模型协议。完成后按回传清单整理证据，推自己的任务分支并向正式 workspace 仓库提交 PR，关联 Issue151。缺权限/数据/环境明确记录，不把准备完成写成评测完成。

## 包内已有与需要你提供的

| 已包含 | 用途 |
|---|---|
| 完整路径 P-DNN 实现、共享随机评分器、20层便携 runner 与机制测试 | 沿用已有采样/缓存/RNG及官方计分协议 |
| config、20份原权重大小/SHA与检查清单 | 防止拿错20层版本 |
| 三项固定 parquet、来源/revision/SHA | 避免数据下载或选集漂移；仅在本地 ZIP，不入 Git |
| 路径无关模型/tokenizer/harness/task/tokenized pins | 换账号后仍核对同一协议 |
| Slurm执行模板、环境版本、agent规则、结果回传清单 | CPU门禁→GPU smoke→完整结果 |
| 根 README/AGENTS/项目备忘录和原任务交接的版本快照 | 理解已有项目规则及交接状态；恢复时仍查远端 |

你需要提供自己的服务器个人目录、Slurm分区/资源、隔离 Python 环境、Qwen2.5-0.5B **Base**本地目录，以及已有20份原始 checkpoint（共697,875,430 bytes，约665.5MiB）。**包内不含模型权重、P-DNN checkpoint、环境或任何登录凭据。**

目标20层：`[1,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22]`；保留原FFN `[0,2,3,23]`。串联 bipolar FullPath v1，joint step1000，每层896→4864→896，输入/隐藏±1、连续BF16权重/读出，原SDPA Attention。N=4指**4条完整采样路径**。历史WT2 PPL约48.91只用于辨认模型，不是本次准确率。

## 固定验收范围

| 任务 | 题目 | 完整case |
|---|---|---|
| PIQA validation | 全1838 | BF16 seed0 + P-DNN seed0/1/2 |
| ARC-Easy test | 全2376 | BF16 seed0 + P-DNN seed0/1/2 |
| HellaSwag validation | 预先固定1000/10042 | BF16 seed0 + P-DNN seed0/1/2 |

共12个完整case；先做每任务首题/最长prompt的 BF16 与 P-DNN smoke。0-shot，无chat template，官方 lm_eval0.4.8 prompt/`_encode_pair`/`process_results`，同时报告 acc 与 acc_norm（后者按原选项**字符长度**归一化）。新服务器重跑 BF16 三项各一次；BF16无随机P-DNN，无须三个seed。20层报告三seed均值、样本标准差、相对同机BF16百分点差；不跨任务简单平均。

## 版本与尚未完成事项

对应 [Issue151](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/151)、[PR155](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/155)，依赖[PR149](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/149)的两层/四层评分协议。源码准确提交及逐文件字节以包内 manifest 为准，PR 状态以远端为准。

移交人已在自己的服务器通过 CPU Slurm2862（28项检查），但尚未取得20份权重、未执行真实20层GPU推理、没有新的20层准确率。**便携入口也必须由接手者通过真实环境/真实checkpoint预检及GPU smoke后才能跑全量。** 本包不宣称已在师弟的服务器执行。

继续按 [SERVER_RUN_ZH.md](SERVER_RUN_ZH.md) 操作；完成后按 [RETURN_CHECKLIST_ZH.md](RETURN_CHECKLIST_ZH.md) 回传。

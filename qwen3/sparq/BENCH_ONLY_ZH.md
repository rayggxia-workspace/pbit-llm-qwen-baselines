# 独立 GPU benchmark 补测

本入口补测修正 UUID 规范化后的计时/板卡功率，复用 `benchmark.run_benchmark`，没有另写 timer。当前实现依据 `ab27a40`；实际执行以新bundle的完整提交和逐文件SHA为准。原作业2878、质量源码 `8d60abe4e7c5c245c8f5f87b7f66e49e23ae0eea` 的PPL、任务结果和54项旧benchmark保持独立；新结果不能冒充原快照已测得功率。

本CLI不提交/监控Slurm，不停止或修改原作业。由任务负责人确认原GPU作业终态、保存终态回执后，再使用已授权个人环境的GPU allocation调用。CPU测试与本地freeze无需CUDA；没有allocation的run在导入Torch前拒绝。

## 固定合同与门禁

- 模型固定 `Qwen/Qwen3-4B@1cfa9a7208912126459214e8b04321603b3df60c`，original FFN，BF16加载/原生SDPA；主配置r32/k128/local32、probability_sum、reallocation=False、validate_finite=False、seed0。
- 固定context128/512/2048 × decode64/128 × native/dense/sparq × 3重复，共54个完整trial、108个phase窗口；每case/mode一次warmup，batch1，固定teacher-forced输入。没有PPL或MC调用。
- 显式钉住原`IDENTITY.json`原始SHA；核验原preflight/benchmark的experiment与payload散列、原preflight通过、完整54项benchmark矩阵和来源。原quality snapshot未完成不妨碍补测，但补测永远不声明完成质量评估。
- `core.py`、`adapter.py`、token-ID散列函数源码必须与原IDENTITY一致；计量代码可以改变并记录新SHA。数值源码改变应另建实验，不能沿用本入口。
- READY原始SHA必须与原IDENTITY一致；本地10个模型/分词器文件逐一验证大小与SHA，不能只查存在；WT2 test原始字节和重新tokenize的全语料int64散列都核对。MC数据不使用、不重新验证，不宣称已重跑任务。
- 包版本与原IDENTITY一致，GPU实际UUID/name及job另录入新identity。新设备允许作为单独测量，不能隐瞒设备变化或混合统计。全模型在同一已分配CUDA设备；源码/输入/输出位于真实登录用户的canonical home中。

## 先提交，再本地冻结

在包含本入口的准确Git提交根目录：

```bash
python3 -B -m unittest qwen3.sparq.test_bench_only -v
python3 -B -m qwen3.sparq.bench_only freeze --out /absolute/new/supplement-bundle
```

freeze只导出13个固定公共依赖/文档/测试文件的Git提交字节及`EXECUTION.json`，拒绝未提交依赖和已存在目标。不会复制模型、数据、环境、凭据或旧结果；不联网。将bundle上传到核实过的个人源码新目录，逐SHA核验后，在**提取后的bundle**中复跑同一CPU测试。不得把新文件覆盖到原8d60运行快照。

## 后续GPU allocation中的唯一执行命令

以下是参数模板，执行者须使用已核验的个人路径和原IDENTITY真实SHA，不填写猜测散列；不在登录节点执行：

```bash
cd /verified/personal/supplement-bundle
/verified/personal/env/bin/python -B -m qwen3.sparq.bench_only run \
  --root /verified/personal/sparq-qwen3-issue157 \
  --parent-results /verified/personal/sparq-qwen3-issue157/results/8d60abe4e7c5 \
  --parent-identity-sha256 EXACT_ORIGINAL_IDENTITY_SHA256
```

`SLURM_JOB_ID`、非空`CUDA_VISIBLE_DEVICES`由真实allocation提供，不手工伪造；入口要求可见设备恰为1且支持BF16。复用已安装的原环境，不自动安装NVML/CUDA、不改功率限制或GPU配置。

输出固定为：

```text
<root>/benchmark_supplements/<measuring_commit_12>_<parent_identity_fingerprint_12>/<job_id>/
  IDENTITY.json
  INVOCATION.json
  progress.jsonl
  benchmark_supplement.json
  report.json
  report.sha256.json
  FAILED.json             # 仅失败时；后续保留为历史诊断
```

结果使用原runner的单文件payload+digest原子提交；不会写原`results/`或其别名。相同job已有完整结果时核验后直接返回；结果已提交但report写入中断可重建report，不重新跑GPU。未完成的trial只保留progress供诊断，不声称具有逐trial恢复能力；新作业是独立补测。

## 下载与解释

`report.json`自包含来源/设备/配置、18组汇总、54trial完成数、功率可用窗口数及待下载artifact的原始SHA/字节数；`report.sha256.json`保存report自身原始SHA，避免自引用散列。下载后先核对report，再逐项核对`transfer_artifacts`；这些是传输/来源证据，不是额外测量。完整54trial与raw power样本在`benchmark_supplement.json`中。

功率仍服从benchmark的UUID双重核验、>=1s窗口、最大采样gap等门禁。NVML不可用、错UUID、过短或缺采样时保留原因并为null；可用值也只是board采样估计，`phase_energy_attribution_validated=False`，并非进程专属或ASIC功耗。补测不会修补旧benchmark文件、继承原快照的质量完成状态或生成虚构面积。

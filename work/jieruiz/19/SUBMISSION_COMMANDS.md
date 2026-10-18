# 不可变快照与Slurm命令

执行版本：`a8ea21f75ae6d736b2bc0136f8ee55977b082060`。任务PR以后新增的文档/结果提交不改变该运行源码。模型身份、数据SHA、配置和算术规范见正式实验README与每个输出source/identity/protocol。

服务器已授权个人项目：

```bash
PROJECT=/home/Hongjie_Zeng/projects/pbit-llama2-ffn-precision-20261018-issue19
SNAPSHOT=$PROJECT/snapshots/ffn-a8ea21f75ae6
SHA=a8ea21f75ae6d736b2bc0136f8ee55977b082060
SLURM=/opt/slurm/21.08.8/bin
```

先用`git archive`生成包含`experiments/llama2_ffn_precision`、`baselines/llama2_7b`、`architecture_tlm/llama2_7b/configs/model_identity.json`的快照，发送到上述新目录（不覆盖原快照）。归档tar SHA在suite_submission.json。实验目录显式eol=lf；vendor子目录保留Issue7原字节，不规范化已记录哈希的资料。

基线使用base `dd9f12b8cc25f474cafb54b1a58f2be20506cd9e`的原baseline源码；原sbatch归档带CRLF，第一次被Slurm拒绝且未生成作业。保留原件，新建仅LF化的驱动`run_bf16_lf.sbatch`后提交2081，结果和原参考完全一致。首次数值snapshot `98223ab`同样被Slurm拒绝；新增目录LF属性后以a8ea21f重建快照才提交2082/2083，没有修改提交中的快照。

实际提交命令等价于：

```bash
$SLURM/sbatch --parsable --chdir="$SNAPSHOT" --mem=8G --time=00:15:00 \
 --output="$PROJECT/logs/test-%j.log" \
 --export="ALL,SOURCE_COMMIT=$SHA,PROJECT=$PROJECT,ACTION=test,CONFIG=experiments/llama2_ffn_precision/configs/calibration.json,OUTPUT=$PROJECT/outputs/test" \
 "$SNAPSHOT/experiments/llama2_ffn_precision/run.sbatch"
# 2082，17/17通过（含CUDA）

$SLURM/sbatch --parsable --chdir="$SNAPSHOT" --dependency=afterok:2081:2082 --time=02:00:00 \
 --output="$PROJECT/logs/calibrate-%j.log" \
 --export="ALL,SOURCE_COMMIT=$SHA,PROJECT=$PROJECT,ACTION=calibrate,CONFIG=experiments/llama2_ffn_precision/configs/calibration.json,OUTPUT=$PROJECT/outputs/calibration" \
 "$SNAPSHOT/experiments/llama2_ffn_precision/run.sbatch"
# 2083，完成；仅train前8192token

$SLURM/sbatch --parsable --chdir="$SNAPSHOT" --dependency=afterok:2083 \
 --output="$PROJECT/logs/ppl-%A_%a.log" \
 --export="ALL,SOURCE_COMMIT=$SHA,PROJECT=$PROJECT" \
 "$SNAPSHOT/experiments/llama2_ffn_precision/suite.sbatch"
# 2084，0-25%2，26完整PPL，最多2GPU
```

作业当前状态需要实时查询，不能把上述提交记录等同完成证明：

```bash
$SLURM/squeue -u Hongjie_Zeng
$SLURM/sacct -j 2081,2082,2083,2084 --format=JobID,JobName,State,Elapsed,ExitCode
```

每个正式PPL输出仅在全部335686个目标计分完成后写summary与ARTIFACT_MANIFEST。使用原manifest逐文件SHA验证后收回小型JSON；逐窗NLL.jsonl留原服务器目录，其哈希仍保留在原manifest中。提交后若需要更改源码/配置，必须创建新快照与新输出目录，记录旧失败及新作业，不修改已运行快照。

本地准备/提交/采集辅助脚本目前在混合工作区`tmp/issue19_*.py`，不是正式模型代码。以上命令、Git配置与每个输出command/config/source足以复现，不依赖隐藏凭据或这些本地脚本。

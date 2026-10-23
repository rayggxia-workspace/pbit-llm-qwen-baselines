# 接手服务器执行步骤

以下变量是示例，必须在你自己的账号核实后填写。`portable_job.sh`不会提交任务；它只在已有 Slurm allocation 内执行。先读本目录 AGENTS。不要执行旧版绑定移交人 home 的 runner/sbatch。

## 1. 核实账号、任务、路径、调度器

先看最新 Issue151/PR155 和145/149及相关交接，确认未重复开工，在原 Issue 记录你负责服务器执行；检查已有 job ID 和队列。包内历史作业2835属于移交人两层/四层任务，状态可能已变化，不能根据旧记录自行取消或重提；项目最多一个pending/running GPU，须协调后再提交。

只读检查：`id`、`getent passwd "$(id -u)"`、`realpath "$HOME"`、home属主；核实服务器角色、Slurm路径、分区、当前账号`squeue`、资源额度。所有下面路径须在你自己的canonical home内，外部共享模型或别人的私有目录不能直接套用本入口。

先在个人home下建立独立项目目录，解包到其`source/`。外部ZIP SHA与包内BUNDLE_MANIFEST一致性在CPU任务中再核验。短路径如`$HOME/pdnn151/source`即可；不要在运行中改动source。包内`data/`已含三parquet，checkpoint单独保持原件，模型目录也由你提供。

## 2. 准备自己的隔离环境和原始权重

已验证参考为Python3.12.3、torch2.7.1+cu128、Transformers4.45.2、lm_eval0.4.8，其他关键依赖见`requirements-pinned.txt`。安装/下载/解包大模型经CPU Slurm staging，隐藏GPU，复用个人`PIP_CACHE_DIR`；不能用系统或共享/base环境全局pip。torch用官方cu128 wheel源，其余用正常包源。该requirements只约束关键版本，不是全部传递依赖锁；安装后保存`pip freeze`和实际版本，strict预检还会比对harness源码SHA。

模型必须是Qwen/Qwen2.5-0.5B **Base**；以`portable_reference.expected.json`的7个模型/tokenizer文件大小/SHA为准。已有个人副本优先；缺失时自己按官方来源下载到个人目录，再校验字节。若tokenizer/config或harness源码与pin不符，先记录差异，不能放宽校验偷跑。

定位你已有原始`joint_full_path_pdnn_layers1_22_twenty_v1/best_layerN.pt`的20份文件，清单见`CHECKPOINT_REQUEST_ZH.md`和`SHA256SUMS.expected`。配置只指向它们，别重存、改名冒充或重训。目标接收目录示例`$HOME/pdnn151/checkpoints/joint20/`，其中直接放`best_layer1.pt`、`best_layer4.pt`…`best_layer22.pt`。若旧文件就在你的另一批准个人目录，可指定该目录，CPU预检最终判断；无需把权重发给移交人。

## 3. 填写本次profile

保存为自己项目根的`site.env`（不要写密码/token；不要提交别人的路径）。填写后逐项核对，不直接把示例占位值提交：

```bash
export PDNN_EXPECTED_USER=YOUR_LOGIN
export PDNN_EXPECTED_HOME=/home/YOUR_LOGIN
export PDNN_PROJECT=/home/YOUR_LOGIN/pdnn151
export PDNN_SOURCE="$PDNN_PROJECT/source"
export PDNN_PYTHON="$PDNN_PROJECT/env/bin/python"
export PDNN_MODEL="$PDNN_PROJECT/models/Qwen2.5-0.5B"
export PDNN_DATA="$PDNN_SOURCE/data"
export PDNN_WEIGHTS="$PDNN_PROJECT/checkpoints/joint20"
export PDNN_RUN="$PDNN_PROJECT/runs/joint20_YYYYMMDDTHHMMSSZ"
export PDNN_SRUN=/ABSOLUTE/VERIFIED/slurm/bin/srun
# 从包内BUNDLE_MANIFEST.json读取code_commit，不能填写PR号/分支名。
export PDNN_CODE_COMMIT=EXACT_40_HEX_COMMIT_FROM_MANIFEST
```

source只是已校验源码快照，Git身份/PR操作在另一个独立checkout内进行。包内代码变更后必须生成新提交/manifest/快照与run，不伪称仍为旧commit。Windows生成的脚本先核实LF，并对实际`portable_job.sh`执行`bash -n`，再用模板运行。别把本次profile变量拼到会被外层提前展开的SSH双引号中。

核对canonical home、project、source、model、data、checkpoint、run全部解析路径和属主后，才创建新的`runs/<唯一run>/`；不覆盖已有run。必要cache/tmp由执行脚本在个人project下创建。

## 4. CPU门禁，然后才GPU

在shell中读取自己核验过的`site.env`。Slurm账户、分区、CPU/内存/time资源由你按实际集群规则填写；下面只是模板。`SBATCH`为你核验的绝对sbatch路径，`PARTITION`为实际可用分区，提交前确认所需所有资源参数。

```bash
source "$PDNN_PROJECT/site.env"
JOB_SCRIPT="$PDNN_SOURCE/experiments/pdnn20_task_accuracy_20261023/handoff/portable_job.sh"
bash -n "$JOB_SCRIPT"
# 写下submission-intent：UTC、host、账号、run、命令及当时队列检查结果。
# 不带GPU申请，CUDA由cpu分支显式隐藏。
"$SBATCH" --parsable --job-name=pdnn151-cpu --partition="$PARTITION" \
  --cpus-per-task=2 --mem=8G --time=00:30:00 --export=ALL \
  --chdir="$PDNN_SOURCE" --output="$PDNN_RUN/cpu-%j.out" --error="$PDNN_RUN/cpu-%j.err" \
  "$JOB_SCRIPT" cpu
```

立刻记录返回job ID；保存第一次CPU终态`State/ExitCode/NodeList/AllocTRES`。CPU将运行机制/流程测试、校验交接包字节、模型/tokenizer、三项数据与固定请求、harness源码、20份SHA及strict checkpoint payload，只有全过才生成`PREFLIGHT_READY.json`。无checkpoint或不匹配均停止；`--inspect-only`只做准备信息，永远不允许GPU。

若CPU检查通过、确认无重复GPU任务且获得资源：

```bash
"$SBATCH" --parsable --job-name=pdnn151-gpu --partition="$GPU_PARTITION" \
  --gres=gpu:1 --cpus-per-task=4 --mem=24G --time=10:00:00 --export=ALL \
  --chdir="$PDNN_SOURCE" --output="$PDNN_RUN/gpu-%j.out" --error="$PDNN_RUN/gpu-%j.err" \
  "$JOB_SCRIPT" gpu
```

GPU脚本先做6项真实smoke：每任务首题和最长prompt，BF16与P-DNN各一项；包含独立BF16 oracle、RNG重放、选项置换和24层prefill/decode覆盖。通过后完成3个本机BF16全量case与9个20层全量case，最后CPU隐藏CUDA汇总。一次最多一个GPU，不开参数扫描、不改变N/层集合/精度来提速。10小时只是资源模板，不承诺运行时长。

## 5. 监控、失败与续接

保存job ID和scheduler结果；用`squeue/scontrol/sacct`实际可用路径检查。第一次终态立即落盘，避免短作业记录过期。SSH断线后先查询同一个job，不自动重提；提交超时结果不明也先查job name/时间/run保存记录。只有明确无现有任务且新提交已获协调后才再次提交。

如果smoke已完成、完整case也已部分完成，恢复前重验源码/输入/已完成原件，使用同一严格入口，它只跳过验证通过的完整case。**partial不自动覆盖或逐题续跑**；保留失败run，开新run重新执行，或提交明确的新恢复方案给移交人确认。源目录、profile或环境变动会触发冻结检查，不能手工补READY marker。

完成后按回传清单核对12case、题目覆盖与官方指标，并记录硬件/软件差异。与145已有两层/四层结果比较时先确认字节与协议一致、BF16表现相容；跨GPU/环境仍分别标注，不把软件时间/显存写成硬件功耗面积。

# Issue151：20层 P-DNN 评测准备交接

负责人amlink1219；独立工作树`workspace_projects/pa20`；分支`task/151-pdnn20-task-accuracy`；依赖PR149发布的`86eb22e1243ec5e215cb98be755bb92fb8f57e31`。本PR以`task/145-pdnn-task-accuracy`为base，只交付20层扩展。145的pa145及本机一次性收尾进程仍单独拥有其目录，不在本任务编辑、切分支或改动冻结helper。

## 用户最新范围

用户要求20层也测同三任务，并确认权重应在师弟处，自己会联系获取；现在先把其他准备齐。**权重尚未提供，没有20层GPU作业，也没有新的20层任务准确率。** 不擅自重训、从他人私有目录读取、选另一个20层版本或伪造结果。

目标为原串联bipolar FullPath v1 joint20 step1000：层1、4–22，保留原0/2/3/23；N4完整路径，896→4864→896，原SDPA与BF16连续权重／读出。20份文件697,875,430 bytes；[可转交给师弟的清单](../../../experiments/pdnn20_task_accuracy_20261023/CHECKPOINT_REQUEST_ZH.md)及JSON／SHA256SUMS均在正式experiment目录。

## 已准备／验证

实际CPU-only Slurm2862 COMPLETED/0:0，2026-10-23：服务器22＋6项检查全通过，模型／tokenizer／数据／固定请求／harness源码与145三个完整新BF16逐题原件／指标回读已匹配，无待补baseline。执行源码`ecd9418510565d76585aee71a4c5675dbcbd61e9`；87文件最小快照，原归档SHA`a8ae24c997cb89339c18a10107fd4ad607eac4d530c0b85cab52513d371fbe3e`。准备run：`/home/Weican_Chen/projects/pbit-pdnn20-task-accuracy-issue151/runs/preparation_ecd941851056_20261023T134441Z`。20份权重均尚未提供，记录awaiting_external_inputs／gpu_allowed=false，无PREFLIGHT_READY，无20层GPU作业。原件SHA回读已核，见本目录preparation/VERIFICATION.json。

评分器严格支持精确20层拓扑；22项CPU机制测试通过（18旧2/4层回归＋4新20层），包括真实tiny checkpoint strict安装、独立prefix评分oracle、全24层执行覆盖、RNG重放与选项映射。此处tiny／CPU检查不是实际20层Qwen推理。

正式入口：`experiments/pdnn20_task_accuracy_20261023/README_ZH.md`、`config.json`、`runner.py`、`prepare.sbatch`、`evaluate.sbatch`。CPU inspect-only只生成PREPARATION_ONLY，缺权重或参考BF16未齐时列waiting；严格CPU全部通过才PREFLIGHT_READY，真实GPU六项smoke才SMOKE_READY；9个完整候选结果后才可summarize。

复用145的同SHA三项parquet、tokenized requests及三项新完整BF16，沿用官方lm_eval0.4.8、0-shot、PIQA1838、ARC-Easy2376、固定HellaSwag1000/10042；acc/acc_norm，三seed，batch上限16，无padding／截断。原件／逐题指标／ID／模型及harness provenance必须匹配，不以旧历史表数字替代。

## 服务器与命令

仅操作本人`Weican_Chen@10.129.164.156:21570`、canonical home `/home/Weican_Chen`。新任务root：

```text
/home/Weican_Chen/projects/pbit-pdnn20-task-accuracy-issue151
```

共享旧模型／环境／数据均只读：

```text
Python: /home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/env-eval-v4/bin/python
Model: /home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/models/Qwen2.5-0.5B
Task data: /home/Weican_Chen/projects/pbit-pdnn-task-accuracy-issue145/data
Reference run: /home/Weican_Chen/projects/pbit-pdnn-task-accuracy-issue145/runs/f4eb25e53834_20261023T124307Z
Expected receiver: <new root>/checkpoints/joint20/
```

收到权重后，先核实用户／home／属主／symlink规范路径，将**原始20份**放到本人接收目录。文件SHA不匹配时保留实际文件并报告版本，不改期望值来绕过。所有Torch／模型／hash扫描计算经Slurm CPU allocation；CPU明确隐藏CUDA，临时文件与缓存留新root。

本轮已核验快照的严格预检命令（收到原权重后，用全新run；不要覆盖准备run）：

```bash
export PDNN20_PROJECT=/home/Weican_Chen/projects/pbit-pdnn20-task-accuracy-issue151
export PDNN20_SNAPSHOT="$PDNN20_PROJECT/snapshots/ecd9418510565d76585aee71a4c5675dbcbd61e9"
export PDNN20_COMMIT=ecd9418510565d76585aee71a4c5675dbcbd61e9
export PDNN20_RUN="$PDNN20_PROJECT/runs/joint20_$(date -u +%Y%m%dT%H%M%SZ)"
export PDNN20_CHECKPOINT_DIR="$PDNN20_PROJECT/checkpoints/joint20"
export PDNN20_INSPECT_ONLY=0
test "$(id -un)" = Weican_Chen
test "$(realpath "$PDNN20_PROJECT")" = /home/Weican_Chen/projects/pbit-pdnn20-task-accuracy-issue151
test "$(stat -c %U "$PDNN20_PROJECT")" = Weican_Chen
case "$(realpath -m "$PDNN20_RUN")" in "$PDNN20_PROJECT"/runs/*) ;; *) exit 31 ;; esac
test ! -e "$PDNN20_RUN"
mkdir "$PDNN20_RUN"
/opt/slurm/21.08.8/bin/sbatch --export=ALL --chdir="$PDNN20_SNAPSHOT" --output="$PDNN20_RUN/cpu-%j.out" --error="$PDNN20_RUN/cpu-%j.err" "$PDNN20_SNAPSHOT/experiments/pdnn20_task_accuracy_20261023/prepare.sbatch"
```

严格CPU预检成功之后，重新检查三个配置服务器的本人相关队列，遵守项目最多一个pending/running GPU。145作业2835未终止前不提交20层GPU。确认无冲突，再提交`evaluate.sbatch`，其内部先smoke、再run、最后summarize。用绝对Slurm路径，保留第一个终态／ExitCode／allocation，失败不自动回放提交或覆盖partial。

## 待办

- 等用户获取20份真实权重与交接来源；核验原字节及CPU strict state。
- 145三个完整新BF16本轮已验证；正式运行前仍重新核对其冻结原件SHA，不重复其任务、不改其进度。
- 权重齐备后新run正式CPU→GPU smoke→9case→独立核验与结果PR。
- 准备阶段CPU inspect-only实际回执已归档；PR远端核验以PUBLICATION.json为准。看板沿同日已验证的read:project不足待有权限者同步。Issue保持开放，不自动合并。

# Issue145 两层／四层 P-DNN 21项完整准确率已交付（2026-10-23）

负责人amlink1219，task/145-pdnn-task-accuracy，PR149。RTX5090单GPU2835 COMPLETED/0:0；CPU2834、18机制检查、9真实GPU smoke与21正式case全部通过，源f4eb25e53834e06220cbfad670ae03195eba8706。完整结果qwen/results/pdnn_task_accuracy_20261023/README_ZH.md与complete_21/，默认21case独立原件／SHA／固定题ID／24层执行／指标聚合审计通过。两层为现存joint4的10/12子集，非历史6/12；四层10..13，现存SHA不同于旧公开joint4，不继承旧PPL。无训练、W8或PPA结论。

任务分支已准备完整结果，通过同一PR149上传、待审、未合并，不自动关闭Issue。最终远端核验以本任务PUBLICATION.json为准；Projects现场缺read:project，未同步看板。旧失败2833与初始1/21快照保留，Issue116/123仍暂停。没有本任务运行中的GPU作业；不得重复提交21case。


完整统计见正式结果；下方保留执行中的历史记录，不当作当前运行状态。

---

# Issue145 接续记录

## 本次有限后台收尾

本机一次性进程只跟踪Slurm2835，不是周期自动化。源与输入receipt SHA固定；要求PR149仍开放且未合并、固定目标repo/head/base；21case默认完整独立审计通过后才归档、提交、上传同一PR及精确更新本任务验收项。任一输入/helper变更、任务HEAD改变、脏工作区、失败终态、缺case或SHA失败都会停止，保存阶段回执并尝试在Issue145报告；不重提GPU，不创建替代PR，不自动合并／关闭。

该进程未来将写pa145；其他任务应使用独立目录。是否已实际启动以本机`outputs/pdnn_accuracy_20261023/WORKER_STARTED.json`为准，成功／阻塞分别看`WORKER_COMPLETED.json`／`WORKER_BLOCKED.json`与worker stdout/stderr。恢复先查这些文件和PR149，再决定接手；不启动第二份收尾进程。不得根据本记录中的历史1/21或4/21推断当前远端作业状态。

最近本地独立核验4/21：两层10/12 PIQA三seed acc68.662±0.094%、acc_norm68.317±0.354%；较新BF16低1.850／1.650个百分点。快照见正式results下`piqa_two_layer_three_seeds/`，四层和其余任务仍运行。

负责人 amlink1219；任务分支 `task/145-pdnn-task-accuracy`；本机独立工作树 `workspace_projects/pa145`；base `6966739a5223680888bf0315f7bb4f73423a1ae6`。目标 PR base `pbit-tlm-attention-details-20261016`，不自动合并。

## 已确认

- 实际GPU运行中：Slurm2835、RTX5090、CUDA_VISIBLE_DEVICES=7；源码`f4eb25e53834e06220cbfad670ae03195eba8706`，结果root `/home/Weican_Chen/projects/pbit-pdnn-task-accuracy-issue145/runs/f4eb25e53834_20261023T124307Z`。CPU2834 COMPLETED/0:0；真实GPU9/9 smoke通过。首个完整BF16 PIQA1838 acc70.511425%、acc_norm69.967356%；独立审计已通过，当前1/21不是最终比较。
- [草稿PR149](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/149)已创建，未合并。执行源之后新增的本地`summarize.py`是独立审计工具，不冒充GPU执行源码；按TASK_DATA记录commit读取冻结Git blobs核验。
- 失败保留：旧源db2090d4、CPU2832成功、GPU2833 FAILED/1:0，runner回调错读不存在的进度字段，未生成完整case。已修后在全新f4eb25e源快照／run重跑，原快照／partial原件留服务器，日志及终态见本目录failed_attempt1。
- 用户首轮选两层／四层 decoder FFN，不训练新模型。
- 新评分器及18项CPU机制测试已完成。独立复核未发现标签泄漏／KV隔离／全局RNG阻断；真实Qwen smoke现已通过。
- Slurm2826 CPU-only checkpoint检查COMPLETED/0:0。本人服务器现存reference_1000层10/11/12/13 checkpoint，可严格按原896→4864→896双投影加载；精确字节身份见正式配置。
- 两层为10/12子集，四层为10..13；它们不继承旧6/12及旧joint4报告的PPL。现存文件SHA与旧公开joint4不同，尚不认定为同一权重。
- 本人env-eval-v4已有lm_eval0.4.8、transformers4.45.2、torch2.7.1+cu128；三项本人parquet数据SHA与Issue59协议一致。没有安装或修改旧环境／数据。

## 执行路径

服务器：`Weican_Chen@10.129.164.156:21570`，规范home `/home/Weican_Chen`。

个人任务root：`/home/Weican_Chen/projects/pbit-pdnn-task-accuracy-issue145`。只在此新root写入快照、输入副本、缓存、日志和结果。原模型、checkpoint、数据和环境只读。Slurm绝对路径 `/opt/slurm/21.08.8/bin/`，partition `gpu5090`、job-name `cwc`，最多单GPU任务；提交前重查三个配置服务器的相关队列。

解释器：`/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/env-eval-v4/bin/python`。

先提交源并生成逐文件SHA的最小不可变快照，包含新experiment、原pdnn_ffn算子及原task_data；CPU-only `prepare.sbatch`运行测试、copy/核验输入、严格checkpoint加载、tokenization。通过后`evaluate.sbatch`先真实模型smoke（BF16独立cached oracle，三架构重放／choice置换），再21case。每题证据实时保存；不覆盖已执行case。

## 当前未完成／待同步

全量21case仍在运行。不得重提任务、修改f4eb25e服务器快照、覆盖run或partial；监控已保存的2835作业身份。终态出现立即保存scontrol状态／ExitCode／allocation与日志。取回已完成case原件以及tokenized固定请求到本地审计目录，逐SHA验证（Git归档排除tokenized和parquet）；运行独立汇总器，默认必须21case齐备：

```text
python -X utf8 -P experiments/pdnn_task_accuracy_20261023/summarize.py --results <原件根> --output <新审计目录> --source-root <本工作树>
```

服务器已逐题执行官方process_results并回读复核；本地汇总器验证原件／ID／候选长度／finite分数／二值指标／24层执行和数值聚合，不能写成在本地重跑官方标签计分。完成后生成按任务的三seed均值／标准差／相对BF16百分点差，更新本记录、STATUS和Issue145，并将同一PR149补齐且转为可审。大权重和数据不提交Git。看板权限仍需实际核对，有权限才同步。

此任务不恢复已暂停Issue116/123，不接管其他Attention PPL或Qwen3任务。恢复时重新读Issue145、相关PR和当前集成入口，不能仅依赖本时点快照。

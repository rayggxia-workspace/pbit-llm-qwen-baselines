# Issue145 接续记录

负责人 amlink1219；任务分支 `task/145-pdnn-task-accuracy`；本机独立工作树 `workspace_projects/pa145`；base `6966739a5223680888bf0315f7bb4f73423a1ae6`。目标 PR base `pbit-tlm-attention-details-20261016`，不自动合并。

## 已确认

- 用户首轮选两层／四层 decoder FFN，不训练新模型。
- 新评分器及18项CPU机制测试已完成。独立复核未发现标签泄漏／KV隔离／全局RNG阻断；真实Qwen smoke尚待执行。
- Slurm2826 CPU-only checkpoint检查COMPLETED/0:0。本人服务器现存reference_1000层10/11/12/13 checkpoint，可严格按原896→4864→896双投影加载；精确字节身份见正式配置。
- 两层为10/12子集，四层为10..13；它们不继承旧6/12及旧joint4报告的PPL。现存文件SHA与旧公开joint4不同，尚不认定为同一权重。
- 本人env-eval-v4已有lm_eval0.4.8、transformers4.45.2、torch2.7.1+cu128；三项本人parquet数据SHA与Issue59协议一致。没有安装或修改旧环境／数据。

## 执行路径

服务器：`Weican_Chen@10.129.164.156:21570`，规范home `/home/Weican_Chen`。

个人任务root：`/home/Weican_Chen/projects/pbit-pdnn-task-accuracy-issue145`。只在此新root写入快照、输入副本、缓存、日志和结果。原模型、checkpoint、数据和环境只读。Slurm绝对路径 `/opt/slurm/21.08.8/bin/`，partition `gpu5090`、job-name `cwc`，最多单GPU任务；提交前重查三个配置服务器的相关队列。

解释器：`/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/env-eval-v4/bin/python`。

先提交源并生成逐文件SHA的最小不可变快照，包含新experiment、原pdnn_ffn算子及原task_data；CPU-only `prepare.sbatch`运行测试、copy/核验输入、严格checkpoint加载、tokenization。通过后`evaluate.sbatch`先真实模型smoke（BF16独立cached oracle，三架构重放／choice置换），再21case。每题证据实时保存；不覆盖已执行case。

## 当前未完成／待同步

CPU源快照预检、GPU smoke和全量准确率尚未执行，尚无新结果；代码尚未发布到PR。完成后取回小型结果／SHA，重新验算官方metrics，生成按任务的三seed均值／标准差／相对BF16百分点差，更新本记录、STATUS和Issue145，并推送任务PR。大权重和数据不提交Git。

此任务不恢复已暂停Issue116/123，不接管其他Attention PPL或Qwen3任务。恢复时重新读Issue145、相关PR和当前集成入口，不能仅依赖本时点快照。

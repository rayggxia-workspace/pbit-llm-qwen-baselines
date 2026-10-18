# Attention E0/E1：数字基线与有限时间采样微基准

负责人 `amlink1219`；[Issue35](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/35)，承接[Issue33计划](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/33)。独立分支 `task/35-attention-e01`，base `3553996bf014a29dee7fdb2250a3965e8fd881a4`。

当前阶段是本地实现与验证，服务器连接阻塞。没有远端作业ID、当次BF16参考或真实输入实验结果。最新状态以 `../../work/amlink1219/35/HANDOFF.md` 为准。

## 比较什么

| 输出契约 | 数字参考与对照 | 测量与解释 |
|---|---|---|
| 完整概率向量 | 稳定FP64数学参考；稳定FP32；BF16输出/FP32和；exp2分段线性数值模型 | TV、最大绝对误差、行和误差；exp使用log2(e)换底，保持原温度 |
| S个类别索引/计数 | 数字IID逆CDF、systematic单随机相位；串行随机扫描硬抑制Ising参考 | 实际频数、唯一V索引、有限样本TV；Ising尝试更新数与事件数；不把短样本直方图当精确概率输出 |
| 最终V输出 | 准确PV及online分块FP32融合参考；各采样方法的V选择/平均 | NMSE/相对误差；相同logits、相同V、相同M/S；online归一化含运行max变化时的重缩放 |

这是常规数字算法和有限时间采样的**软件数值实验**。分段线性方法尚不是指定库、字长和流水线的RTL实现。CPU/GPU时间不是ASIC延迟；没有面积、功率、能量或物理p-bit优势的实测。既有Ising函数的几何事件压缩只跳过软件中的空更新，账本仍记录所有逻辑尝试更新。

## 本次有限范围

先12个微基准pilot；通过后，默认full为465项：60项数字数值对照，加405项采样。M=64/512/2048，S=32/128/512，seed=0/1/2。profile为uniform、peaked和固定3个真实layer/head行。它们是本轮实现的明确矩阵，不表示Issue33的623行总计划已经执行。

真实捕获使用未修改Qwen2.5-0.5B Base BF16+SDPA；固定test起点0、2048token的**prefill最后一个查询**。保存layer0/12/23、head0/13共6行，微基准预先选择行0/3/5，即layer0/head0、layer12/head13、layer23/head13，覆盖两个KV组。M较小时截取对应logits和V前M个候选并重新归一化。这是固定子候选分布微基准，不是已校准的QK筛选器，也不是整体模型质量结论。所选行有限，不代表完整WT2或全部头的统计覆盖。

捕获时保留实际SDPA参数/调用，要求带捕获和不带捕获的模型输出logits逐bit相同。post-RoPE QK额外以FP32计算，仅为离线微基准输入；不能把此捕获开销算成部署后的稀疏QK数据流。V是BF16源转换到FP32的原始值；NPZ留个人服务器，不上传Git。

全模型部分仅重跑**未修改BF16**完整WT2：window2048/stride1024、299078tokens/299077targets、参考PPL11.652735047455899。本轮不做完整随机Attention替换PPL、不训练，也不改变FFN。原始基线 `../../baselines/common.py` 和 `../../baselines/perplexity.py` 不修改。

## 输入身份与执行阶段

`expected_identity.json` 复用项目已公开的Issue30/32哈希记录。模型权重、tokenizer、原始test及完整token序列分别核验。登记的709字节服务器config与681字节原始upstream config各有独立SHA；不能覆盖其中任何一个来“修复”哈希。verifier同时检查模型语义形状，不把某个config字节版本冒称官方原件。训练数据不参与本次实验，其历史SHA只作索引。

服务器当前授权账户/home是 `Weican_Chen`、`/home/Weican_Chen`；每次写入和提交前实时核验。仓库历史记录里的其他用户环境/模型路径不构成本任务的读写授权。`run_config.template.json` 故意为 `ready=false`，路径尚未现场确认，不能直接提交。

1. 连接恢复后，先只读核验身份/home、节点角色、Slurm分区、本人队列、本人目录下可用环境和输入；不要读取他人私有目录。缺个人环境或模型时先记录，再通过CPU Slurm staging任务准备，不能在登录节点大规模下载/安装。
2. 本地提交所有执行源，生成source manifest和不可变快照；上传前核对目标个人目录，不覆盖历史快照。核验LF、SHA并 `bash -n experiments/attention_e01/run.sbatch`。
3. 个人Python轻量调用 `prepare_inputs.py --model ABS_MODEL --text ABS_TEST --output NEW_MANIFEST`，将已固定SHA绑定到现场确认的个人路径；大文件哈希仍在计算节点完成。将review后的run配置设为ready=true，记录其SHA。
4. 原子检查本人无GPU任务后，提交**一个** `baseline_capture` GPU作业（gpu5090、gres gpu:1、4CPU、16GiB、45分钟上限）。内部先输入核验/单测、128token BF16及短捕获，再完整BF16和2048token真实捕获，任何门槛失败即停。
5. GPU完成后记录调度终态/退出码，核对stage_summary与制品SHA。将trace路径/SHA和capture_report写入一份新配置，然后CPU作业 `micro_pilot`，显式CUDA_VISIBLE_DEVICES空字符串。CPU作业不请求GPU。
6. 12-case pilot通过后再独立提交CPU `micro_full`。单case120秒超时；增量JSONL及时flush，保留失败；已有结果目录拒绝覆盖。没有通过的pilot时full拒绝启动。
7. 回收小型结果、制品哈希和日志；原始trace、完整每case数组留授权个人存储。用任务分支/PR发布，回读远端；无push权限时只同步本人Issue并保留待推送文件。

`run.sbatch` 需要显式环境变量E01_PYTHON、E01_CONFIG、E01_SOURCE_MANIFEST、E01_SOURCE_COMMIT、E01_SOURCE_ROOT、E01_STAGE。GPU仅由 `sbatch --gres=gpu:1` 分配；CPU阶段不加gres。Slurm命令绝对目录 `/opt/slurm/21.08.8/bin/`。提交前需使用个人根内的锁保护“查本人GPU队列→提交”，保存submission intent、job ID，超时后先查已有任务，不能盲目重交。

本地测试（已安装的NumPy即可，不需要Torch；捕获测试只验证可在本地验证的合同和保护）：

```text
python -m unittest discover -s experiments/attention_e01 -p "test_*.py" -v
```

这些测试不等于GPU捕获通过。实际输出逐项保存源提交/文件SHA、配置SHA、输入SHA、job/allocation、环境、命令、耗时和结果SHA。短链相关诊断不证明稳态；uniform在M>S时经验TV很大是有限样本现象，需要同S的IID对照。有效样本数按类别指示/实际V投影诊断，不用类别编号的自相关代替。本轮S最大512，低于ESS最小诊断阈值1024，因此正式输出会标记insufficient_samples；长期混合/ESS验证属于后续E1c，不能从本轮短链得到。

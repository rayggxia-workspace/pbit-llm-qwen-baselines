# Qwen3 Base 原始BF16完整WT2基线

Issue136 / PR137，负责人jieruiz，2026-10-23。两个真实模型的基线已运行完成并通过本地归档核验；PR待审，不代表已合并。FFN/Attention均未修改，没有随机计算、训练、RTL或PPA实验。

| 模型 | 完整WT2 PPL | mean NLL | 目标token | 窗口数 | GPU评测秒 | 峰值allocated GiB | 峰值reserved GiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen3-1.7B-Base | 8.3673395166 | 2.1243359745 | 299077 | 292 | 16.9192 | 6.1106 | 6.2988 |
| Qwen3-4B-Base | 7.0386116013 | 1.9514109350 | 299077 | 292 | 32.9219 | 10.4506 | 10.7246 |

GPU均为RTX5090，PyTorch2.7.1+cu128、Transformers4.51.3。原始BF16参数/算术，原生FP32归一化/RoPE与FP32交叉熵；SDPA，batch1，window2048/stride1024，seed0，无chat模板、附加BOS、KV cache或文本截断。计时含同步的评测阶段，不含下载、模型加载及排队；显存数为PyTorch allocator统计，不是整卡或硬件PPA。

两个模型均得到299078个语料token，同一int64-LE token序列SHA：`8d41d21825bb0e103dc63337727daf4b51c631cacec5937f014b119ae209081e`。位置1..299077各计分一次。PPL由逐窗口NLL总和/目标数后exp计算；不是窗口PPL平均。1.7B NLL总和635340.0302581787，4B为583622.1282043457。

## 版本和可恢复原件

- 官方模型：Qwen/Qwen3-1.7B-Base @ea980cb0a6c2ae4b936e82123acc929f1cec04c1；Qwen/Qwen3-4B-Base @906bfd4b4dc7f14ee4320094d8b41684abff8539。
- 镜像：hf-mirror.com。权重留服务器个人项目，不上传Git；模型配置/分词器/权重逐文件SHA、大小及LFS/Git元数据在prepared目录的两个清单中。
- 执行源码：968046f9346258029192983000b4def643667cca，配置SHA79a3b2224ecfae04b14381049092ba39a8c5e6e7a94abbe21055e0359a12506c。原始源码8文件SHA随每个result记录，全部与Git该提交原字节一致。
- 服务器ROOT：`/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136`。权重ROOT/models，冻结代码ROOT/snapshots/968046f，清单ROOT/prepared，结果ROOT/results，日志ROOT/logs。
- train/test raw：沿原服务器WT2，SHA分别为6707892fa3788b5ab9ed78ab5ff37d9fe825f6011a2ad4fcd6a6d467f0e7da57、173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08；train仅校验不训练。
- 本目录results、prepared、logs为原字节小型归档，11文件SHA由SERVER_SHA256SUMS.txt固定。源包及执行命令见work/jieruiz/136/HANDOFF.md、JOBS.json与RECOVERY_20261023.json。

## 执行与负面记录

CPU2797通过2组覆盖检查和原生tiny Qwen3前向/保存重载、完成1.7B下载校验，随后4B镜像连接被关闭而FAILED/1:0；GPU2798由于依赖失败取消、未运行。失败日志保留，不能将其写成健康作业。

恢复不改源码：CPU2799仅重试4B下载（有最多3次有限网络重试），最终10文件校验通过；GPU2800_0运行1.7B，GPU2801_1依赖2799运行4B，两者均输出COMPLETE和完整结果。1.7B结果文件时间19:19、4B19:43 CST。Slurm accounting被禁用，最终查询时scontrol已清理完成job，故不伪造sacct完成回执；证据是冻结源码、准备清单、完整窗口日志、COMPLETE及结果SHA。

CPU tiny模型默认配置曾出现Transformers的sliding-window警告；两个真实模型清单均use_sliding_window=false、sliding_window=null，未启用滑窗Attention。评测语料的滑动窗口协议与该模型特性是两件事。

## 核验

运行 `python qwen3/validate_baseline_results.py`：11个服务器原文件SHA、两模型revision/config/data/源码绑定、完整目标覆盖及NLL/PPL重算全部通过；10个内存损坏用例（重叠计分、计数、NLL、PPL、窗口边界各2模型）均被拒绝。VALIDATION.json保留回执。此为存储结果独立审计，不是第二次GPU推理。原计分测试 `python qwen3/baselines/test_baseline.py` 2组通过。

未来候选应使用各自匹配的此基线、同模型revision/分词器/文本/精度/窗口协议，至少3独立采样seed。不要用模型间PPL差当作随机替换收益；本阶段没有新随机方案质量结论。

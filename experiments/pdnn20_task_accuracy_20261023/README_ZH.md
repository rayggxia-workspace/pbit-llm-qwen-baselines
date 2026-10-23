# 20层 P-DNN 的代表任务准确率准备

Issue151，负责人amlink1219。用户确认权重应在师弟处，由用户联系获取；本轮交付其余准备，**尚未执行真实20层模型推理，也没有新的20层准确率**。依赖Issue145 / PR149的已发布评分协议；独立分支`task/151-pdnn20-task-accuracy`、本机`workspace_projects/pa20`，PR base为`task/145-pdnn-task-accuracy`。运行中的145作业、工作树和收尾进程保持独立。

服务器准备检查已完成：CPU-only Slurm2862 COMPLETED/0:0，22项评分机制＋6项流程检查全部通过；模型／tokenizer／三项数据／固定请求／harness源及145三个完整新BF16均已匹配。执行源码`ecd9418510565d76585aee71a4c5675dbcbd61e9`。当前唯一外部输入为20份待交接权重，记录状态`awaiting_external_inputs`、`gpu_allowed=false`；未生成PREFLIGHT_READY，未提交20层GPU。原件与终态见任务HANDOFF／preparation目录。

## 模型与评测范围

固定原串联bipolar FullPath P-DNN v1的20层联合训练step1000，替换decoder FFN的`[1,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22]`，保留`[0,2,3,23]`。每层为896→4864→896双投影；入口／隐藏均为±1，权重、读出、残差保持连续BF16。每次平均N=4条完整路径，Attention仍为原SDPA。该模型不是20层独立训练student直接叠加，也不是0/1可学习编码版本；不重训。

| 任务 | 数据范围 | 候选模型 |
|---|---|---|
| PIQA | validation完整1838题 | 20层，seed0/1/2 |
| ARC-Easy | test完整2376题 | 20层，seed0/1/2 |
| HellaSwag | validation预先固定1000/10042题 | 20层，seed0/1/2 |

共9个候选完整case；复用Issue145相同模型／tokenizer／数据／batch／官方计分的3个新BF16完整基线，必须核对其SHA、题目数和逐题覆盖，不使用旧历史近似数字替代。保留lm_eval0.4.8官方prompt、`_encode_pair`及`process_results`，0-shot、无chat template；同时报告acc和按选项字符长度归一化的acc_norm。

## 已准备的接口

- `config.json`：固定层集合、N4、三seed、batch≤16、context2048与基模型权重SHA。
- `checkpoints.expected.json`、`SHA256SUMS.expected`：[20份原权重的交接清单](CHECKPOINT_REQUEST_ZH.md)。总697,875,430 bytes；文件SHA来自旧公开joint20报告，不用旧PPL充当本次质量结果。
- 共享`pdnn_score.py`：只扩展允许精确20层拓扑；采样、缓存和浮点算术保持原2/4层实现。22项CPU机制测试覆盖18旧回归、20层安装／全24层执行／独立评分oracle／RNG重放与选项置换。
- `runner.py preflight`：核对本人路径、模型／数据／参考基线／源码／配置／20份checkpoint。`--inspect-only`允许缺权重，**只生成PREPARATION_ONLY.json，不允许GPU**；正式预检全部通过才生成PREFLIGHT_READY.json。
- `runner.py smoke`：真实BF16每任务首题＋最长prompt的独立cached oracle，以及20层seed0同题的重放、选项置换和24层执行覆盖，共6个case，通过后生成SMOKE_READY.json。
- `runner.py run`：9个完整候选case；每题实时证据，完成case逐SHA核验后才能跳过，partial不覆盖。
- `runner.py summarize`：要求9case完整且三份参考BF16通过，生成逐任务三seed均值、样本标准差、相对BF16的百分点差及原件索引；不跨任务简单平均，不作硬件PPA结论。

## 收到权重后的执行顺序

1. 把20份原文件放入本人个人接收目录；不读取师弟的私有目录，不在未经授权的共享目录操作。传输或解包前先核实本人的canonical home、目标路径和属主。默认接收目录为`/home/Weican_Chen/projects/pbit-pdnn20-task-accuracy-issue151/checkpoints/joint20/`。
2. 在独立新run中通过CPU Slurm预检；缺文件、大小／SHA／payload层号／类型／训练步数／配置不符均停止，不更改文件名或期望SHA来绕过。
3. 确认Issue145三个完整新BF16均可核验。若仍在运行则等待；不重新启动其作业。
4. 检查主服务器及两个已配置fallback的本人相关任务。本项目最多一个pending/running GPU；现有2835还在运行时不提交20层GPU，也不取消它。未来选择fallback时按skill披露并另核环境。
5. 在本人Slurm分配的单GPU上先smoke、再9case、最后summarize。取得原件、终态／ExitCode／allocation和SHA后通过任务PR交付。

具体脚本见`prepare.sbatch`与`evaluate.sbatch`，运行变量见[HANDOFF](../../work/amlink1219/151/HANDOFF.md)。模型、数据、tokenized prompt和长原件保留本人服务器；Git只交付必要代码、配置、小型结果与索引。未提供权重与未完成真实smoke时，状态保持等待，不把准备完成写成模型评测完成。

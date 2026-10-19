# 三种短流分层FFN与实际Attention联合验证

Issue50，负责人jieruiz；分支task/50-joint-ffn-attention，PR依赖base为task/46-fixedw-multiscale@5518a0a。复用Issue48/PR49冻结源11f1d6eea2776e201f2021081f8b0fbae2cc455e，不接管amlink1219的原Attention扫描或Slurm2380。原代码按字节保存于upstream_attention，来源/制品SHA见UPSTREAM_MANIFEST.json。

## 被测路径

- FFN：B2/T32/K32、B4/T32/K32、B4/T16/K16。相同历史固定W8，全24层，prefill与decode都替换；g/up输入共享64路分层门限，连续FP32 SiLU(g)×u后z独立编码，输出转BF16。未训练。
- Attention：全部24层单token decode走max4摘要＋历史train校准sigmoid/Bernoulli筛块＋固定8块额度修补，候选精确QK，有限时间hard-onehot CTMC Ising，观测索引直接V gather/平均。
- Ising的burn16、spacing4保留，计分主路径不先计算Softmax目标再IID。V选择就是PV采样，不额外重复抽一次。理想硬互斥CTMC不是物理器件或有限抑制延迟电路实测。
- 固定8块最多512个有效候选，尾块可能较少。QKV、RoPE、KV cache、Wo、BF16残差保留；多token Attention prefill仍准确SDPA。

## 为什么改用cached计分

旧整窗2048/stride1024的FFN PPL程序每次q_len>1，会绕过decode-only Attention补丁；不能把它用于联合结果并仍称Attention已替换。

本任务先用与上游相同的32个linspace起点：每段prefill2047个token，然后128个被计分查询逐token执行，共4096目标，batch8。Attention与FFN各自独立hook核对每个被计分目标都经过24层，不允许只安装而不执行。所有对照使用同一位置和token SHA。

这是**固定后缀PPL，不是完整WT2**。原BF16完整299077目标/11.652735重新复现只作为环境/数据门禁；后缀损失应相对新匹配后缀BF16，不能与11.65直接相减。full接口采用同窗口目标覆盖的cached方案，每个计分query真走替换；它与整窗BF16排程不要求逐bit相同，必须另配匹配参考，并先看实际运行时间。

## 冻结的首批矩阵与门禁

CPU：全部38项冻结上游测试、10项联合集成测试及13项FFN核测试；未安装Torch应失败，不将skip当通过。GPU：核验模型/语料/源与原BF16完整参考，再跑8项短pilot。none和B4/T32各自原SDPA与同BF16 digital_sdpa wrapper的所有计分logits SHA必须一致；手写FP32 QK不是这个严格接入对照。

通过门禁并检查耗时后，提交34项匹配后缀：

| 对照 | 数量 |
|---|---:|
| 原FFN＋原Attention | 1 |
| 3种FFN＋原Attention，各3seed | 9 |
| 原FFN／3种FFN × 联合Attention S128/S512 × 3seed | 24 |

S128约为初始2K长度的1/16；S512是保守的较高采样预算，约1/4，不能冒充同稀疏率。S是本批固定参数；完整cached的上下文逐query变化，不能称全程恰为L/16。仅重做必要的S128/512 Attention-only匹配对照用于联合交互分析，不重复Issue48的S32..1024全曲线。seed固定0/1/2，无挑选。

若完整链表现不佳，预注册fallback为4种FFN状态（含none）×3seed的screen_iid S128：同筛选、候选准确Softmax、PV采样，用于定位有限Ising与筛选损失。不会把fallback冒称原Ising链。

## 随机性与复现

FFN的input/product generator与Attention selector/sampler彼此独立；复用历史种子域，S不进入Attention seed。相同batch/段顺序才能配对；改batch或协议需要单列。FFN在prefill也开启，因此KV不是由原FFN生成的“干净缓存”。

先在原模型上安装上游Attention controller，再替换FFN；自有guard在替换之后检查全部参数和6个冻结FFN权重buffers的对象/存储/version，可变统计/RNG排除。异常时恢复Attention和hooks。不得通过禁用上游install校验或修改原源码绕过guard。

模型/语料/源/配置/目标位置/输出SHA、逐段NLL、24层执行统计、实际候选比例/采样重复、GPU耗时与Slurm作业均记录。69等历史完整FFN结果保留原协议；联合项另放qwen/results/joint_stratified_attention_20261019。大原件、权重和运行校准制品留本人授权服务器；Git只发布代码/汇总/索引。无新PT/PPA/TLM能效结论。

## 完整cached确认

`run_full.py`/`run_full.sbatch`另冻结新提交，保留d61原后缀快照。重新校验模型/文本/冻结依赖及d61成功门禁的制品与原源码；不重复相同环境下刚完成的向量化BF16参考。先做16×2047和32×1023-token真实前缀的B4T32+S512显存试运行，两项成功才生成READY允许完整worker。此前Slurm2425在不属于完整计划的更大32×2047前缀pilot上显存不足，16×2047已通过（16.23GiB）；没有提交完整worker。实际完整计划首窗无prefill且batch1，其余正常prefill仅1023，所以修正pilot覆盖实际batch形状，原失败快照保留。

完整矩阵22项：1个新cached BF16、3种FFN单独各3seed、原FFN及3种FFN配S128 Ising各3seed。统一batch32、window2048/stride1024，292窗口、299077目标，每目标独立24层调用审计；首次长窗与尾窗也覆盖，12357次decode forward。S128固定，不是逐query固定L/16。前缀Attention仍为原SDPA，FFN前缀同样替换；与旧向量化或batch8后缀结果不混成同协议。未生成结果的任务仍标记运行中，不提前填值。

离线统计脚本`summarize_results.py`复核目标位置/模型/批形状和三seed齐全，再报告PPL算术平均、seed总体标准差及平均NLL。联合交互按每seed `Ljoint-Lffn-Lattention+Lbaseline`，避免相加PPL。小seed标准差不代表语料不确定性；CTMC相同seed的轨迹可能随logit/事件消耗改变，不能假定全部随机数逐位配对。

2026-10-19发布前复核：PR47已由并行会话合并bef83e54，PR52已改为集成分支pbit-tlm-attention-details-20261016；原始执行快照和基线5518a0a保留，不重新运行相同实验。主34项＋12诊断见qwen/results/joint_stratified_attention_20261019/RESULTS_ZH.md；完整22项Slurm2430仍运行。

## Ising观测次数扫描（同Issue50）

用户要求目前只测PPL。固定B4T32/K32、筛选8块、burn16/spacing4，`run_samples.py`新增S32/64/256/1024各3seed及筛选后准确PV三seed（15项）。已有S128/S512、FFN-only、BF16均从原d61的同batch8/4096目标结果复用，不重算；原FFN六档曲线来自成员Issue48/PR49已公开原件。新的prepare先复核模型/数据/旧源、再重跑完全不改的同目标后缀BF16门禁10.37155678462956，成功才生成READY。

S是每个head/query保留的CTMC观测数，观测时间为16+4k，k=1..S；不是硬件时钟拍或有效独立样本数。只改变S，候选随真实模型hidden自然改变，不能冻结教师候选。通过后缀审阅后，完整phase仅新增B4T32的S256/S512各3seed（6项），匹配batch32/2048/1024，复用正在运行的53dd/Slurm2430的S128及BF16/FFN-only，不重提。worker核验原53dd实际显存门禁和数值内核源码一致；原执行快照不修改。

# Qwen3 概率架构：全部26项后缀先导已完成

2026-10-23 21:50 CST；Issue144/PR147，负责人jieruiz。Slurm2828/2829均已退出队列，两模型日志均PILOT_COMPLETE，带SHA sidecar的complete.json及13/13病例齐全。未取得历史sacct退出码，不以队列消失单独证明成功；以完成标记、全量原件及独立计分核验为依据。执行源码8c35145未修改，未补跑或重下载。

## 最终对照：同一4096目标后缀

每个随机方案为seed0/1/2的PPL算术均值±样本标准差（ddof=1）；标准差不是语料泛化误差或置信区间。BF16仅一次。Δ和相对变化均对本模型同目标cached BF16计算，PPL越低越好。

| 方案 | 1.7B PPL | ΔPPL / 相对变化 | 4B PPL | ΔPPL / 相对变化 |
|---|---:|---:|---:|---:|
| 原生BF16 | 7.590088 | — | 6.331575 | — |
| FFN-only | 7.666993 ± 0.008650 | +0.076905 / +1.0132% | 6.365253 ± 0.002990 | +0.033679 / +0.5319% |
| 筛选＋精确Softmax/PV＋FFN | 8.067234 ± 0.030143 | +0.477146 / +6.2864% | 6.676899 ± 0.014846 | +0.345324 / +5.4540% |
| 筛选＋校正拒绝128＋FFN | 8.249476 ± 0.027266 | +0.659388 / +8.6875% | 6.810810 ± 0.021287 | +0.479236 / +7.5690% |
| 筛选＋赢家1024＋FFN | 8.091915 ± 0.010626 | +0.501827 / +6.6116% | 6.700177 ± 0.012948 | +0.368602 / +5.8217% |

FFN-only迁移在本先导中损失较小。加入筛选但保留精确Softmax/PV后，相对FFN-only平均PPL再增加0.400241/0.311646；这表明本配置下筛选路径是主要质量损失来源。赢家1024相对筛选精确对照再增加0.024681/0.023278；拒绝128再增加0.182242/0.133911。这些是方案差值，非严格误差可加分解：上游激活/缓存随方案变化。赢家结果更接近筛选对照，但1024次相关链更新与128个接受样本不等成本，也不是同有效独立样本数；不能宣布算法等预算更优。

## 实际架构与参数

- 保留Base预训练权重，不训练模型；1.7B revision ea980cb0a6c2ae4b936e82123acc929f1cec04c1，28层、H2048、FFN6144、Q16/KV8；4B revision 906bfd4b4dc7f14ee4320094d8b41684abff8539，36层、H2560、FFN9728、Q32/KV8；head_dim均128。4B Q宽4096不等于hidden2560，适配器已通过非等宽测试。
- FFN：固定对称W8、64×64 tile；B4档A/A4/A16/A64；A8幅度q/256＋独立符号＋满幅旁路；T32/K32门限分层、64路和跨档共享，gate/up共享x，FP32 SiLU(g)×u，z独立重编码。x与z各T32，不是整FFN总32拍；不是逐通道独立Binomial或自然IID。
- QK筛选：64-token块，4个16-token均值取max4；free-block均值/std归一化，std floor=.01；强制首块与末两块；Bernoulli选择后按既定优先级修复到8块，保留尾块mask。每模型TRAIN16拟合＋16独立holdout、context2048，逐层逐Q头标量bias，temperature=1，拟合原始期望保留率.30；不是固定最终保留30%。
- 拒绝：128个接受样本，shift初始0、上限24、proposal cap factor128；无静默fallback。赢家：1024次更新/保留，argmax初始化、burn0、spacing1、shift0；相关保持链。两者直接读V均值，不再二次PV采样。
- QKV/Wo、QK-Norm→RoPE、GQA/cache、RMSNorm/残差/embedding/lm_head保留。FFN替换所有层prefill及decode；Attention仅所有计分单token decode替换，multi-token prefill仍原生SDPA。
- 理想FP32概率响应＋软件Philox数值参考，不是物理RNG、q/256硬件采样器、RTL/PPA或芯片加速验证。接口BF16，概率/FFN归约/CE为FP32，NLL累加FP64。

冻结结果args仍有legacy burn=16/spacing=4，仅为旧scorer默认字段，未被传入新采样kernel。实际调用与sampling_stats.sampler_parameters一致：winner burn0/spacing1。原始文件没有为修饰元数据而重写。

筛选后有效候选约占原始Q-head候选22.7563%（后缀上下文会增长且尾块未满），不应直接写作8/32=25%。按共享KV头合并Q-head选择的实际union约1.7B 32.77%、4B45.91%；不能把Q-head候选减少比例直接等同GQA内存流量减少或整机能耗收益。

## 逐seed与软件耗时

| 模型 / 方案 | seed0 PPL | seed1 PPL | seed2 PPL | 平均秒/配置 |
|---|---:|---:|---:|---:|
| 1.7B FFN | 7.674493459 | 7.668954618 | 7.657529959 | 155.89 |
| 1.7B screen-exact+FFN | 8.046793277 | 8.101852444 | 8.053056588 | 270.18 |
| 1.7B rejection128+FFN | 8.269766446 | 8.260180255 | 8.218481920 | 327.26 |
| 1.7B winner1024+FFN | 8.079963786 | 8.095488580 | 8.100293988 | 357.77 |
| 4B FFN | 6.368627866 | 6.362933265 | 6.364198303 | 203.88 |
| 4B screen-exact+FFN | 6.661737934 | 6.677550811 | 6.691408523 | 373.05 |
| 4B rejection128+FFN | 6.807865035 | 6.791149573 | 6.833416406 | 453.09 |
| 4B winner1024+FFN | 6.687485641 | 6.713367026 | 6.699678389 | 492.21 |

BF16后缀36.47/47.62秒。每模型单RTX5090，batch2，Torch2.7.1+cu128/Transformers4.51.3；逐项完整environment/command/峰值显存见原件。时间为GPU数值实现wall_seconds，不是硬件性能；首项JIT和运行波动会影响均值。

## 完整WT2预算（未提交）

若保持同一cached逐token评分方式、2048/1024、batch2，299077目标对应292段、150597次decode调用及297693 prefill token。本后缀是2048次decode、65504 prefill token。用实测decode×73.5337＋prefill×4.54465外推，单位GPU小时/seed：

| 方案 | 1.7B | 4B |
|---|---:|---:|
| matched cached BF16 | 0.72 | 0.91 |
| FFN-only | 3.00 | 3.76 |
| screen-exact+FFN | 5.34 | 7.22 |
| rejection128+FFN | 6.50 | 8.85 |
| winner1024+FFN | 7.13 | 9.65 |

完整复现全部26配置名义约156 GPU小时（1.7B66.6、4B89.4）。若两卡各固定负责一模型串行，名义约89.4小时/3.7天；给±30%规划余量约2.6–4.8天，不含排队、初始化和校准。这不是测量或统计置信区间：完整窗口平均上下文更短，首末batch1、编译缓存和负载会改变速度。不能用向量化完整BF16的16.5/32.2秒估算随机逐token评测。**本次未提交任何完整WT2候选作业**；需用户决定后续预算/范围。

## 证据与验证

最终原件[checkpoints/complete](checkpoints/complete/)共78文件：37个带SHA sidecar的JSON、3日志和SERVER_SHA256.json。服务器包ROOT/exports/complete-v1.tar.gz及本机tmp/qwen3-issue144-complete-v1.tar.gz，SHA256 a3d0df3f043d4a1fee23f9da547d585bcde0f28e9c325d665880fdd5c1a2ace3；没有权重。37 sidecar、77个清单文件原字节、27执行源blob、模型revision/准备manifest、原文/token/config/校准绑定均核验；26病例逐段NLL/PPL重算、所有4096目标×28/36层decode与FFN prefill覆盖通过。校验和用于完整性核对，不是数字签名认证。

validate_results --require-complete双模型COMPLETE；17语义篡改负例全部拒绝（含源commit/blob、模型/原文/校准绑定、prefill覆盖、真实burn/采样事件/筛选预算、缺末病例）；见[NEGATIVE_TESTS.json](NEGATIVE_TESTS.json)。汇总与预算可由`python -m qwen3.stochastic.summarize_final`重算，数值见[SUMMARY.json](SUMMARY.json)。后加审计脚本不属于8c35145执行源，不改运行行为。提交后用--git-blobs复核所有服务器原字节，远端回执见work/jieruiz/144/FINAL_PUBLICATION.json。

完整WT2 BF16锚点仍为8.3673395166/7.0386116013，299077目标/292窗口，原968046f源码重放NLL完全相同；不能与后缀PPL直接作增量。train SHA6707892fa3788b5ab9ed78ab5ff37d9fe825f6011a2ad4fcd6a6d467f0e7da57，test SHA173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08，299078 token序列SHA8d41d21825bb0e103dc63337727daf4b51c631cacec5937f014b119ae209081e。CPU/GPU tiny、两真实模型SDPA包装bitwise、kernel oracle/分布/仲裁/cap门槛已通过。PR交付待审，不合并、不关闭Issue；Projects缺read:project待有权限成员同步。

## 以下为20:33历史阶段记录（已由上方最终结果覆盖）

2026-10-23 20:33 CST；Issue144/PR147。CPU2827完成；GPU2828（1.7B）/2829（4B）运行。两模型FFN-only的三个种子已完成并独立验证，联合Attention仍未完成。

## FFN-only 首轮已验证结果（4096目标后缀，不是完整WT2）

| 模型 | 配对BF16 PPL | B4/T32/K32三seed平均±样本标准差 | ΔPPL | 相对增量 |
|---|---:|---:|---:|---:|
| Qwen3-1.7B-Base | 7.59008810 | 7.66699268 ± 0.00865026 | +0.07690458 | +1.01322% |
| Qwen3-4B-Base | 6.33157462 | 6.36525314 ± 0.00299026 | +0.03367853 | +0.53191% |

FFN替换覆盖28/36层prefill与全部4096单token计分query；Attention仍原生SDPA，没有筛选或采样。三个种子分别：1.7B为7.674493459/7.668954618/7.657529959；4B为6.368627866/6.362933265/6.364198303。每配置实测约155.6–156.5秒及203.1–205.1秒；这是GPU数值参考耗时，不能作为硬件加速/能耗结果。

检查点checkpoints/ffn，包SHA53d085047ee27025f2ef42bf04c2ee7c863ae5cb09dcd4eab733c3557af8ab63，38小文件含服务器SHA清单；17已签JSON、6随机配置及2配对BF16全部覆盖/逐段NLL/源码/模型/数据/配置/校准SHA核验通过。后缀初步显示FFN迁移损失较小，但不能据此宣布完整WT2或FFN+Attention联合质量达标。

## 基线和门槛

| 对照（均未替换） | 1.7B | 4B |
|---|---:|---:|
| 完整WT2原始BF16重放，299077目标 | 8.3673395166 | 7.0386116013 |
| 本轮配对cached BF16后缀，4096目标 | 7.5900880974 | 6.3315746169 |
| 后缀执行秒数 | 36.47 | 47.62 |

后续所有后缀增量必须减第二行，不能混用完整WT2行。每模型13配置：BF16一次，FFN-only、FFN+screen-exact、FFN+拒绝128、FFN+赢家1024各3seed。W8固定64×64、B4/T32/K32共享64 A8；QK max4/64-token块/8块、TRAIN16拟合+16holdout温度1标量校准；QK-Norm/GQA/原生缓存保留。完整架构和实际作用域见[参数说明](../../stochastic/README_ZH.md)。两个采样数不等成本，理想数值响应不是物理RNG/RTL/PPA验证。

实际门槛：CPU tiny非等Q投影、全层计分、codes无损压缩、保存重载/异常恢复通过；GPU tiny和两个真实模型的SDPA包装逐logits hash一致；固定采样核独立轨迹/分布/均匀仲裁/拒绝cap测试通过。完整BF16使用原968046f源码精确重放NLL，未放宽阈值。迁移执行源8c35145冻结，校准/配对结果均绑定源/model/data/config SHA。

归档：checkpoints/start包含收取时点26小文件；包SHA12e1110bedfc8bc1e390d10bc085f8d188c59e6aafdf1f88e88a604345224427。SERVER_SHA256.json保存原件校验；11 sidecar、27源码blob、模型/数据/配置绑定、完整4096目标覆盖与NLL重算通过。VALIDATION.json明确PARTIAL；独立验证器8类篡改负例通过（PPL/目标/执行覆盖/token/revision/config/protocol/校准SHA）。日志为进行中快照，不是终态。大权重仅保留原服务器目录。

完整候选WT2尚未提交，将先根据实际联合概率配置速度评估预算。当前没有Attention联合方案的最终PPL均值、标准差或替换增量。

元数据注意：冻结8c35145复用旧scorer的args仍含legacy `burn=16/spacing=4`，它们只用于旧CTMC接口验证，并未传入本轮新kernel。实际执行由adapter→kernels.sample确认：winner burn=0、每更新保留一次（spacing=1），rejection无burn；结果sampling_stats.sampler_parameters为实际参数。保留原字节不改这些历史字段，不据其将本轮重命名成CTMC。

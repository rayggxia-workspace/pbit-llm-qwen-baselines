# 给远程 Agent：Qwen3-4B 随机FFN训练执行交接

> **2026-10-24补充：Python容器与电路数制分开。** 可以用FP32模拟定点运算，但须显式保持目标舍入、饱和、比较及概率响应；宽整数还须检查宿主精度。TLM和功能模拟引用同一数值契约。暂时没有RTL可以用已定义的功能宏及有来源的条件PPA估计，不得以理想转换代替尚未定义的硬件行为。局部累加位宽不等于g/u接口位宽，详见 [NUMERIC_BOUNDARIES_ZH.md](NUMERIC_BOUNDARIES_ZH.md)。


> **2026-10-24 硬件边界更正，优先于旧版清单。** 旧版把FP32 g/u、SiLU及乘积列为训练前向，这不符合目标电路。它现在只作高精度诊断参考。部署训练必须先落实有限位宽恢复、g/u量化、随机非线性/乘积和尺度对齐；尚未实现，不能启动原57项部署验收扫描。GPU主权重、优化器和反向可保留浮点，前向必须显式执行硬件数值约束。详见 [HARDWARE_FORWARD_AUDIT_ZH.md](HARDWARE_FORWARD_AUDIT_ZH.md)。


**这是交给执行方的任务说明。目标是实现训练器、建立新基线、完成先导训练，再按扫描清单运行；不是再写一份研究综述。** 收到本文件后，先核对仓库和环境，按下方阶段推进。已有信息不必反复向用户询问；缺少数据权限或集群访问时，明确记录缺项，继续不受影响的实现和测试。

## 0. 已确定的任务，不要重新选模型或算法

| 项目 | 执行要求 |
|---|---|
| 模型 | **`Qwen/Qwen3-4B`**，非Base、非Instruct-2507；学生初始化与冻结教师用同一固定revision |
| 训练范围 | 完整36层模型联合训练；36个FFN全部替换，prefill/decode均生效；非FFN参数也允许更新 |
| FFN权重 | 每项实验统一选b=4、6或8，全部36层gate/up/down都用同一Wb，三个位宽各跑完整一套；**权重不随机化，也不冻结训练**，保留浮点主权重更新 |
| FFN输入 | x与SwiGLU输出z分别分组、分档、转概率并随机采样；64通道一组 |
| Attention | 首轮沿用原准确Attention算法，不加筛选/Ising/PV采样，以隔离FFN影响 |
| 算力 | 用户说明至少十张H200可用；实际Slurm分区、节点互联和个人路径由执行方核实 |
| 交付 | 代码、测试、非Base基线、先导训练结果、扫描进度、真实W4/W6/W8导出及可恢复交接；不能只交PPL数字 |

**当前已有的是设计和推理参考，没有本任务训练器、非Base训练结果或已提交的H200任务。** `scan.py`仅检查57项计划，不会训练或提交Slurm。PR147使用Base权重，其分数不能充当本任务基线；PR153的0.5B静态尺度表也不能移用。

## 1. 获取资料和建立独立任务

正式仓库：<https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines>。

| 入口 | 用途 |
|---|---|
| [Issue159](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/159) / [PR161](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/161) | 本交接、训练设计、扫描清单；先读最新评论，确认无人正在做相同实现 |
| PR147，提交 `357db5884726a66d988d75f92447ff8ecf8698e6` | Qwen3推理数值参考，**只读复用算子，不沿用Base运行配置** |
| PR153，提交 `c28549b7d19ad3fc1f0b8e961ac5c61ca4ddbfcc` | 静态编码和TRAIN校准方法参考，**不沿用0.5B模型/表/层数** |
| [Issue158 / PR160](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/160)，本次读取head `989546376f2295990b7712ea553615f0b8d88cb4` | 已有非Base模型准备与推理基线任务；先读其最新交接，复用权重manifest，避免重复健康作业 |

**已锁定目标revision：`1cfa9a7208912126459214e8b04321603b3df60c`。** PR160的2026-10-23 22:45北京时间交接记录CPU2869下载/预检、GPU2870等待依赖，尚无已发布新PPL；这是交接时点，不是本文件实时查询的队列状态。原执行SHA `e174d91cfcdb318da6481884bbf17ff37c1e3797` 不改。依赖方先读取 `work/jieruiz/158/HANDOFF.md` 和当前队列/封存结果，不重复提交。

已有存储入口为 `/home/Hongjie_Zeng/projects/pbit-qwen3-stochastic-nonbase-20261023-issue158/`：准备成功后的 `prepared/Qwen3-4B.json` 给出模型文件和token SHA，完整BF16在 `results/Qwen3-4B.json`，复跑在 `anchor/results/Qwen3-4B.json`。路径仅供有权限者读取；换H200环境仍需用相同权重/数据做当地BF16一致性验证，不要求复制全部历史实验或假定跨服务器路径可直接访问。

核实你自己的GitHub登录身份，读最新AGENTS、README、PROJECT_MEMORY、相关Issue/PR及本人STATUS。Issue159/PR161当前交付的是设计；若独立承担训练实现，建立关联Issue并注明负责人、范围、验收及与159的关系，在独立分支/工作目录执行。不要把自己默认为jieruiz，也不要覆盖设计作者分支或他人的Slurm任务。

以下为Linux新目录示例，目录名可按个人环境调整；已有合适checkout则复用，不重复克隆大权重。**这些git命令可执行，后文列出的训练模块是待实现接口。**

```bash
git clone --filter=blob:none --no-checkout \
  https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines.git pbit-qwen3-training
cd pbit-qwen3-training
git fetch origin refs/heads/task/159-hardware-forward-contract:refs/remotes/origin/hardware-plan-159
git fetch origin refs/pull/147/head:refs/remotes/origin/reference-147
git fetch origin refs/pull/153/head:refs/remotes/origin/reference-153
git fetch origin refs/pull/160/head:refs/remotes/origin/reference-160
git sparse-checkout init --cone
git sparse-checkout set qwen3/training/sc_qat_20261023 progress work
git switch --detach origin/hardware-plan-159
git rev-parse HEAD
# 阅读协作规则，认领/建立关联Issue，再用实际Issue编号创建自己的task分支。
python qwen3/training/sc_qat_20261023/scan.py
```

上面的稀疏范围可进一步收窄到本人progress/work；不检出历史大结果。记录实际计划提交SHA。两个参考提交存在于取回的历史中，应检查 `git cat-file -t <SHA>`；如果参考PR已改写导致缺失，取其固定提交或向维护者核对，不能悄悄换版本。

不必合并两个历史实验分支。用 `git show <SHA>:<path>` 阅读文件；若提取成oracle，记录原blob/SHA和必要的import修改。PR161自身没有PR147全部推理代码，不能仅下载本方案后假定import一定可用。

### 精确代码入口

| 固定版本中的路径 | 可以复用什么 | 必须改什么 |
|---|---|---|
| PR147 `qwen3/stochastic/vendor/core.py::quantize_int8` | 64×64 tile对称W8，[-127,127]，tile scale=maxabs/127 | 增加可训练主权重与STE；不要把quantized buffer当Parameter |
| PR147 `.../stratified_core.py::stratified_counts` | T/K门限分层、共享64路的联合计数分布 | 增加可重放随机键接口，保留共享协方差 |
| PR147 `.../stratified_core.py::encode_input`、`project_counts` | A8/full-one/符号、动态PoT、尺度恢复 | 动态原版档间距固定为4；泛化B、d，新增静态/学习尺度 |
| PR147 `.../stratified_core.py::StratifiedFFN` | gate/up共用x，z独立采样的正确边界 | 原类detach权重、只注册buffers，是推理oracle，不能直接训练 |
| PR147 `.../shared_counts.py`、`range_core.py` | stratified_core的相对导入依赖 | 与core一起提取；不要漏文件或替换为独立逐通道Binomial |
| PR153 `experiments/qwen_static_multiscale_20261023/static_core.py::encode_static` | 静态PoT表、截断、满幅旁路、输入不重排 | 原版只接受4档，并依赖历史sys.path链；训练版要泛化并整理本地import |
| PR153同目录 `run_static.py::prepare` | W8-only与动态采样学生传播路径的TRAIN校准思路 | 原脚本绑定0.5B/旧路径；只借方法，另写4B校准器 |

PR147的 `scorer.py` 含 `ModelGuard`、eval、inference_mode；这是冻结推理评估器，不是训练入口。不要解除guard后直接训练而遗漏权重/采样梯度问题。

另外，`qwen3/stochastic/calibrate.py` 校准的是Attention筛选偏置，**不是FFN幅度尺度**。完整PPL窗口/计分可参考PR160的 `qwen3/posttrained/baseline/support.py`、`evaluate.py`，按本环境manifest核验。PR153的静态测试在 `experiments/qwen_static_multiscale_20261023/test_static_core.py`；其历史导入链还涉及 `qwen_multiscale_stratified_20261019`、`qwen_dual_range_20261018` 和 `qwen_dual_iid_exact_20261018/vendor/frozen`。建议整理成新包的相对import并验证，不能只拷一个文件就假定依赖齐全。

## 2. 先把运行信息填全

复制本目录 `REMOTE_ENV.example.json` 为自己的运行配置，填写路径、准确版本和manifest SHA，禁止写token/密码。确认：

1. 按上面的Qwen/Qwen3-4B固定revision，核对权重、tokenizer、chat template逐文件SHA；有缓存就复用。教师始终冻结、eval/no_grad，学生由同一原件初始化。PR160的模型manifest未完成前，不能凭revision号宣称权重字节已验证。
2. 隔离Python/PyTorch/Transformers/CUDA环境及GPU/互联信息。Transformers应支持Qwen3；最终锁定实际通过测试的版本，不直接升级别人的环境。
3. 许可训练数据、TRAIN校准片段、独立validation及最终test的固定版本与SHA；评测集不得用于校准、尺度选择或蒸馏文本来源。
4. Slurm分区、H200申请方式、个人项目根目录、共享权重位置和checkpoint输出。无这些信息不能假报“任务已提交”。

**数据起点**：有效监督token约40%通用文本/代码/多语言、30%非思考指令/多轮、30%思考类数学/代码；这是工程默认，可根据可用许可数据调整并记录理由。对话只监督assistant目标，保留目标轮推理和最终答案。原始文本正常next-token计分。教师KL与CE使用同一mask、同一有效token分母。

审计实际chat-template渲染，不要以为传 `enable_thinking=False` 就自动修好训练样本。防止重复think前缀、把目标推理删掉、或4096截断后只剩思考没有答案。校准覆盖prompt prefill、普通回答和长推理decode。

## 3. 实现下列五块，不要先开57个大任务

正式新增实现建议放在 `qwen3/training/sc_qat/`；设计文件仍在本目录。下列名字是需要实现的模块契约，不表示已有代码。

| 模块 | 最小职责/输入输出 |
|---|---|
| `encoding.py` | 输入x或z与ScaleSpec，输出sign、bin_id、selected_scale、q、full_one及梯度代理；支持D/F/L/H、B、d |
| `sampling.py` | 输入A8概率、T、K、RandomKey，输出联合counts；显式比特流oracle、精确压缩实现、重放测试 |
| `trainable_ffn.py` | 从原MLP接收三组Parameter；Wb假量化（b=4/6/8）＋x共享采样→有限位宽g/u→已冻结契约的随机非线性/乘积→z独立采样→Wd；输出原接口dtype |
| `calibrate.py`、`train.py` | TRAIN-only尺度表、全模型CE＋KD训练、分布式/重算、可恢复checkpoint、统计日志 |
| `export_eval.py`与测试 | 导出真正Wb+固定表+配置，重载推理前向与评测；覆盖全36层prefill/decode |

### 3.1 更正后的部署前向要求（硬件契约尚待实现）

```text
x → 64通道组分档 → A8随机计数，gate/up共用同一份计数
  → Wg_b/Wu_b → 有限位宽计数/尺度对齐 → 量化g/u
  → 按硬件响应及独立性约束采样，实现g·sigmoid(g)·u → 有限位宽z
  → 独立的z分档与随机计数 → Wd_b → BF16输出 → 原残差
```

- 权重确定性Wb（b=4/6/8）；本轮无双随机、无OR近似、无新增FFN bias。
- 输入保留符号；概率普通码为q/256，q∈0…255；另有概率1旁路，q255不等于1。零组稳定输出0，不出现NaN。
- 每token/原通道组64路及跨档共用该拍门限。不同组/token/层/x或z阶段独立；gate/up只抽一次x。不同stratum的区内随机偏移应独立，不能只抽一个偏移复用所有stratum。
- B档为 `S/2^(d*i), i=0…B−1`；逐元素选最小可容纳档；超过S时截断；低于最低档仍用最低档。**不重排通道**。
- K=T：0…255分K区，每区随机抽一次；K=1：自然IID。K须整除256和T。分层不是自然IID；T256/K256是确定完整覆盖，不作为随机优势的证明。
- T_x和T_z是两个阶段预算；不能把整个FFN称为只花T拍。
- FP32/BF16旧路径仅作oracle，不作为部署学生前向。先填写HARDWARE_CONTRACT.example.json，验证有限位宽标量参考、逐拍参考与压缩后端一致，再做短训。不能只把张量cast到BF16就宣称非线性已量化。
- T_nonlinear、概率响应精度、流相关性和z重编码必须单列；原T_x/T_z预算不包含新增非线性采样。

**不需要保存T份巨大矩阵。** 固定W、精确累加下，可先保留每条输入的counts，再做一次GEMM；先正确恢复每个输入的符号/尺度。它仅在实数线性运算下等价。部署后端必须与相同随机序列的有限位宽逐拍参考核对，包括每个饱和、截断、移位和舍入边界；不能仅用FP32容差证明硬件等价。这不是将噪声改成独立高斯。

### 3.2 可训练参数与梯度

**位宽扩展严格只改权重量化精度。** 三组均按64×64 tile，`Qmax=2^(b−1)−1`，`scale=maxabs(W)/Qmax`；INT4码−7…7、INT6码−31…31、INT8码−127…127。全零tile保持0并按原规则防除零；round、对称截断、浮点主权重/STE规则相同。PR147只给W8 oracle，W4/W6需新增独立量化边界参考，不能把weight_bits配置字段改了但仍除127。

输入概率仍是A8 q/256，门限仍8位、共享64，绝不能随权重改成A4/A6。训练/数值参考可用int8容器保存W4/W6码，但结果必须分开记录逻辑位宽、容器位宽与实际packed字节；未经bit-pack不能声称实际存储缩为4/6位。W4/W6仍是固定权重，非权重随机流。


主权重用浮点Parameter：前向quantize/dequant得到对应Wb，反向用明确的STE。不能把带 `detach()` 的buffer直接交优化器。Attention/RMSNorm/embedding/lm_head保持正常数制且可训练；保留原模型tied embedding/lm_head关系。

尺度策略：D两处动态；F两处TRAIN校准后固定；L每组顶档log2尺度可学习、前向始终取整数指数；H固定x、动态z。F不能在推理时自动扩档；L最后20%训练冻结为整数指数继续适配。x有40组/层、z有152组/层，共6912组，不能硬编码旧模型24层/896宽。

静态表仅从TRAIN生成，x/z分别统计，每个位宽独立校准，至少包含该位宽Wb-only和目标动态采样学生传播路径。默认最大值向上取PoT、无额外headroom。离线表冻结后验证/测试只读。记录各档占比、裁剪比例/裁剪能量、零概率比例及selected_scale统计。

固定/动态尺度第一版：范围内单位STE，截断范围外0。L方案不要把尺度路径detach：可使用

```text
e_ST = a + stop(round(a) - a)
s = 2**(e_ST - d*bin_id)              # bin_id停止梯度，s仍可微
p = clamp(abs(x)/s, 0, 1)
p_q = p + stop(A8_probability(p) - p)
p_hat = p_q + stop(counts(A8_probability(p))/T - p_q)
x_hat = sign(x) * s * p_hat
```

这是**有偏代理梯度**，不是精确无偏随机梯度。合法指数上下界依据校准固定，监测触界；明确零点梯度与full-one处理。验证代理图梯度及优化更新，不要求它等于硬量化函数的有限差分导数。

**Checkpoint重算必须复现同一次噪声。** 每步新随机数，但同一前向重算用相同RandomKey，例如run_seed/optimizer_step/microbatch/rank/layer/signal/token-group及调用编号。不要只靠自建Generator被PyTorch自动保存；recompute不能推进调用计数。保存数据游标和随机状态；先在相同world size下验恢复，变更world size另定义协议。FFN噪声seed与生成解码seed分开。

## 4. 验证门槛与执行顺序

| 阶段 | 现在应做的工作 | 通过后才能做什么 |
|---|---|---|
| G0：环境/原模型 | 固定模型与数据SHA；非Base原生BF16完整WT2和短对话/双模式检查 | 校准、替换与训练 |
| G1：算子/梯度 | 小形状逐拍与压缩counts；边界/共享协方差；兼容配置对PR147 oracle；新B/d/静态另独立oracle；每层三投影梯度与optimizer更新 | 真实4B短训 |
| G2：4B先导 | 每个位宽的D32、F32、L32分别120步，使用下述独立短课程；重算开关、保存恢复、导出重载；检查36层覆盖及吞吐/显存 | 扩展扫描 |
| A：主扫描 | 3位宽×（16随机配置＋3训练控制）=57项，每组200M有效训练token | 从独立validation选动态/全静态候选 |
| B/C：结构/机制 | 各位宽分别B/d、x/z不同T、z额外档位、IID匹配训练 | 每个位宽最终2–4结构长训 |
| D：最终 | 每个位宽选2–4结构，每结构2B起，必要时5B；最终优选至少3训练seed；导出后完整评测 | 质量/成本结论与交付 |

任何阶段失败：保存配置/日志/异常张量摘要，修复后新执行快照；不覆盖旧结果、不修改运行中源码、不重复健康Slurm任务。单条配置失败不自动停止其他独立健康配置。G2实际用过的数据预算若要并入A，必须显式计累计token；默认A从原模型重新初始化。

**G2独立短课程：每配置120个优化step，先20步mean、20步T128、20步T64、60步目标T32；L在最后20步冻结尺度。** 这只用于烟测，不能机械套用A的200M-token日程，否则先导可能尚未进入目标T。必须验证目标T与冻结L阶段的loss/梯度/重载，才放行A；A仍从原模型初始化。三个位宽分别执行，不能由W8通过推断W4/W6通过。

G1最少覆盖：正/负/零、恰等尺度、q255与full-one、全部档位、T8/16/32/64和K1/K=T、不同分组、相同/不同随机键、all-zero权重tile。参数验证看各投影张量梯度范数和更新，不要求每个元素梯度非零。

### 首轮57项，按这个执行

| 策略 | x尺度 | z尺度 | T_x=T_z，K=T |
|---|---|---|---|
| D | 动态 | 动态 | 8、16、32、64 |
| F | 固定 | 固定 | 8、16、32、64 |
| L | 学习后固定 | 学习后固定 | 8、16、32、64 |
| H | 固定 | 动态 | 8、16、32、64 |

以上16种在INT4、INT6、INT8上各执行一遍，共48种随机训练。每个位宽分组再加同数据/预算的BF16微调、该位宽Wb-only QAT、固定B4/d2 A8编码mean QAT三个控制，共9控制、合计57项，计划工作量为原来的3倍。三份BF16控制的数值设置相同，是各分组配对重复，不能算三种位宽结构或三训练seed。统一B4、d2、组宽64；其余设置不变。mean指用编码概率均值代替采样，**不是整个非线性FFN的数学期望**。同时保存原始未训练BF16及各结构未训练随机结果，才能区分训练收益和编码收益。

初始优化设置：AdamW，FFN LR=1e−5、其他参数2.5e−6、L尺度1e−4；betas=(0.9,0.95)，weight_decay=.01（尺度为0），clip1；3% LR warmup＋cosine；损失CE＋0.5 KL(teacher||student)，温度1。总监督token/更新约131072，按有效mask计数。全局归一化必须考虑DDP/FSDP默认梯度平均，不能让不同rank有效token数量改变样本权重。

A阶段每个位宽前5%有效token使用对应Wb+A8编码mean；接着7.5% T128、7.5% T64；后80%目标T。分层K随T，IID对照始终K1。L最后20%冻结尺度。控制组无随机课程；同等数据/预算。数据顺序、训练seed与验证集在A阶段固定。

B阶段在每个位宽内分别从最佳动态与最佳全静态F/L各选一个，扫描B={2,4,8}×d={1,2,3}，每个位宽最多18组，总计最多54组；完全相同位宽/配置/预算可复用。继承选中的**结构**，不把A训练权重偷当新初始化。C也在各位宽内单项增加(8,16)/(16,32)/(32,64)采样预算、z8档、静态百分位；两优选结构至少各测自然IID T16/32/64，训练和推理随机律一致。

## 5. H200、Slurm与评测

先profile后排程：可用两组各4张H200训练、2张评测/数据生成；每训练组内部运行教师，避免跨组传大词表logits。实际显存允许时可改更多两卡任务。用FSDP/ZeRO与activation checkpoint；不是 `device_map="auto"` 推理切分。FP32 FFN oracle可能限制TensorCore收益，不能按H200峰值承诺时间。

先提交G0/G1/G2 Slurm，验收通过再提交A数组/独立作业；代码按Git SHA冻结到个人执行目录。作业记录step、有效监督token、各项loss、grad norm、学习率、尺度/噪声统计、tokens/s、峰值显存和checkpoint。保存last与必要best，不长期保留每步全模型副本；按项目共享存储约定保存大文件，Git只放manifest/摘要。

评测要求：

- 完整WT2 window2048/stride1024，对同轮非Base BF16；记录原文与token SHA、目标数量/NLL。不得借Base的PPL，不把4096目标后缀称完整。
- 中期：独立验证loss、PIQA/ARC-E和双模式样本；最终：补ARC-C/HellaSwag/WinoGrande、IFEval、GSM8K或MATH-500、代表性代码任务。固定版本/模板/解码参数/长度预算，报告各项变化。
- 生成评测的thinking/non-thinking分开；记录重复、截断、think结束和答案完整率。长推理需要足够输出预算；最终候选适当混入8K/16K训练和长上下文验证。
- 每最终checkpoint至少3推理seed，最终优选至少3训练seed；分别报告，不混淆。再测训练T→推理T8/16/32/64/128迁移表。
- 目标暂定相对PPL增加≤1%、代表任务平均下降≤1个百分点且无明显能力失效；不是已验证保证。超标也要如实报告，不只保留最好seed。

## 6. 对方需要回传什么

每个结果使用本目录 `RUN_RESULT.example.json` 的字段，null表示未测，不当0。完成时必须将placeholder标志设false，并填写实际命令、执行源码manifest与配置路径/SHA。BF16控制实际weight_bits填16，随机编码/替换字段为不适用；W-only也不填写虚构的输入采样。逐seed保存NLL、目标数、PPL、原件路径和SHA，不能用单个NLL代表三seed。大权重留在远程共享存储；回传路径、访问要求、文件大小和SHA-256。每次汇报先给一张表：

| case/执行SHA/权重位宽 | 尺度/B/d | T_x/T_z/K | 训练token/seed | WT2 PPL及相对BF16 | 代表任务变化 | 吞吐/显存 | 状态/输出位置 |
|---|---|---|---|---|---|---|---|
| 填实际配置 | 实际值 | 实际值 | 完成量 | 未测写未测 | 未测写未测 | 实测 | completed/running/failed/blocked |

**第一次回传应是：环境与模型manifest、实现PR、G0/G1报告、各位宽D32/F32/L32先导曲线与吞吐；G2通过后再附A阶段Slurm清单。** 首批未通过就报告问题和可执行修复，不等待整个大扫描结束。只有提交成功的回执才能填写job_id；只有验证封存结果才能标completed。

正式代码/结果按qwen3目录；个人进度维护 `progress/<你的GitHub用户名>/STATUS.md`，辅助资料 `work/<你的GitHub用户名>/<执行Issue>/`。交付任务分支和PR，写实际验证及未跑项；暂停时留下checkpoint、数据游标、随机状态、job_id与恢复命令。不要自动合并或关闭设计Issue159，不向GitHub上传凭据/工艺库/模型权重。

详细背景和来源见同目录 `TRAINING_PLAN_ZH.md`；参数列表见 `SCAN_MANIFEST.json`。**实施过程中若发现本交接和代码矛盾，先用独立oracle定位并记录差异，再修正新模块；不可为了通过测试静默改变采样定义。**

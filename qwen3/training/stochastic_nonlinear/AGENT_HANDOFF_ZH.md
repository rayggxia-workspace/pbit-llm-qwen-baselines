# 随机非线性 FFN 训练交接（Issue177，2026-10-24）

目标：接续昨天训练的 FFN 权重，把前向中的精确 SiLU×u 换成有限随机三路 AND，并继续只训练 gate/up/down 权重。昨天结果还未全部完成，当前未提供 checkpoint 路径、代码和训练回执。不要重交或取消昨天健康作业；本文件不声称已完成 Qwen3-4B 新训练。

## 1. 先用哪个版本

- 模型必须是后训练版 **Qwen/Qwen3-4B**，revision `1cfa9a7208912126459214e8b04321603b3df60c`；36 层、hidden=2560、intermediate=9728。不是 Qwen3-4B-Base。
- 本实现以 PR174 的三路 AND 推理代码 `b41ee00835b1ae385b2a7c3654df67df26eff3e3` 为依赖。新代码在 `qwen3/training/stochastic_nonlinear/`。不要拿旧冻结推理 wrapper 的 detached buffer 直接交给 optimizer。
- 先 **W8、x T=K=64、非线性 T=128**。第二条独立实验改非线性 T=64；32 暂留诊断。不要误把 T=128 写成输入矩阵也采样128次。
- W4/W6 的配置与量化代码仍可用；先验证 W8 的训练收益，再把 `weight_bits` 改为6/4分别重校准。各自是独立实验，不能沿用 W8 校准或结果。
- 当前不采用 FSM。固定 g 范围的小状态 FSM 在此前模型试测中失败，不能用函数 MAE 替代模型验证。

## 2. 实际前向和电路对应

| 阶段 | 本版做法 | 必须保留的边界说明 |
|---|---|---|
| x 编码 | 每64通道预存四个 PoT 尺度；每元素选最小可容纳档，幅度8位＋符号，概率1旁路 | 只选档，不做在线max；表来自TRAIN，训练期间固定 |
| Wg/Wu | 确定 W8（可4/6），每64×64 tile 对称量化；64路共享R8、T=K=64 | Wg/Wu共享同一x采样；权重不变成随机流 |
| g/u 接口 | 固定四档 `[S/2,S/8,S/32,S/128]`，幅度P8＋符号 | g和u的S独立，都是TRAIN固定值；最高档允许截断 |
| σ(g) | 用g实际尺度恢复的signed8驱动，步长1/8、范围[-16,15.875]，查冻结256项P8表 | 不是σ(g/S)；概率码0..256，256是端点，不能悄悄截成255 |
| 非线性 | g幅度流、σ(g)流、u幅度流三路AND，另行合并符号 | 32个联合单元=4×2×4，T128每单元4抽，T64每单元2抽 |
| Wd | AND事件直接驱动固定权重；相同事件共享给全部Wd输出；按尺度移位合并整数计数 | 不生成z均值再量化/重新采样；两路四档产生7个相对指数和，不是16个独立尺度 |
| 输出 | 16位恢复系数、int64容器内有界精确累加、整数RNE后转BF16 | 不是每一级都8位累加；位宽上界和输出正常数范围由oracle检查 |

**尚未完成定点化的边界：Wg/Wu 的计数与尺度恢复沿用 FP32 参考。** x/g/u由连续容器到码字的编码也由Python描述，尚无全链RTL对照。非线性核心及Wd遵守上述有限位规则，但不能将本代码命名为“完整硬件bittrue训练”。要完全封闭这处边界，下一项任务应把首级整数累计、系数、舍入接入，并重新验证；不能在TLM中把该FP32参考计算当作免费的电路。Attention、RMSNorm、残差、词表输出保持加载模型的正常做法。

Python 用联合计数的**精确分布压缩**避免展开巨大逐拍张量。它保持同一输入对Wd各输出的共同事件，也保持32联合单元的统计规律；没有把真实随机数替换成均值。压缩采样与逐拍比较器分布相同，但并不保证同seed逐位相同。更换随机源共享/相关性，需要重新定义和验证联合规律。

## 3. 反向怎么算

前向输出由硬路径给出；不使用“硬值＋软值－软值”这种可能损失低位的算术拼接。反向单独构图：

1. 权重码字、tile尺度、选档和移位标签当作固定；权重采用直通代理梯度。
2. x、g、u和signed8驱动在范围内用直通梯度，超过饱和范围的输入梯度为0。
3. Wd 权重梯度使用**该批真实采样的z**；向Wg/Wu传播使用量化条件均值的导数，其中sigmoid导数用FP32求值。
4. 这是有偏STE，不是随机离散运算的精确导数，也不是REINFORCE。反向浮点只用于离线训练，不属于部署前向。

只更新108个参数张量（36×gate/up/down）。master权重、梯度和Adam状态使用FP32，以免丢小更新；前向每次从master重新生成W4/6/8。尺度及LUT是buffer，不训练。Attention、embedding、norm和lm_head冻结；但仍要反传穿过冻结模块，以训练更早的FFN。

## 4. 接续昨天权重

先向原训练任务核对最终执行SHA、模型与tokenizer SHA、训练数据版本、checkpoint SHA和已训练参数范围。只得到“训练完成”的口头状态不够。

- 若得到完整本地HF目录，可直接作为 `model_dir`；必须保留原模型ID及后训练属性，并记录它是warm-start而不是原始BF16基线。
- 更推荐由原agent导出**平坦tensor字典**：精确名称 `model.layers.0.mlp.gate_proj.weight` 等，共108项；只含FFN三组权重。用 `torch.save(flat_dict, path)`，记录SHA，填入manifest的 `warm_ffn`。加载器严格核对完整键名/形状/有限值，保留FP32 master精度。
- 不猜测原有optimizer、LoRA键名或shard布局；由拥有原代码的agent导出/合并后再载入。
- 昨日FP32非线性checkpoint是**warm start**，不是本版已验收结果。若昨日还改了非FFN参数，必须用对应完整模型作父模型，不能只移植FFN而默认为相同模型。
- 重新用TRAIN校准x/g/u。旧x/z校准中的z不能充当g/u；不能把原始模型的g/u尺度默认为适合新权重。

## 5. 最小可运行入口

在已检出本分支及依赖源码的Git根目录运行。需要支持Qwen3的Transformers及PyTorch；不要修改正在执行的快照。正式数据是已经分词并排成 `[blocks, sequence]` 的int64张量，torch.save保存，**仅TRAIN、无padding**。保留生成它的分词器、原语料SHA、是否加special token/chat template说明。推荐使用昨天相同的训练语料；WT2只用于小规模连通性调试，不建议拿它独自做完整适配。

manifest JSON结构如下（示意路径/SHA必须换成真实值）：

```json
{
  "model_id": "Qwen/Qwen3-4B",
  "revision": "1cfa9a7208912126459214e8b04321603b3df60c",
  "posttrained": true,
  "model_dir": "/personal/project/model",
  "model_files": {"config.json": "SHA", "model-00001-of-00002.safetensors": "SHA"},
  "warm_ffn": {"path": "/personal/project/yesterday_ffn.pt", "sha256": "SHA"},
  "train": {"path": "/personal/project/train_blocks.pt", "sha256": "SHA", "split": "train", "raw_corpus_sha256": "SHA", "tokenizer_revision": "REV", "tokenization": "explicit protocol"},
  "calibration": {"path": "/personal/project/calibration/calibration.json", "sha256": "SHA"}
}
```

`model_files`实际需列出目录内全部模型/配置/tokenizer文件；示例不是完整清单。训练文件和warm权重也逐SHA验证。校准时可以先不写 `calibration`。只读本地模型，不自动下载或执行远程自定义代码。

```bash
python -m unittest qwen3.training.stochastic_nonlinear.test_training -v

# 单GPU、TRAIN前16个block做起步校准；正式可增加到128，冻结后不再在线更新。
python -m qwen3.training.stochastic_nonlinear.train \
  --manifest manifest.json \
  --config qwen3/training/stochastic_nonlinear/config_w8_t128.json \
  --out /personal/project/calibration --make-calibration --calibration-blocks 16

# 将校准路径/SHA填回manifest。先2个optimizer step验证，再用新目录做200步pilot。
python -m qwen3.training.stochastic_nonlinear.train \
  --manifest manifest.json \
  --config qwen3/training/stochastic_nonlinear/config_w8_t128.json \
  --out /personal/project/pilot --steps 200 --micro-batch 1 --accum 4 \
  --lr 1e-5 --seed 0 --gradient-checkpointing
```

最小入口采用next-token CE；没有实现KD、scheduler或验证集选优。已有训练器可继续使用其CE/KD方案，但要把teacher、温度、权重、学习率计划写进配置。这些选项不能假称在本入口已经实现。

接入原训练器的关键代码：

```python
# 加载旧权重之后、创建optimizer/DDP之前：
names = install(model, calibration, Config(nonlinear_samples=128))
optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-5)
for step, batch in enumerate(loader):
    optimizer.zero_grad(set_to_none=True)
    with noise_context(model, NoiseKey(seed, step, microbatch=0, rank=rank)):
        loss = model(**batch).loss
        loss.backward()  # 必须在context里面，包括activation checkpoint的重算
    optimizer.step()
```

上下文键包含seed/optimizer step/microbatch/rank/layer/stage；重算同一前向时复用相同随机样本，新microbatch换键。启用激活检查点时用 `use_reentrant=False`。不要跨microbatch挂起反向再修改模块的key；流水线并行需要另写每microbatch独立上下文。禁止TF32；硬路径内部禁用autocast，不要 `.bfloat16()` 整体覆盖已经安装的FP32 master。

多卡可用 `torchrun --nproc_per_node=... -m ...train` 的DDP入口，各rank随机键独立；当前是正确性参考，没有fused算子或通信/内存最优化。**先测实际step时间和峰值显存，再决定10张H200如何分配**。FSDP/ZeRO、异步流水线、torch.compile尚未验证，不能直接宣称兼容。DDP固定相同world size才能严格断点续训。

保存：每50步及最后保存FFN master、固定尺度/LUT、optimizer、next step、配置与provenance，附文件SHA。`--resume`指向本格式checkpoint，`--steps`是总目标步数，输出用新目录；配置、数据、代码提交、世界大小变化会拒绝恢复。不要把单纯warm start和严格resume混称。

## 6. 先验证再扩展

| 次序 | 实验 | 验收 |
|---|---|---|
| 0 | 同轮原始BF16、昨天checkpoint精确非线性、昨天checkpoint新随机前向（未再训练） | 相同模型/文本SHA、window/stride、token计分覆盖；不能用旧PPL冒充同轮参考 |
| 1 | W8、x64、非线性128，先2步再200步pilot | 36层都替换；仅108张量更新；梯度有限；检查饱和比例与train/heldout loss；记录吞吐/显存 |
| 2 | 相同初始权重独立训练T64，或明确标注从T128继续适配T64 | 不混淆训练采样数和评估采样数，验证收益/成本 |
| 3 | 选定训练预算后seed0/1/2及完整WT2滑窗PPL | 用训练集拟合、验证集选参数，最终test封存；至少三评估随机seed |
| 4 | W6/W4（仍需保留），分别校准与适配 | 不继承W8结论；若前期明显失败保留负结果，不做无依据的大扫描 |

此前未训练的新路径后缀PPL是BF16=13.5660、T64=21.8821、T128=15.3647；只是8×128后缀，不能写成完整WT2或训练后结果。小模型优化损失下降只证明代码能训练，不证明4B可以恢复精度。

监测使用 `diagnostics.diagnose(module, x, NoiseKey(...))`：返回g/u截断率、signed8驱动饱和率、非线性零事件率和平均事件概率。它是额外诊断前向；可在MLP输入hook中按固定TRAIN/验证片段调用，避免每一步都增加成本。代理梯度在饱和区为0，若截断持续升高，先在TRAIN重校准或开新配置实验；不要暗中在线改尺度。冻结当前checkpoint和配置，再做比较。

## 7. 交付记录

任务对应Issue177，依赖PR174、原计划Issue159。新结果放本任务结果目录/共享存储；Git提交小型配置、命令、摘要与SHA索引，不传权重。更新本人STATUS、HANDOFF与Issue，注明模型全称、父checkpoint、源码、语料/分词器、固定校准表、W位宽、x采样数、非线性采样数、seed、计分协议。没有完成训练的就写“训练待执行/结果待出”，不要以代码已推送代替模型已验证。

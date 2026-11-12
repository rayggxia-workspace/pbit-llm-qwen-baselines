# 权重和采样算法合同

## 固定权重

父模型 [Qwen/Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B/tree/1cfa9a7208912126459214e8b04321603b3df60c) 是后训练模型，不能换 Qwen3-4B-Base 或其他 revision。36层、32Q头、8KV头、head_dim128、GQA4。PPL按原始文本计分，不启用chat/thinking模板。

使用 [K_WH64 overlay](https://huggingface.co/CyberPrometheus/p-computing4llm-models/blob/d5e64227171c59ead00c00e610b53f424fbcbba2/submissions/20261106T064727Z-xhy12309-attention-100m-projections/models/k_wh64/projections.safetensors)，固定 revision `d5e64227171c59ead00c00e610b53f424fbcbba2`。文件1,887,453,752字节，SHA256 `89619fc18a1ea2a885f8495ea1ebddb4d187b3d8ae1096292dc8d046173cdfa9`。

只加载144个BF16张量：`model.layers.{0..35}.self_attn.{q,k,v,o}_proj.weight`，形状须与父模型一致。其他参数和FFN必须与原父模型一致，代码在覆盖前后哈希验证。不得加载同仓库另外的联合FFN权重或不同K/S各自训练权重。`parent_bf16` 例外：完全不加载overlay，用于环境校验；它与8.x PPL的同权重控制不是一个模型，不可用其差值声称采样提高准确率。

## SparQ：本项目实际版本

对每个KV组的四Q头，在post-RoPE的Q上计算每个维度的四头绝对值和，选最大的r=32个**共享维度**。不是四头各自选32维。设选出的Q为q_r，原维度D=128，对每头使用 `tau = sqrt(D * sum(abs(q_r))/sum(abs(q)))`，粗得分为 `(q_r/tau) @ K_r.T`。四头分别Softmax后将概率相加，得到KV组公共候选评分。

强制最近32个token评分为+inf，再取TopK，所以recent32包含在K128/K256预算中，不能额外追加。使用本包 `core.py:select` 的PyTorch `topk`返回顺序；不另做按地址升序重排，tie行为依赖已记录运行时。局部winner0指此候选数组的位置0，不必等于时间最早token。N≤K时直接保留所有N个token，按自然地址顺序。

选择后用完整128维重新计算准确QK，再做相应PV。无mean-V补偿。零范数/零选中范数按既有源码退回该组全可见K/V，并记录次数；正常真实Q应无此退化。无筛选分支显式绕过上述粗QK、Softmax聚合与TopK。

## 最新前端与winner-hold

对每个Q头已选候选的完整缩放QK分数s（FP32）：

```
c = max(s)                                  # FP32，先求最大值
a_i = clamp(RNE((c - s_i) * 16), 0, 255)     # U8/F4，共256地址
t_i = floor(256 / (1 + exp(a_i / 16)))       # 8位阈值，t_0=128
b_i = (u8_i < t_i)                          # u8为GF64输出字
```

这里的RNE是round-to-nearest-even；大差值饱和到255，不能溢出回绕。禁止绝对s先转signed12/signed8。输出概率为p_i=t_i/256；阈值不是已经归一化的softmax概率。独立理想伯努利条件下此winner链的平稳分布对应归一化odds `p_i/(1-p_i)`，有限P8/GF相关性和短S会影响实际结果；不宣称有限S输出恰等于精确softmax。

每个查询初始化局部赢家w=0，不预热。每帧并行产生候选b后：

```
A = {i: b_i == 1}
if b[w] == 1 or len(A) == 0:
    keep w
else:
    w = uniformly_selected_member(A)
emit w
```

当A恰有一个成员，直接选择；多个成员时从独立Bivium字中取足够低位，用rejection获取无模偏的有效rank。K≤256每字8位，无筛选物理容量2048每字11位。每次取字推进Bivium160步，取前8/11个输出bit；初始化预推进800步。拒绝最多64次，若仍失败**整项报错，不接受clamp后的结果**。

每64个候选用一组独立非零seed的GF32状态，输出64个8位字；K128/256/2048对应2/4/32组。同KV组四Q头顺序消费状态，跨查询保留状态，winner在新query重新置0。实际可见N小于容量时屏蔽不存在的lane；不能选到padding。`hardware_rng.py`给出精确seed派生、状态推进和分块规则，`gf_tables.bin`与`gf_map.sv`是无工艺数据的随机映射参考。

S帧输出S个winner，重复地址保留并按次数累加：`output = sum(V[w_t] for t in range(S))/S`。不能做无放回采样、去重后平均、只保留第一次winner，也不乘额外softmax权重。这里只是软件行为评测，V实际物理缓存/DDR突发/PPA不由该程序测量。

## 接手者的GPU检查

本次自包含移植扩展了无筛选仲裁字宽，**尚未在GPU运行**。`test_hardware.py`对128/256/2048做两次连续调用，逐字/逐rank/逐winner/末状态比对CPU oracle，其中有超过256活跃节点的压力输入。`run_eval.py gate`还验证实际模型长上下文和N=1冷启动、overlay、原生wrapper。必须先通过这些再运行完整WT2；失败应提交原始错误与源码补丁，不删除检查。

`SOURCE_ORIGINS.json`保留旧已运行代码的来源SHA；本次有改动的移植文件不是旧GPU验证的同字节制品。新实验以本次Git提交、源码hash和GPU gate结果为准。

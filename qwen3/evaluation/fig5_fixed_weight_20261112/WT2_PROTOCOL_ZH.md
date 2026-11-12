# 完整 WT2 cached-decode 计分协议

本协议供远程执行者复现本项目 Attention-only PPL。它不是固定1024后缀、训练 loss、chat PPL，也不是一次2048 token向量前向后仅换 decode 内核的假评测。

## 原文与 tokenizer

| 项目 | 固定值 |
|---|---|
| 数据集 | Salesforce/wikitext，wikitext-2-raw-v1，test |
| `wiki.test.raw` SHA256 | `173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08` |
| tokenizer | Qwen/Qwen3-4B revision `1cfa9a7208912126459214e8b04321603b3df60c` |
| tokenize | 全文一次；`add_special_tokens=False`；不套 chat template、不添 BOS/EOS |
| token 数 | 299078 |
| token SHA256 | `8d41d21825bb0e103dc63337727daf4b51c631cacec5937f014b119ae209081e` |
| token 哈希字节 | 每个 ID 为 signed little-endian int64，连续拼接；不是 JSON/hash字符串 |

HF parquet 将原文仅含空白的行存成空字符串。恢复每个空字符串为一个空格加 LF，即 `" \n"`；其他行保持原内容，直接连接，不额外插入分隔符。以原文 SHA 为最终标准。HF 数据仓库的下载 commit 在 `assets.json` 记录；即使数据 revision 改变，只接受上述原文和 token 哈希。

训练端曾有另一 token 哈希 `8557ef42be22a592e5f1704026fedbedc937b484e52f517add9f478adc0de20f` 及约11.540059父模型PPL；它不能与此处约11.538160参考混用。数值接近也不是同一协议。

## 窗口与目标坐标（全部为0起始，右边界不含）

context=2048，stride=1024。`plans.py:full_window_plan` 是实际算法，产生292窗。目标位置1到299077各出现一次。

```python
previous_end = 0
for begin in range(0, token_count, 1024):
    end = min(begin + 2048, token_count)
    first_target = max(previous_end, begin + 1)
    prefill_tokens = first_target - begin - 1
    # scored inputs: first_target-1 ... end-2
    # scored labels: first_target   ... end-1
    previous_end = end
    if end == token_count:
        break
```

| 窗口 | 原文 token 范围 | 准确预填充 | 实际计分 label |
|---|---|---|---|
| 0 | [0,2048) | 无 | [1,2048)，2047个 |
| 1 | [1024,3072) | [1024,2047)，1023个 | [2048,3072)，1024个 |
| 后续 | 每次起点前移1024 | 第一个计分 query 之前的1023个 | 只计尚未计过的目标 |
| 最后 | 由源码按299078截断 | 同规则 | 余下目标，绝不丢尾部 |

第一窗从冷启动逐 token 采样；后续窗先对未计分前缀用原生准确 BF16 SDPA，再将每个计分 query 的36层 Attention core 替换为对应方案。前缀使用同一权重 overlay，只有 Attention 算法准确，不回退父模型权重。

每窗 KV cache 重建，局部 RoPE 位置从0起（由原模型缓存位置机制生成）。当前 query 的 K/V 会先加入缓存；可见范围包含自身和历史，不包含未来。无 padding；不同长度/前缀长度的窗不在同一batch混合，不引入伪 token。

用模型预测真实下一个 token，输入始终是真实文本而非生成的 token。FFN、QK归一化、RoPE、残差、O投影、lm_head 保持模型原生路径；只有单 query 的 QK/选择/PV core 被替换。要求每层 decode 执行计数均为299077；随机方案每层应有299077×32个Q头采样事件。未计分前缀不计这些计数。

## 数值与合并

原模型参数 BF16；精确/采样 core 中 QK、粗筛、概率和 PV 累加为 FP32，返回原生 BF16接口。TF32关闭。logits 转 FP32后计算每 token cross entropy；逐 token loss 用 FP64 累计，每窗记录 NLL。最终：

`PPL = exp(sum(window.nll_sum) / 299077)`

禁止平均窗口PPL、忽略第一窗/最后一窗、把窗口大小当标签个数，或使用会额外减去一个 label 的loss denominator。所有目标位置的 int64哈希：`9bdd82d765abd7f46540033c03ad335e62d3bfd5b3e99ee83096f8f454f9e751`。

分块固定每32窗口，起点0,32,...,288；块内最大batch32，只批合兼容窗口。GF候选/仲裁状态在块内按层、batch-slot、KV组保持，同KV组四Q头顺序使用；块开始重新初始化。S变化会改变后续状态消费，**同seed不等于不同S全模型共享同一随机前缀**。

原生未改动父模型的同协议参考为11.538160478496504。新设备重跑后允许 mean NLL绝对差不超过1e-4（约PPL相对1e-4，属于新执行的验收容差，不表示历史结果逐bit相同）；超出先排查版本、语料、tokenizer、计分，不能直接放宽阈值。另报告精确差值。

`overlay_bf16` 与 `exact_kall` 是不同算子精度的同权重控制，不强迫二者逐bit相同。原生 wrapper 身份检查则必须同算子同精度，要求 logits SHA一致，不能用更宽误差阈值掩盖接入错误。

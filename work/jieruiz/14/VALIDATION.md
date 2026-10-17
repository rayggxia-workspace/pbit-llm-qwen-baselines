# Llama 2 当前标准 TLM：实际验证记录

负责人 @jieruiz，Issue14/PR15。实验原始输入与执行版本分开于后处理和文档；未修改已提交快照。

## 模型与基线

- 用户授权的ModelScope镜像；11文件全部匹配官方LFS SHA或Git blob。官方revision01c7f73d771dfac7d292323805ebc428287df4f9，镜像revisione61a2c602c83286a3ffbadaa29c20ad1160a8c4e；实际原字节SHA见正式identity。
- Slurm1960下载完成，1961 BF16完整WT2评测完成；2K PPL4.979502845218782、4K4.895831220529201，均335686个target，335687个原始token，不加BOS/EOS。9项CPU协议测试通过。
- 读取实际逐窗口日志，覆盖target1..N-1且NLL之和闭合；原始12文件与manifest共13文件字节/散列已核验。生成检查完成，但不是准确率基准。没有测GPU功率。

## 捕获和不可变源

- 正式1963四上下文512/1K/2K/4K均1024行，每个token原BF16和观察前向逐bit一致，最大logits差0、greedy一致。旧pending1962仅被取消，没有改其原始快照。
- corpus SHA173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08；固定start201979，前2K IDs SHA5c208664955a0c5e4d2fb19d1a018559bf02eccd36d6aafb2a77b0e5d8cabca8与Llama1一致。
- 捕获/TLM执行源b5964b165dfead06676580029235bf5e952b5dad，57输入SHA反复核验未变。BF16评测源9ee1ab47d0317430212364e75adb78abec9797fb。
- 7项TLM模型/身份契约检查通过；旧Llama1同形状trace、缺身份、非逐bit参考、上下文越界均拒绝。4K显式synthetic只作结构测试，未并入真实结果。

## 4K独立资源与映射复核

下表是构造和地址容量检查，不是8种方案的性能实测；所有8个构造均通过。

| 4K情景 | 外存地址上限 | 片上Attention工作区峰值 |
|---|---:|---:|
| BF16 dense | 14.55322GiB | 2.02783MiB |
| SC dense | 10.52197GiB | 2.02783MiB |
| SC＋筛选＋PV | 10.64893GiB | 6.58527MiB |
| SC＋筛选＋Ising | 10.64893GiB | 6.60144MiB |

均低于16GiB/8MiB；KV保守预留2GiB＋512KiB，筛选摘要130MiB。32Q/32KV、group=1、4K S256；adapter的union仅本头V去重，没有GQA跨头并集放大。RMSNorm epsilon1e-5、RoPE10000及原生4096边界符合实际配置。

## 后处理验证

- 11项报告契约测试通过。数字11个source key，SC额外3个；共同SHA、同variant完整字典和57个canonical输入逐项比对，不误将合法模块差异当成混源。
- 只读解析实际BF16与4个实际2K/4K Link输出通过；另用3种数字BF16/数字W8/SC路径核canonical源码SHA通过。没有重跑或修改原始结果来适配报告。
- 最终后处理Slurm2069依赖1961/1964/1965/1966全成功；必须116个唯一key齐全才产生正式汇总。源358d8b8f943f60986f86362f7bc7aacfca531adc，与执行源分开。

最终结果及发布manifest就绪后，再核116key、逐项时间/能量和、真实K/V与样本事件守恒、源码/原始成果SHA和Git blob。正在运行的DRAM任务不能提前写完成。

解释边界：原BF16 PPL与单条真实QK地址oracle均不证明随机FFN/筛选/Ising联合质量。TLM不是芯片/GPU能效实测，部分算子与PHY/布线仍未标定。

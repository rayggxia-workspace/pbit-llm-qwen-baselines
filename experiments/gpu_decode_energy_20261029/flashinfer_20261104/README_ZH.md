# FlashInfer／SDPA decode补测（Issue212）

## 2026-11-05修复与接续

旧作业4392已经结束，33个产物的大小/SHA与封存manifest核验通过。FlashInfer CUDA/Tensor在2K/8K均因0.2.5的`head_dim`未初始化异常退出支持检查，没有可接受的FlashInfer性能数据。直接GQA核心数值检查通过，但部分整模型logits relative-L2超过预设1%，不能写为整模型验收通过。下方“4392排队中”为历史提交时点。

修复仅针对调用接口：Qwen的scale等于`1/sqrt(head_dim)`，先严格验证这一点，再让FlashInfer使用完全相同的默认`sm_scale=None`，使其正常初始化head_dim。不改site安装文件、不改变BF16 Q/K或缩放值；遇到非默认scale明确拒绝，不静默近似。回归测试直接调用CUDA/Tensor两条包装路径，模拟旧API的初始化分支。

新GPU预检4604已实际编译并运行CUDA/Tensor内核，head_dim异常消除；它暴露CUDA single_decode对带padding的增长缓存报`k must be contiguous`，故该失败快照保留，未启动的依赖4605撤回。后续v4仅在CUDA路径执行K/V.contiguous，实际复制位于计时/能量窗口内部，不免费预处理；Tensor路径继续直接接受HND stride。此处不是把KV展开为32头。

新快照额外保存`HF_ORIGINAL_NATIVE.json`：未安装Attention Adapter的官方HF SDPA/DynamicCache连续256步生成，排除prefill。它与展开KV的静态缓存Adapter、直接GQA、FlashInfer两路径分开报告。固定CUDA Graph前向仍不等于连续生成。

新增`--preflight-only`仅执行2K/8K的支持与数值检查，不测正式时间/能量；支持异常返回非零以阻止依赖作业。CPU测试、GPU预检、正式GPU作业通过Slurm afterok依赖串联。所有原门槛及失败清单保留，不为直接GQA或FlashInfer放宽。旧环境/旧快照/旧结果不覆盖；准确新作业和状态见本次专门回执。

用户授权：编写脚本并通过Slurm提交补测。旧3399/3440/3443及其环境、源码、封存结果均不改。本次不训练、不量化、不跑PPL，不宣称最佳GPU服务引擎。

## 比较条件

Qwen/Qwen3-4B后训练版，revision `1cfa9a7208912126459214e8b04321603b3df60c`，原BF16、B1、2K/8K，32Q/8KV头、head_dim128。沿用原模型/分词器/语料与token SHA，运行前逐文件核验，单张Slurm分配的RTX5090，同一进程配对测量，不使用TDP估算能量。

| 后端 | 处理 |
|---|---|
| sdpa_expanded | 安装版HF同样的repeat_kv＋强制PyTorch Flash SDPA |
| sdpa_gqa | 强制Flash SDPA，直接enable_gqa=True |
| flashinfer_cuda | FlashInfer single_decode，原生8个KV头，CUDA-core路径 |
| flashinfer_tensor | 同上，use_tensor_cores=True的FA2路径 |

保留现有Torch2.7.1+cu128/Transformers4.51.3；任务目录独立安装兼容FlashInfer0.2.5/ninja1.11.1.4，不升级原环境。该固定软件版本用于隔离后端影响，不声称代表最新版FlashInfer/vLLM/SGLang的最佳表现。源码包从官方PyPI获取并核验SHA；首次CUDA JIT发生在数值预检阶段，编译时间不计入正式窗口。

## 实际测什么

1. 完整36层模型固定单token CUDA Graph前向：每后端/上下文10秒×3，排除prefill、argmax与上下文增长；同后端Graph/eager要求logits逐位一致。
2. 完整模型连续贪心decode：每次256步×3，包含argmax、KV当前位置更新及上下文增长，排除prefill；能量窗口不足3秒时明确低置信，不当长窗主结果。
3. Attention核心：使用未改动模型全部36层的真实Q/K/V输入，5秒×3独立回放；其时间/能量不能相加冒充完整模型。
4. 独立Profiler检查内核、36层覆盖和14类模块kernel时间。Profiler阶段独立，不将其插桩时间作为主延迟。核心CORE_TRACE与整模型TRACE分开保存。

能量主值为NVML累计整卡能量差，包含板载显存；首重复另作功率积分一致性诊断。记录温度、SM/显存频率、预热稳定性，既不锁频也不假称恒温；两种NVML接口不是独立电表。仅使用Slurm分配GPU，并拒绝同卡外来计算进程。

## 数值门禁

- 三个不重叠的真实文本位置，所有后端使用同一原模型KV与输入token。原SDPA静态缓存路径保持bitwise相同；其它后端保留原relative-L2≤1%且top1相同门槛，不为让历史GQA失败通过而放宽。
- 连续decode所用较大容量HND缓存会有不同head stride。v2增加带padding的同一真实接口及连续两步因果更新检查，防止只验证紧凑固定缓存。
- 对第一/中间/最后层输入，另用FP32 math SDPA作独立Attention输出oracle，relative-L2≤1%。这只是数值正确性检查，不把FP32 oracle当实际高效基线。
- 已应用RoPE/QK-Norm的Q/K送入内核，FlashInfer设置pos_encoding_mode=NONE。仅访问已写入有效前缀，不将未使用缓存槽当真实K/V。
- 未通过数值/支持检查的后端单独封存原因，不计入接受的整模型性能结果；其它后端继续。正式结果状态包含失败清单，不把部分后端成功写成全部通过。

## 当前提交状态

CPU4388已COMPLETED/0:0/11秒：隔离安装与6项CPU测试通过，Torch不变，FlashInfer使用JIT后端。首次GPU4389尚未启动即由v2替代，未消耗GPU测量时间，旧包/回执保留。**当前有效GPU作业4392**，单5090、4CPU、48GiB、1小时上限，排队中；不重做已完成安装。

v2执行包SHA `5e5f0f324f84bdeb7cc73e50bd04083aa3b0d03bedeccffff06c4c0d92322f11`，manifest SHA `d2afc2b2239ecfb66f31837fe456365040ba117cb303c7a7050d53536d2ee5d8`。每run核验代码、配置、准备清单、权重和输入SHA。输出ARTIFACT_MANIFEST与COMPLETED.json封存；大trace留已有个人服务器存储，Git仅索引与小结果。

本机从冻结快照进行AST/逐文件SHA检查及6项CPU测试通过；GPU正确性、可用内核、时间与能量尚待作业运行。不把“安装通过/任务提交”写成“GPU已验证”。这次是FlashInfer接入HF完整模型的后端消融，成熟服务引擎对照仍需单独建立。

## 入口

测量：`bench.py --root <冻结源码目录> --prepared <原准备清单> --output <新结果目录>`。配置CONFIG.json，依赖来自Issue212原冻结测量源码，controlled_remeasure.load_dependencies逐SHA验证。提交/访问的本机路径与回执在任务HANDOFF，不公开凭据或旧完整历史。

机制参考：[FlashInfer固定版本decode源码](https://github.com/flashinfer-ai/flashinfer/blob/v0.2.5/flashinfer/decode.py)、[官方PyPI版本](https://pypi.org/project/flashinfer-python/0.2.5/)、[PyTorch SDPA](https://docs.pytorch.org/docs/2.7/generated/torch.nn.functional.scaled_dot_product_attention.html)。

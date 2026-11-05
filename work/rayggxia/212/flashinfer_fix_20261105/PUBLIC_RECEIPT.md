# FlashInfer接口修复与GPU补测接续

2026-11-05，Issue212 / PR214，负责人rayggxia。用户授权修复调用错误，并比较官方HF与直接GQA内核；没有修改TLM或训练任务。

旧4392已结束，33个产物manifest的大小和SHA全部核验。FlashInfer0.2.5两后端在显式传入默认sm_scale时触发head_dim未初始化，未得到可接受性能结果；旧快照保留。

修复先严格确认Qwen使用1/sqrt(head_dim)，再传sm_scale=None，数值相同且不修改共享安装。GPU预检4604已真实编译/执行两后端，原异常消除；发现CUDA路径要求连续K/V，增长缓存需在调用内作contiguous。该复制的时间和能量计入测量，Tensor路径保留原HND步幅。4604失败归档，依赖未启动的4605已撤回；没有覆盖原环境或失败结果。

v4源码包SHA-256：a1516504096ffedf566caed7efe413ed59b4e5124a8919b54505fb669145561a；源码manifest：55d3b2360e9a79e7aa2642fee8f2020826912317dba7d7dab70ce8ab3c511f45；配置SHA：bb68cc009fb4bbc262a2a188c7bd50bc698ff1589adca42084026f0013848741。本地冻结快照10文件SHA/语法与9项CPU测试通过。

新作业：CPU4606 → 单5090 GPU预检4607 → 正式补测4608，使用afterok依赖、各GPU4CPU/48GiB，预检45分钟/正式90分钟上限。提交不等于完成；准确进展以封存结果和后续回执为准。

实际回查：CPU4606九项通过；GPU4607 completed/0:0，1分09秒。13个预检原件manifest大小/SHA核验通过，四后端2K/8K均无支持异常、核心oracle均通过，FlashInfer最大核心relative-L2为0.2570%。三位置及增长接口top1均相同，但直接GQA/FlashInfer部分整模型relative-L2仍超过原1%门槛，不接受为整模型精度通过。正式4608已RUNNING，尚无完整封存结果。

同后训练Qwen3-4B/BF16/B1/2K及8K，原模型/数据/配置保持。新增HF_ORIGINAL_NATIVE.json测未安装Attention Adapter的官方HF SDPA/DynamicCache连续256步；展开KV、直接GQA、FlashInfer CUDA/Tensor分别测量和标识。核心回放、固定Graph与连续生成不混称，prefill不计入decode。

保留原relative-L2≤1%且top1相同、真实HND步幅/连续两步、FP32核心oracle等检查。部分直接GQA/FlashInfer整模型门槛未通过时不晋升正式整机成绩；支持失败不会隐藏成零能耗。未宣称新PPL、最优服务引擎、GPU节能倍数或ASIC PPA，PR未合并。

## 最终实际回执

正式4608已结束，47个原件大小/SHA、10执行源、42窗口W×秒=J和14类/36层Profiler覆盖通过。39个小原件已收集，大轨迹留服务器。官方HF连续生成：2K22.964ms/5.516J每token，8K27.035ms/8.718J。36层核心回放：展开KV1.821/6.187ms，直接GQA0.459/1.133ms，FlashInfer CUDA0.431/0.837ms，Tensor0.340/0.906ms（2K/8K）。这些核心成绩不当作整机token时间。

直接GQA/FlashInfer部分整模型logits仍超过1%门槛（探测top1相同），所以未接受其整机正式成绩，无新PPL/质量无损主张。没有本轮运行中作业。完整分口径报告和统计见results/gpu_decode_energy_20261029/flashinfer_20261105/REPORT_ZH.md及RESULTS.json；旧历史结果与环境未改。

# 采样次数与decode时间：秒级tile估算＋完整TLM适配

2026-11-06，Issue225/PR248。用户要求前级Wg/Wu采样8次、后级非线性三路AND直连Wd采样32次的时间预估，lm_head单独列出；先查最新服务器结果，再对当前1216KiB/640路配置运行原生对照。

## 1. 最新已完成的完整参考

服务器38616054两项已COMPLETED/0:0，RESULT/SEAL SHA与本地归档一致。当前已完成的96KiB GU状态方案仍为1952KiB SRAM、1024路普通数字池、12个C20公共核、前后均T64、2K/K128/赢家S64、100MHz。它不是1216KiB/640路的新组合。

|完成参考|含lm_head ms/token|lm_head阶段 ms|扣lm_head阶段 ms/token|
|---|---:|---:|---:|
|2008KiB／152KiB GU状态|49.95081|6.95415|42.99666|
|1952KiB／96KiB GU状态|49.93827|6.95415|42.98412|

“扣lm_head阶段”保留final norm，也保留已经在最后NL_Wd中重叠发生的少量lm_head预取。它不是取消lm_head硬件和全部预取的第二次运行；不能用它宣称对应能量也全部移除。后续正式结果始终同时列这三列，不只给一个模糊decode时间。

## 2. 快速使用

```text
python -B architecture_tlm/sampling_latency_20261106/fastsim.py --gu 8 --wd 32
python -B architecture_tlm/sampling_latency_20261106/fastsim.py --scan --out quick.json
python -B architecture_tlm/sampling_latency_20261106/fastsim.py --profile <新封存T64参考的profile.json> --gu 8 --wd 32
python -B architecture_tlm/sampling_latency_20261106/fastsim.py --profile architecture_tlm/sampling_latency_20261106/CURRENT_PREFIX_PROFILE.json --gu 8 --wd 32
```

脚本只用Python标准库，不依赖EDA服务器、GPU、PyTorch或原生DRAM库。默认REFERENCE_PROFILE绑定上面1952KiB/1024路完整参考，不能把它的数值改名为1216KiB结果。将来新T64完整任务结束后，用work/rayggxia/225/sampling_latency/make_profile.py从RESULT和SEAL生成新profile即可。

六组默认扫描本地约0.7秒，结果在QUICK_SCAN.json。点估计如下，均属轻量模型：

|GU采样|非线性＋Wd采样|含lm_head ms|扣lm_head阶段 ms|
|---:|---:|---:|---:|
|64|64|49.93827|42.98412|
|32|32|49.90371|42.94956|
|16|32|49.89219|42.93804|
|8|32|49.88643|42.93228|
|8|16|49.88067|42.92652|

这些小数位只保留复算信息，不表示微秒级预测精度。尚未用新采样配置的完整原生结果校验误差；现阶段应理解为“约50ms／约43ms，速度可能只小幅变化”，不能把0.10%当已验证的收益。

### 当前1216KiB／640路粗估

两层原生结果完成后，CURRENT_PREFIX_PROFILE用T64两层各阶段×18外推36层，embedding只计一次、final norm沿原宏，并暂用旧1024路的6.95415ms作为lm_head代理。该代理不是新640路实测；第三个捕获Attention层及末层预取差异也未由两层外推覆盖。CURRENT_QUICK_SCAN按此锚点得到：

|当前1216KiB配置|含lm_head粗估ms|扣lm_head阶段粗估ms|
|---|---:|---:|
|前64／后64|51.30|44.35|
|前8／后32|51.25|44.29|

因此可以暂估“约51ms含头、约44ms扣头”，而不是声称已得到新版完整token结果。完整原生任务完成后，应以其RESULT/SEAL替换该外推profile，lm_head单独更新。

## 3. 为什么没有按8/64或32/64比例缩短

快估每层分别运行GU和Wd的tile级离散事件模型：32个有限8KiB权重槽、12个共享核、每核两个未退休结果、输出间的严格K依赖、两个状态服务端口、GU均衡输出窗口及输入命中优先。权重加载按带宽串行推进，加载、核计算和跨K退休允许重叠。它不展开每个16B SRAM字和每个64B DRAM请求，因而快得多。

旧actor每帧660ns，即1装载＋64采样＋1读出。新时间适配维持每拍相同电路服务，GU8为100ns/帧、后级32为340ns/帧；没有把额外编码、跨K读取/累加、输出转换、Attention、QKV/O或lm_head时间一起乘采样比例。该可变T时序是沿原协议的宏假设，尚无新T8/T32芯片PPA。

Qwen3-4B每层GU6080帧、Wd3040帧，每帧权重8192B；36层FFN权重约2.690GB。136.4606GB/s下理想搬运约19.71ms，而T64核服务的理想12核平均计算量约18.06ms；前8/后32的理想计算服务约4.92ms，但权重仍要搬同样多。跨K状态、槽信用和其他调度也不消失。因此减少核内采样能节省工作和潜在能量，未必直接转化为同等速度提升。

每个阶段用实测T64阶段时间减去tile模型T64时间，保留固定校准偏移；变化采样后只更新tile事件部分。该近似没有重新精确求解跨阶段DRAM竞争、bank冲突和真实延迟分布；QUICK_SCAN不用于新能量/面积结论，也不用于验证PPL。

## 4. 当前1216KiB原生TLM对照

新执行快照4528b0b42a97，不修改既有1216、FFN96或旧运行源。`model.py`只在实例delay接口改变common_GU_core/common_Wd_core实际服务时间，并修正冻结actor中原660ns统计及R8动作计数；其他delay不缩放。仍1216KiB/304宏、640普通池、12公共核、96KiB状态、CIM32槽、K128/赢家S64。后级AND事件直接进入Wd，不引入z平均后重编码。

7项本地检查及EDA门禁38617085已通过。两配置T64/64与T8/32的两层配对38617086已完成并逐SEAL SHA核验；完整36层＋lm_head数组38617087依赖成功后接续。1CPU/任务、0GPU、最多2并行；完整结果尚待运行，不把前缀当整机。原来未成功的1216计划没有重交另一套重复任务。新采样配置不套T64电路能量价格，当前只验时序和事务。

|真实原生两层|总时间ms|GU＋NL_Wd时间ms|
|---|---:|---:|
|前64／后64|2.46395|1.25171|
|前8／后32|2.46201|1.24790|

两层总时间−0.0787%，FFN两阶段−0.3044%；两侧外存均257484544B。MAC/归约/QK/PV/Attention样本/等效SC工作/跨K次数守恒；GU随机端口动作缩为1/8，后级缩为1/2。R8减少被正确统计，未被误写成不变。原件逐字节归档至project_archives/sampling_latency225_20261106/native/prefix/，小表NATIVE_PREFIX_RESULTS绑定原结果SHA。

测试覆盖可变帧时长、非FFN延迟不变、资源及边界、带宽下限、计算受限时采样加速、带宽/状态受限时回压、参考重建和lm_head分列。原生配对完成后核MAC/跨K/Attention次数和外存字节；随机动作应随样本数变化，不能要求其也不变。没有新训练或PPL验证。

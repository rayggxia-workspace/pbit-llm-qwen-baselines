# Attention：100/250MHz小SRAM确定性数字路径交付

2026-11-07，Issue198 / PR199；响应Issue236 / PR244的DIGITAL_BASELINES_100_250_NEXT交接。**本模块交付完成，宿主原生单层/36层整机验收尚未运行。** 概率Attention默认、100MHz旧结果、FFN及总面积目标均未修改。

交付源码：`architecture_tlm/attention_digital_small_20261107/`。接入入口为`adapter.Attention`，两个模式`dense`、`screen_full`。公开材料仅摘要、profile及纯SHA索引；执行源/完整回放保留本地授权工作区。

## 已完成什么

- dense采用tile32在线Softmax/完整PV；同KV组四个Q头共用K/V一次外存填充和一次算术操作数读取。没有N×N矩阵、没有全KV驻片上假设。
- screen_full采用r32、四头粗概率相加、K128、local32、无reallocation；保留粗K、精确K重打分以及全部128候选V，不使用S64赢家地址。尺寸选择含原SparQ的每头L1温度，零L1/N≤128转dense。源算法的candidate metadata由宿主提供；局部回放由合成BF16 Q/K产生真实规则的候选，非模型结果。
- QK和PV实际向同一个宿主FMA池申请64lane租约，归还前必须消费结果；projection/FFN/head可用同一仲裁器。测试包含只有64lane的池、两个Attention组及竞争宿主客户端，未超额使用。
- 每个并发slot48KiB/12bank；2/4/8组分别96/192/384KiB。100使用1088KiB/272bank，250使用960KiB/240bank，全部16B/1RW、与计算同频。空间从宿主已有SRAM划分，不另加宏面积。
- K/V各双缓冲，32B操作数FIFO4信用，512B转置保持、最多16笔store在途；双缓冲消费完才允许覆盖。DMA全局256信用/16KiB入口由宿主统一提供。实际地址决定bank冲突和返回回压。
- 已测FMA16/C4没有免费FP32状态装回接口。本版每tile先从零做PV，最终C4结果暂存在复用的1KiB Q保持，再用8路FP32加法器合并到SRAM输出。下一tile重新读取Q；合并的加法、读写、保持和时延全部计入。

## 矩阵池与固定成本合同

`PROFILES.json`按频率/模式/并发给固定组件、合法池大小、L/II、生命周期。共享池resource_id=`ordinary_BF16_FMA_pool`；100/250每16lane分别0.2448702252/0.2487972024mm²。已经乘0.81，不再折算。池允许4..128个16lane slice；Attention最多同时使用64×并发组lane，额外lane可供宿主其他阶段，不假定继续降低Attention时间。

固定组件包括每slot8FP32 ADD（QK归约与Softmax时分共享）、4exp、1FP32 MUL、1倒数种子、1BF16转换；2176B有界保持；10%标量面积＋0.01mm²/slot控制/接口预留。screen另有一套共享top16＋norm16。宿主SRAM、DMA保持、向量处理、投影FIFO、FFN、head不在固定表中重复收费。控制预留建议0.5×/2×敏感性，不是新综合PPA。

FMA反馈L4/C4、稳态II1；精确QK为4头×4token×Kparallel4，16token一批，3ADD/输出归约后消费再复用C4。PV每次处理64维，共两遍，每个V元素实际只读一次。PV merge用8ADD/L4、4×32B读改写信用。FMA价已含反馈寄存器，不再追加旧partial_state逐MAC费用。

## 数值和250MHz边界

Q/K/V为BF16；QK四partial及归约FP32，分数按1/sqrt128缩放。在线running max/l、差值、重缩放和输出归一化为FP32；exp采用已有自然指数range-reduction表、BF16权重；倒数种子＋两次FP32 Newton；最终BF16 RNE。这里没有Ising绝对signed8前端，也没有用FP32理想exp免费替代硬件表。准确PV指无采样，不代表与框架逐位相等。

250 FMA、top/norm使用已有TT250校准。**在线Softmax的标量ADD/MUL/exp/倒数/转换仍为SS100面积与动作价代理，250的L/II是显式宏合同，不是新TT250 STA通过。** 可建立条件TLM，不据此宣称完整250MHz电路已签核。标量共享/跨模块接口、布线和门控控制保留预留；未做新RTL/PT。

源SparQ硬件粗分数存储按BF16代理收费；与算法FP32候选规则的逐位一致性未在本轮验收，不能把这些时间/能量当新PPL证明。mask为单token decode、N个可见历史位置；其他mask/tail需扩展合同，不静默补零。

## 完整形状局部回放

下表为同一套合成BF16 Q/K：8组seed17+1000×组号，真实计算每块max是否提高；只有max提高的头才重缩放。不是假定每块都缩放，也不是Qwen性能测量。周期和能量由实际有限缓冲事件产生。外存解析后端为60ns、136.4606GB/s；32请求/片上拍发射上限不额外限制链路。整机应换原生LPDDR后端，不把下表当整token。

|MHz|路径|并发KV组|租用池lane数|局部时间µs|固定逻辑mm²|共享池mm²|能量小计µJ|
|---:|---|---:|---:|---:|---:|---:|---:|
|100|dense|2|128|3743.540|0.444776|1.958962|425.272|
|100|dense|4|256|1892.900|0.889553|3.917924|425.428|
|100|dense|8|512|951.660|1.779106|7.835847|425.505|
|100|screen_full|2|128|1017.490|0.531011|1.958962|84.313|
|100|screen_full|4|256|584.600|0.975788|3.917924|84.814|
|100|screen_full|8|512|443.390|1.865340|7.835847|87.019|
|250|dense|2|128|1496.572|0.444776|1.990378|464.006|
|250|dense|4|256|756.784|0.889553|3.980755|464.021|
|250|dense|8|512|381.300|1.779106|7.961510|464.031|
|250|screen_full|2|128|414.048|0.538126|1.990378|90.392|
|250|screen_full|4|256|237.528|0.982903|3.980755|90.444|
|250|screen_full|8|512|179.724|1.872455|7.961510|90.662|

能量小计=本模块逻辑活动＋明确门控背景＋实际SRAM动态＋外存4pJ/bit；包括列出的共享FMA池在本窗口的背景。**不含宿主公用SRAM泄漏/DMA捕获/PHY/其他阶段**，宿主整机只加一次；不能与概率方案不一致的边界直接作能量比。`ESTIMATES.json`分列logic/SRAM/external及4/6.6/8pJ/bit。活动按动作收费，等待关闭时钟和输入；保留泄漏、活动时钟增量，holding沿旧idle作泄漏上界，未假定所有等待功耗为零。

|N2048单层32Q/8KV|dense|screen_full|
|---|---:|---:|
|粗QK MAC|0|2,097,152|
|精确QK MAC|8,388,608|524,288|
|PV MAC|8,388,608|524,288|
|粗K读|0|1,048,576 B|
|精确K读|4,194,304 B|262,144 B|
|V读|4,194,304 B|262,144 B|
|逻辑新K/V追加|4,096 B|4,096 B|

本后端只实现64B整burst写，因此screen转置K副本维护还显式计64KiB读＋64KiB写RMW。**这是后端追加政策，不是SparQ必需算法量。** 支持byte mask的共同宿主可以替换这段；概率侧和数字侧必须一起采用同政策，已有宿主追加不得再重复计。含追加的外存总量dense8,392,704B、screen1,708,032B；前述表中的算术读取保持独立。

当前执行采用有限tile/双缓冲，QK、Softmax、PV在slot内分阶段；不声称已经实现跨tile全部重叠或Flash-Decoding最优映射。2/4/8并发均给出，宿主按相同总面积、FFN接口与实际LPDDR利用率选主点。不能固定旧512QK＋512PV，也不能默认本表FMA数就是整机最终选择。

## 验证与接入步骤

1. 4项本地测试通过，含24个三seed数值对照（dense/选K后完整PV、4Q头）；精确在线恒等式误差阈值rtol1e-11/atol1e-12，含BF16 exp/FP32 tile-local merge/最终RNE的相对L2<2%。另验K打包4096元素双射与Kparallel4点积、fallback、非法配置拒绝、有限共享池竞争与读量守恒。它们不是模型PPL或门级端到端验证。
2. 12个N2048全形状局部回放均通过：MAC、GQA K/V、追加字节、pool峰值≤配额、4词FIFO、DMA/SRAM队列排空。256信用和实际1RW bank由原共享内存后端执行。旧串行打包/假想状态装回的中间结果保留为SUPERSEDED，不参与正式汇总。
3. 宿主读取选定profile，将固定组件与FFN组件合并；共享池面积只加一次。`legal_pool_slices`与FFN合法集合求交，按planner选相邻可行点，不修改本轮33.284710/20.872325目标。
4. 由宿主创建一个`SharedPool(h,lanes)`（或相同acquire/release/live接口），所有投影/Attention/FFN共享；分配48KiB×并发regions；`actor=Attention(h,pool,regions,Config(...))`，yield from `actor.run_layer(rows)`。rows含每KV组base、r32 dimensions、K128 candidates、每tile提高max的头数max_changes；Config(rescale='trace')使用实际trace。没有trace可用upper明确跑敏感性，不能默认为0。
5. KV外存布局：base为row-major K，base+N×256为dimension-major K，base+2N×256为row-major V；四Q组输入已RoPE，Q_arrival/KV_append_input是生产者向当前region交付的写事件。宿主若已执行交付或append，必须对接而不是再收费。test旧hub额外预留但不用的16KiB返回SRAM在总容量内，不是增加16KiB宏。
6. 源码、SHA、完整回放和TEST_LOG按索引取；本地命令：

```powershell
python -m unittest architecture_tlm.attention_digital_small_20261107.test_adapter -v
python -m architecture_tlm.attention_digital_small_20261107.replay --memory <宿主shared_memory.py绝对路径>
python -m architecture_tlm.attention_digital_small_20261107.profile
```

剩余由Issue236负责：同面积最终pool数、FFN合同合并、原生LPDDR单层门禁与36层（含/不含lm_head）结果。没有额外GPU作业，没有新训练或精度宣称。SS标量250路径若用于最终物理结论，应另补时序或调大宏L/II后重放。

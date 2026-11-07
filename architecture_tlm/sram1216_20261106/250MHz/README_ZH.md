> 2026-11-07当前默认：SRAM已实际改为960KiB/240bank，投影双缓冲2×32KiB、八组Attention各48KiB、删除未使用DMA SRAM32KiB；返回寄存器保持16KiB。1216/1088/960三版完整冷单层为1.085980/1.086184/1.085700ms，时间持平，旧TT核参考覆盖面积22.59477→20.87233mm²。见[本轮报告](SRAM_COMPACT_ZH.md)与SRAM_COMPACT_RESULTS.json；显式`--sram-profile reference1216`可恢复容量对照。100MHz不改。

> 最新电路证据：短T/C19 TT250报告已收，但setup为−0.421007ns，未闭合4ns；有效核价继续null，当前周期和旧核价只作条件参考。下方早期快照、旧面积审查与原生任务保留原历史范围，不代表当前容量或完整token结果。

> 2026-11-07最新接合：默认安装新交接的有限FIFO、离线交错投影权重与显式宽分数前端，替换旧v1，不叠加5.2µs预算。真实返回4ns整数周期审计、同宏TT SRAM事件价格已接入。3/2核完整冷单层解析回放1.085992/1.114148ms，见REFRESH_RESULTS.json；短T/C19 TT250 PPA仍待收，旧T64参考单列。下文LOCAL_RESULTS与旧四项原生作业属于前一冻结快照，不替代本版全token结果。完整对照见architecture_tlm/module_refresh_20261107/README_ZH.md。

# 统一250MHz整机TLM：初版冻结快照与当前入口

2026-11-07，Issue225，负责人rayggxia。此目录由原证据目录扩展为**可执行的完整decode模型**；100MHz入口、默认和原件保持不变。代码已经接合，本地两种核数的完整形状单层检查已通过。原生LPDDR的36层＋lm_head四项任务 **38622601** 已提交，首次核查两运行、两排队；完整token时间仍待封存结果。

## 配置

|部分|本版配置|
|---|---|
|模型工作负载|Qwen3-4B，B1／2K，36层＋最终norm和lm_head；不是PPL推理|
|片上时钟|计算、SRAM、DMA前端全部250MHz，4ns；外存时钟独立|
|FFN|GU16／Wd32分层采样，K64/M128准确加权树，公共C19、20bit传输；推荐3核，2核敏感性|
|FFN驻留|32×8KiB权重槽、每核两结果信用、两个state32口、96KiB宽状态；不按减核缩减编程并行|
|Attention|K128／S64，4采样器、4top＋4norm、64 PV ADD；共享256路FMA，16末端归约ADD|
|片上存储|1216KiB，304×4KiB宏；每bank16B／1RW，前端176bank交织共享|
|DMA|24请求/拍、256在途、24KiB实际返回保持；既有有限请求/返回队列|
|外存|已有derived8533原生Ramulator时序，136.4606GB/s峰值；不随片上频率乘2.5|

GU每帧18拍＝72ns，后级每帧34拍＝136ns。state32四次更新占4拍＝16ns；GU恢复/定点编码暂4拍，Wd最终BF16恢复暂3拍。归一化指数分别−4／−5，不能沿用T64的−6。随机前端保留本地服务接口，GF64已在前代整核价格内，不再加随机池或概率SRAM。

## 本地已完成的检查

|单层方案|完整形状单层时间|GU阶段|非线性＋Wd|覆盖面积代理|
|---|---:|---:|---:|---:|
|3公共核|1.090076 ms|0.363908 ms|0.183108 ms|22.5948 mm²|
|2公共核|1.117640 ms|0.364048 ms|0.210532 ms|21.6253 mm²|

这是**解析外存＋实际片上bank/队列的单层回放**，不是新原生整token结果。两核慢约2.53%，覆盖面积少一颗前代核0.96948mm²。逐帧/逐K依赖、两结果信用、动作和外存字节守恒、队列排空检查通过；与Attention作者的536.832µs解析前缀逐时刻相符，另显式加入其先前未计的5.2µs宽分数前端宏。

## 时序确实考虑了什么

所有模块共享同一事件时间轴。模型执行真正的权重搬运、32槽ready/release、norm双缓冲、计算与预取重叠、SRAM地址重排和bank仲裁、有限DMA及返回回压、跨K状态SRAM读改写。共享FMA在QKV/QK/O/lm_head间切换，不同时拥有两套阵列。PV只读取采中且未命中本地缓存的V；QK候选与采样地址沿冻结输入复用。

没有把一层总时间当固定宏，没有将旧结果除2.5，没有取消未完成的访存或把所有SRAM访问串行化。输出包含每层每阶段时间、采样核心忙时、等权重/结果信用等待、实际SRAM动作和DRAM地址/流量摘要。原生任务检查外存完成字节与主模型计数一致。

## 仍以宏或代理表示的部分

1. **GU16/Wd32的C19核PPA尚未测出。** 时序按T+2及交接接口运行；面积暂用已测TT250/C20的每核0.969479mm²。能量单列“保留旧T64每帧增量工作”的参考情景，不按16/64或32/64送节能，不称短T实测；未知实测字段为null。
2. **格式转换、RMSNorm/RoPE、残差和最终归约**沿既有周期合同及SS100动作单价代理；不宣称新的4ns STA。宽分数max/差分/量化每层另收5.2µs宏和面积/能量预留。
3. **PV2、微块转置暂存及新仲裁/译码/广播**有模块推导和显式价格预留，尚非整合后布局PPA。SRAM采用已有E宏访问时间和事件能量，4ns可容纳该宏的既有最小周期，未宣称全互连TT250签核。
4. **外存能量**列4／6.6／8pJ/bit条件值，覆盖全部访问字节；原生外存时序不等于实测LPDDR功耗。完整NoC、PHY、时钟树和物理CIM读出接口仍不闭合。

覆盖面积约22.59mm²**不是最终die面积**，也不能与100MHz旧资源的52.62mm²直接做“提频省面积”因果比较：本版同时减少了FFN核、数字池、PV和归约资源。所有55等效面积已单次×0.81，不再重复乘。

## 运行与复核

```text
python -B run.py --runtime <冻结runtime> --dependencies <冻结dependencies> --inputs <已有捕获输入> --backend native --scope full --cores 3 --seed 17 --out <新输出目录>
```

运行入口是本目录run.py。--scope可选full／layer／prefix／ffn，默认full。需要受控存储中的既有runtime及dependencies，SHA见INTEGRATION_SOURCES.json；本目录不复制公开旧私有输入、库、权重或大型轨迹。Windows本地验证用--backend analytic；原生Linux CPU任务使用已有liblpbridge.so与配置。运行后产生RESULT.json、BUDGET.json、SEAL.json。

本地结果见LOCAL_RESULTS.json和VALIDATION.json；来源见INTEGRATION_SOURCES.json；当前执行状态见ASSEMBLY_STATUS.json。MODULE_CATALOG.json及CATALOG_README_20261107_ZH.md保留原“仅证据目录”的历史，不再代表当前接合状态。原生完整结果收齐前，整机时间/能量/功率字段保持null。

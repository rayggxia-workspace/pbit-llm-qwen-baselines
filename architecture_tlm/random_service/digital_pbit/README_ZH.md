# 数字p-bit统一调用与PPA目录

2026-10-30，接续Issue95。这里将已完成的8位比较器、Sigmoid表及融合输出端标定整理为独立可调用组件；**不改变现有随机服务或完整TLM默认**。

先看[单路实际结果及128节点方案表](RESULTS_ZH.md)。完整五种活动模式、SS/TT、内部/切换/泄漏在[catalog.json](catalog.json)。原始小型汇总按字节保存在[evidence](evidence/38427136_SUMMARY.json)，运行时核对SHA。

## 三种使用方式

| 接口/结构 | 输入 | 保存与更新方式 | 已有证据 | 适用情况 |
|---|---|---|---|---|
| 已有概率直接比较 | q8或q9、R8 | 由调用方保持q；组合输出 | 独立LT8、q/256比较器实际PPA | 上游已得到概率，避免重复Sigmoid |
| 每节点完整LUT＋比较＋输出bit寄存 | signed8局部场、R8 | 无额外概率寄存；采样边沿寄存结果 | `pbit_sample8_reg`实际单路PPA | 每拍并行新输入；或上游已有稳定x |
| 共享M张LUT＋N组8/9位阈值缓存＋比较＋输出保持 | LOAD阶段提供局部场，SAMPLE阶段提供R8 | 先装满阈值缓存，再并行采样 | **组合估算**；8/9位独立缓存阵列PPA尚缺 | 阈值少改多用、可接受准备周期；需同时核算存储/时钟 |

本地LUT不会保存128节点的输入。全复制方案若同x采K次，x必须由上游寄存器/SRAM等保持；其面积/能耗在上游付一次，不能因本目录未计就当作免费。共享方案将概率持有在本地缓存，LOAD后上游x可释放。若两种方案的输入保持条件不同，要先补齐同边界存储再比较。

## 数字合同

- 局部场码`c`是**signed8整数[-128,127]**，实际log-odds为`c/8`。表输出`q=round(256*sigmoid(c/8))`。
- 输入必须是局部场码，不是g/u按共享幅度尺度编码后的绝对值。浮点/定点恢复、RNE、饱和、尺度和输入转换由调用方执行并计价。本目录不悄悄更改数值合同。
- 比较为`R8<q`，R8是外部提供的0..255整数。q9范围0..256，精确包含概率0和1；仅q8存储时不能保存256。
- 要严格8位阈值缓存，须显式`storage_bits=8, clip_p1=True`，将q=256裁成255，概率1变成255/256。最大端点误差1/256；这里不把9位存储偷偷叫8位。
- 若需要`P=(1+tanh(h))/2`，上游应构造log-odds`2h`，再按此合同形成码。不能把sigmoid(h)当作同一函数。
- 本目录不生成随机数。每次sample显式传N个R8，不能把广播同一个字默认当N路独立随机输入。GF64有已知联合秩限制，Attention不得因成本低就自动采用。

## Python调用

在仓库根目录执行，Python标准库即可：

```python
from architecture_tlm.random_service.digital_pbit import (
    Catalog, ThresholdBank, compare8, sigmoid_code,
)

q = sigmoid_code(0)             # 128，即P=1/2
assert compare8(127, q) == 1
assert compare8(128, q) == 0

# 原始单路标定。返回瓦、raw/equivalent面积和频率证据等级。
c = Catalog()
measured = c.component("pbit_sample8_reg", corner="tt")

# 全复制128路，每拍更新局部场；复制预算，不是实际128路阵列PPA。
full = c.estimate_window("full_lut", nodes=128)

# 8张表服务128路，每个概率保持64次采样；默认q9保留p=1。
shared = c.estimate_window(
    "shared_lut_cached", nodes=128, lut_lanes=8,
    samples_per_configuration=64, corner="tt", clock_mhz=100,
)
assert shared["load_cycles"] == 16
assert shared["total_cycles"] == 80
assert shared["effective_per_node_Msample_s"] == 80

# 全复制方案重复使用x时，必须显式承认上游确有输入保持。
full_reused = c.estimate_window(
    "full_lut", nodes=128, samples_per_configuration=64,
    inputs_held=True,
)

# 功能参考只消耗调用方给的随机字；configure返回需付的LOAD时钟数。
bank = ThresholdBank(nodes=128, lut_lanes=8, storage_bits=9)
load = bank.configure([0] * 128)
bits = bank.sample([127, 128] * 64)  # 示例固定字，不是质量合格随机源

# 若明确接受概率1裁剪，才选择真正8位阈值存储。
q8 = ThresholdBank(128, 8, storage_bits=8, clip_p1=True)
```

`ThresholdBank`是事务级参考：`configure`代表一次完整、原子的LOAD阶段；调用方须在自己的时间线上推进返回的装载拍数，再发起SAMPLE。它不是新RTL、没有隐藏并行装载、队列或随机源，也不把Python运行时间当硬件时间。

## 功耗、面积怎样计

### 已测单路

已有38427136完成10设计、150个门级/PT窗口，SS1.08V125℃、TT1.2V25℃，100MHz、三seed17/503/1009，输出负载0.001pF。均报告setup/hold非负；TT部分核有最小ramp边界的库表告警。仅布局前、零延迟门级活动，无CTS/SDF/SPEF和完整毛刺。

原面积保留。项目等效55nm面积`A_equiv=A_raw*0.81`只乘一次；不改变原PVT，不缩放功率、能量或频率。目录输出是**单元面积**，不是宏物理占地；空白/布线/IO另计。

融合核已经包含LUT、比较和bit/valid输出保持，不可再添加同一份LUT或比较器。现有PRNG服务端点也包含比较/保持/控制：采用整端点时应只补缺失的LUT，不能再加整份融合采样核。完整随机源、种子、调理、CDC、局部场MAC、输入转换与上游存储另计。

### 共享缓存组合估算

当前没有同边界的8/9位阈值阵列实测。`estimate_window`只提供可追溯代理：

```text
A_q_proxy = A_registered_LUT - A_comb_LUT
A_bit_proxy = A_fused_sampler - A_comb_LUT - A_compare
A_shared = M*A_LUT + N*(A_q_proxy + A_compare + A_bit_proxy)
```

q代理含9位q、valid、使能/复位和综合映射差异；不是单独8位寄存器价格。即使选q8，也沿用同一代理，不按8/9比例伪造省面积/功耗。写地址译码、输入选择器、bank布线及真实ICG新增开销**尚未标定**，结果不能当完整宏PPA。

功耗按明确阶段计费：所有缓存和输出保持使用free-running CE时钟，无ICG优惠。保留实测idle功耗；操作只加扣除idle后的增量，避免重复加静态/时钟。q/bit保持使用同样的映射残差。

```text
P_idle = M*P_LUT_idle + N*(P_q_proxy_idle + P_compare_idle + P_bit_proxy_idle)
E_window = P_idle * (LOAD+SAMPLE)*T
         + N*E_LUT_increment + N*E_q_load_increment
         + N*(K+1)*E_compare_increment + N*K*E_bit_capture_increment
```

共享加载时q改变也可能引起组合比较器活动，因此额外计N次配置比较。全复制无q缓存与LOAD段，同输入K次时只计一次LUT变化查询、K次比较与bit采样。任意固定q的比较活动未单独扫描，代理仍用random比较活动预算，不将fixed50低活动推广给所有q。

这使共享LUT通常省逻辑面积，但若q缓存一直跑时钟，能量未必优于上游已有x保持的组合表。低频更新可以考虑真实ICG/锁存，但应补8/9位阵列功耗再替换代理。已有[12/16位真实ICG相关试验](../../attention_compare_20261027/regbank_20261029/REPORT_ZH.md)保留hold/库表告警，不按位宽直接折成已测8位。

## 频率、延迟与吞吐

实际单路标定只有100MHz。它是已测试约束点，不是最大频率，不能由正slack直接推500MHz成立。`component`允许100MHz以下的动态功率比例投影、保留泄漏；其它频率均标明投影。大于100MHz默认拒绝，必须显式`allow_above_reference=True`才做代数外推，仍不取得时序认证。

共享方案M路表每拍处理M个场，装满N路需`ceil(N/M)`拍；之后每拍并行采N位，采K拍。未实现预取、双缓存和LOAD/SAMPLE重叠：

```text
首输出延迟 = ceil(N/M)+1 拍
窗口总拍数 = ceil(N/M)+K
每节点平均输出率 = f_clk*K/(ceil(N/M)+K)
```

128节点、8表、K64、100MHz：LOAD16拍/SAMPLE64拍，总800ns，首输出17拍；平均每节点80MS/s，采样阶段为100MS/s。K1则只有约5.88MS/s，不能只报SAMPLE阶段的100MHz。

LOAD端口须真实提供M个8bit场/拍（M8为64bit/拍）；全并行更新128路则需128个场/拍。R8供给在SAMPLE阶段每拍需128个字，1024bit的接口需求不等于1024个独立物理熵bit。供给延迟和联合随机质量由上游服务决定，不在此处假定免费。

已有单核`pbit_sample8_reg`无ready/反压，在有效边沿捕获输入并输出bit/valid。接入有回压服务时，要保证空间或加输出保持协议；旧`rng_ffn_shared64`的held_q还承担事务对齐，不能直接删除后接当前输入。

## RTL入口与验证

复用[既有五核RTL](../pbit8_char/rtl)，不复制、改名或重写冻结源。当前共享缓存是预算/事务参考，尚无新阵列RTL/PPA，不将Python类称为硬件验证。

```sh
python -m unittest architecture_tlm.random_service.digital_pbit.test_model -v
python -m architecture_tlm.random_service.digital_pbit.report
python -m architecture_tlm.random_service.digital_pbit.report --write
```

测试覆盖概率端点计数、signed8合同、现有表一致性、源SHA、单路标定复现、面积只折一次、装载吞吐、输入保持与q8损失确认、能量闭合及未验证频率拒绝。它们不代替阵列STA、PVT/实际模型活动或联合随机质量验收。

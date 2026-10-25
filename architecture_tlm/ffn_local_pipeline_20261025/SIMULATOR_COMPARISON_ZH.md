# 成熟模拟器、读取复用与速度差异：只读核查说明

2026-10-25；Issue186 / PR190 参考材料。本次只核查固定源码和已封存结果，没有新跑性能、修改上游或重新下载环境。下文不预测尚未实现优化的提速倍数。

## 1. 为什么成熟模拟器看起来更快

**既有对照同时包含硬件资源差异和模型抽象差异，不能全部称作“调度更好”。** LLMCompass 的 B1 投影快捷路径不展开共享 SRAM；普通 tile 路径则确实计入复用和双缓冲。ONNXim 可提供更明确的指令依赖，但也不是所有片上带宽细节都已建模。

| 路径 | 固定源码的实际做法 | 对我们的启发与限制 |
|---|---|---|
| LLMCompass，M=1 GEMV | 时间取计算与外存时间的较大值；输入、权重、输出各计一次逻辑传输；不进入 tile 搜索，不检查 L2 带宽 | 接近理想持续供数预测，不能据此证明共享 SRAM、DMA、本地端口已能满足吞吐 |
| LLMCompass，普通 tile | 相邻 tile 共享 A/B 时免重复读取；共享输出 C 时保留部分和；双缓冲重叠读取和计算 | 这些是可以实现的复用机制，但映射到相同 core、容量和供数条件仍需成立 |
| ONNXim，GemmWS | tile 内激活只在首个输出块 MOVIN；跨 C/reduction 块保留 accumulator；最后 C 才 MOVOUT | 支持“输入复用＋部分和本地驻留”，并不要求每个 K64 块都写回共享 SRAM |

LLMCompass 固定版本 `2e015fd2ee750e6cad8d7152df52551e5b41ef20`：

- [matmul.py:285–306，GEMV 快捷路径](https://github.com/PrincetonUniversity/LLMCompass/blob/2e015fd2ee750e6cad8d7152df52551e5b41ef20/software_model/matmul.py#L285)：`max(2MKN/计算吞吐, 数据字节/外存带宽)`；本地已运行合同测试，将 L2 带宽改为 1 B/拍时返回时间不变。
- [matmul.py:917–952，L2 tile 复用和双缓冲](https://github.com/PrincetonUniversity/LLMCompass/blob/2e015fd2ee750e6cad8d7152df52551e5b41ef20/software_model/matmul.py#L917)：相同 `(m,k)` 复用 A，相同 `(n,k)` 复用 B，相同 `(m,n)` 保留 C；流水时间不是把全部读、算、写简单串行相加。
- [matmul.py:1229–1288，L1 批次复用](https://github.com/PrincetonUniversity/LLMCompass/blob/2e015fd2ee750e6cad8d7152df52551e5b41ef20/software_model/matmul.py#L1229)：根据前后批次的张量 tile 消重，读写按共同 L2 带宽收费，并假设可把复用数据映射到相同 core。

ONNXim 固定版本 `8599bee46b311fb267ac34b0677ad7db3d8a8ccd`：

- [GemmWS.cc:46–64](https://github.com/PSAL-POSTECH/ONNXim/blob/8599bee46b311fb267ac34b0677ad7db3d8a8ccd/src/operations/GemmWS.cc#L46)：按 batch N、输出 M、归约 C 生成 tile；`C != 0` 标为累加。
- [GemmWS.cc:181–207](https://github.com/PSAL-POSTECH/ONNXim/blob/8599bee46b311fb267ac34b0677ad7db3d8a8ccd/src/operations/GemmWS.cc#L181)：仅 `Ms == 0` 发激活 MOVIN，在 tile 内跨输出块复用。
- [GemmWS.cc:254–292](https://github.com/PSAL-POSTECH/ONNXim/blob/8599bee46b311fb267ac34b0677ad7db3d8a8ccd/src/operations/GemmWS.cc#L254)：最后一个归约 C 块才写出结果。

## 2. 现有原生探针证明了什么

以下都是已有的四 tile 合成探针，每项合计读取 1024 B、写出 512 B。数字为原生 8×8 WS；SC 仅替换计算忙时为显式宏，无数值载荷。

| 计算服务 | 双 tile 入口 | 单 tile 入口 | 双 tile、冲突 bank |
|---|---:|---:|---:|
| 原生数字 WS | 121 拍 | 221 拍 | 176 拍 |
| SC 忙时 64 拍/tile | 282 拍 | 329 拍 | 302 拍 |
| SC 忙时 128 拍/tile | 538 拍 | 585 拍 | 558 拍 |

这说明在相同数据量下，重叠和 bank 排布能影响完成时间；不代表完整 Qwen 或同面积数字/概率芯片的性能对比。探针外存是合成有限服务，没有接入 DRAMSys；原生 Sram 主要管理容量与 valid，并未展开完整 SRAM bank 仲裁。现有探针人工构造各自独立的 tile，**没有验证 GemmWS 生成的跨 C 驻留路径**，这部分目前是源码依据。

结果入口：`architecture_tlm/unified_v6/results/scheduling_20261025/native/RESULT.json`；接口与限制：`probes/onnxim_native/README_ZH.md`。原生单/双 PRELOAD 的既有参考分别为 39/47 拍，不能与本表含搬运的四 tile 总周期混用。

## 3. 每次读取到底复用了几次

**B1 decode 中，一个权重对应一个有效乘积。数字和随机方案的“有用权重复用”都是 1；随机方案把这一个近似乘积展开成 T 次采样事件。** 只要权重能本地保持，就不需要 T 次外存读取；但 T 次事件不是 T 个独立有效 MAC。

| 对象 | 应分别统计的量 | 当前结构示例与硬件成本 |
|---|---|---|
| 权重 | 有效乘积/权重装入次数；采样事件/权重装入次数 | 数字 B1 为 1；SC 为 1 个近似乘积、64/128 次事件。必须提供本地保持、驱动与装载接口 |
| 输入 x 或非线性流 | 物理读数、操作数消费数、空间扇出、跨波重放次数 | 8×64 阵列一次广播最多512输出；GU有38个输出波，Wd有5个。广播树和重放状态不能当零成本 |
| 时间计数器 | 每帧 T 次本地更新、帧末读出 | 当前已经本地累计随机事件，不保存 T 份结果，也不是每拍写共享 SRAM |
| 跨 K 部分和 | 本地合并的 K64 块数 R、共享写回窗口数 | GU共40块、Wd共152块；R8跨8块再写回。512输出×64位＝4KiB局部状态，另计累加器和端口 |

当前已封存默认实际为 GU64、NL/Wd64；NL/Wd128是允许的扫描配置，不能未经核对把所有既有结果标成128。

若输出数为 O、K64 块数为 G、保留 R 块，64位部分和的共享读写量为：

`O × 8字节 × (2 × ceil(G/R) − 1)`。

初始零不必读，最后结果仍需写。Qwen3-4B每层 GU＋Wd 合计：R1为17.645MiB，R8为2.059MiB，全K为0.168MiB。这是已经实现并统计的部分和流量；总权重仍需搬运，不能把部分和节省比例当成整机提速比例。当前本地驻留还需要输入码窗口及随机起点状态，不能只计4KiB部分和。

现有 `model.py:342` 的 `digital_local_activation_read_byte = K×N×输入字宽` 按 MAC 消费量计数，尚未展开广播后的物理 RF 读取。新对照应分列 `activation_operand_uses`、`activation_RF_reads` 和 `broadcast_fanout`，不直接将每次消费都按 SRAM 读单价收费，也不追改已封存原结果。

## 4. 怎样解释“带宽利用率提高”

应分开报告三种变化：①读取字节减少（复用/驻留）；②相同字节更连续、更多在途或更少 bank 冲突（有效带宽提高）；③相同搬运与计算更充分重叠（关键路径缩短）。三者不能混为一个利用率数字。

公平对照应使用相同外存、容量、bank/端口和相同数据范围，数字与随机都允许输入广播、双缓冲及部分和驻留；再列不同本地状态、计算阵列和恢复通路成本。LLMCompass GEMV可作为理想持续供数参照，ONNXim probe可检验依赖和回压，但都不能替代这些具体接口条件。

本地现有说明：`architecture_tlm/unified_v6/LLMCOMPASS_COMPARISON_ZH.md`、`SCHEDULER_RESEARCH_ZH.md`、`FFN_LOCALITY_ZH.md`。本文件的参考根为 `C:/Users/86134/Documents/a_P_BIT/tmp/mature-scheduling-issue186-20261025/`。

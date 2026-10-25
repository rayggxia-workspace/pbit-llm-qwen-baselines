# 成熟模拟器调度借鉴与历史工作核对

2026-10-25后续实跑：LLMCompass官方固定源码的Qwen3-4B完整算子图适配已完成，见[五配置对照](LLMCOMPASS_COMPARISON_ZH.md)。投影走其原生GEMV解析分支，GQA QK/PV与Softmax走原生tile映射，Qwen专有向量过程用明确宏补齐；不是完整周期精确Qwen移植。下方“LLMCompass仅借鉴”的内容描述早一轮共同调度实现，现由此新增实跑证据补充。

Issue186，2026-10-25。固定 revision 见 `SCHEDULER_SOURCES.json`。正确名称是 ONNXim；ONNXsim 是另一个图简化工具。本轮不接管 #116/#123 用户暂停的工作。新出现的 #187 由 rayggxia 负责广泛论文证据矩阵，与本任务实现和运行范围分开。

## 采用什么、没有采用什么

| 来源 | 可借鉴机制 | 本轮使用边界 |
|---|---|---|
| [ONNXim](https://arxiv.org/html/2406.08051v1) | Core 两 tile 入口、双缓冲、输入 valid 后执行、最终 MOVOUT、返回回压 | 在我们的执行器中独立实现共同 tile 生命周期；上游原生小 probe 单列证据，不声称完整 Qwen 已在 ONNXim 执行 |
| [LLMCompass](https://arxiv.org/html/2312.03134) | 多级 tile、循环顺序、复用、双缓冲候选 | 借鉴“产生候选→同一执行模型重新计时”；没有套用其带宽 roofline 为实际 DDR4 时延 |
| [SCALE-Sim](https://arxiv.org/html/2504.15377v1) | 阵列时延、scratchpad 预取与 demand stall | 可用于之后的数字阵列交叉校验，本轮未运行，不把文献公式当本次测量 |
| [Timeloop](https://github.com/NVlabs/timeloop) / 既有 ZigZag-LOMA | 容量约束下搜索分块、空间/时间映射与动作数 | 当前做有限候选扫描，不宣称全局最优，也没有执行任意循环重排 |

ONNXim 的 Core.cc 使计算等待源数据有效；GemmWS.cc 将矩阵转成 MOVIN、GEMM_PRELOAD、累加和最终 MOVOUT；Mapping.cc 是 Gemmini 派生容量启发式。Simulator.cc 保留 core / NoC / DRAM 的交互与回压。但其 Sram.cc 的 cycle() 为空，主要记录容量、返回数和 valid；SimpleInterconnect 的有限 buffer 仍有 TODO。把整个项目搬来不会自动给我们完整 SRAM bank 时序。

本轮共同调度保留真实 DRAMSys、已有 SRAM 约束和随机服务接口。一个 pending DMA response、两个共享 SRAM slot、一个 active operand tile；下一 DMA 可以覆盖当前计算，但下一次 SRAM fill 在当前 tile 退役后才开始。同步 DRAM actor 不能倒退时间，所以不能对已完成的请求再进行“回到过去”的任意乱序插空。

## 为什么不直接给 ONNXim 换一个模型配置

- 最新 ONNXim `8599bee...` 刚修复 KV-head 寻址。旧 MHA 可能一直读 head0，旧 GQA 会漏读后面的 KV heads；旧版本不能作为当前 GQA 金标准。
- LanguageModel.cc 从 hidden/heads 推导 head_dim；本项目 Qwen3-4B 的 head_dim=128，而 2560/32=80，直接传配置会生成错误 QKV/O 形状。
- 全局 precision 与默认 4 B accumulator 不能直接表达 W8/BF16/64位部分和混合边界。
- SystolicWS 的 SWISH 延迟仍有 TODO；SystolicOS::cycle 是 TODO+assert，其旧 OS 测试体被注释。不能把空测试或占位激活称为支持。
- 我们的 Attention 地址取决于真实采样完成；候选生成、拒绝、去重、GQA 合并和随机服务回压都需要显式依赖，不能用平均采样次数直接提前读取 V。

这些是代码适配问题，不代表成熟调度不适用。我们先把可验证的共同机制抽出来，再保留现有数制和采样的真实边界。

## 数字 WS 时延的可核对公式

ONNXim SystolicWS.cc 对 H×W 阵列、compute_size=m，计算段为 `H+W-2+max(m,4)`；空流水线的首条 PRELOAD 另有 `2H-1`。流水线非空时，PRELOAD 的启动间隔为 `max(previous_m,4,H)`，非 PRELOAD 为 `max(previous_m,4)`。

64×64 下，孤立首条从进入执行段到结束，m=1/16/64 分别是257/269/317拍。这是源码公式，尚不包含发射与依赖唤醒的一拍差、MOVIN/MOVOUT、DRAM、NoC、非线性等。不能给每个K块都串行重复加首条127拍，也不能再把同一次本地weight preload完整重复计入。

M=1 decode 并不能利用所有4096个PE。因此原生WS适合作为“具体阵列”的锚点，不能冒充所有数字ASIC的最优GEMV。主对照继续保留显式的512 MAC/周期宏，并标明未经过同工艺RTL/STA校准；不会用低利用率WS刻意削弱数字参考。

## 之前 GitHub 已经做过什么

| 任务 / 已发布版本 | 实际完成边界 | 本轮怎样使用 |
|---|---|---|
| #117 / PR119，merge `8c137a4ecb4c134997fc6b21ac6cbf30c92ef6ff` | 208项合成decode与容量负例；保持映射时增容量不改变时间 | 继承“容量变化不自动等于性能提高”的约束 |
| #118 / PR120，merge `2630aa2627257a1632b105ec2b99c6f3d708560f` | 权重状态48KiB→5KiB，30tests/66整数案例；不是PPA倍率 | 参考状态生命周期，不复制旧FFN数值边界 |
| #116 / PR126，merge `f50d3147ab7a4daa43cce52a4037168203bba3aa` | 旧ONNXim原生WS 39/47拍，4个原生Operation/Tile小probe；有限外部服务，没有完整2K/8K Qwen | 证据保留，最新源码重新核验；旧FFN为连续SiLU→z，不是当前AND直入Wd |
| #123 / PR125，merge `b51d347cc1fa59d00eb2f84c14ea27a3fe4757c0` | 已发布阶段代码和120项payload检查，长实验用户暂停 | 不恢复暂停作业，不继承其完整系统结论 |
| 早期ZigZag-LOMA，`00c12466b8ca8095352f2be28ba02608cf399286` | 54个合法映射/624候选，16项真实DRAMSys；loop prefix影响连续DMA粒度 | 复用候选生成和重新计时方法，不继承旧Qwen0.5B/T4096/存储配置结果 |

上述 PR 是合入历史 TLM 分支，不是自动合入 main。旧2K周期工作仅构图、没有完成完整运行；小形状成功不等于大型模型成功。

## 本轮比较的约束

固定资源表比较相同模型、DRAM、共享SRAM、算子边界；数字/SC都允许同样的DMA预取。再扫描32/64/128/256KiB数字行tile，分别用于数字与SC整机；独立扫16/64 SC阵列时明确改变了硬件规模。SG深度16/64/256也单列。三seed用于主要概率配置，单seed参数扫描仅作资源试探。

每个数字tile隐含的本地权重/激活存储现在显式报告。局部512-lane供数、互连和控制PPA尚未标定；不会把这些存储当免费。当前K外层映射保持随机序列复用，但需要宽部分和SRAM读写。改变为output-stationary或融合GU/down会改变输入重读、随机重放和部分和，必须另做映射及数值验证，不能在本轮只改循环顺序就省去成本。

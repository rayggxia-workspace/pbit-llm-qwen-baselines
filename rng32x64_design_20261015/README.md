# 单个32位LFSR供给64路随机字的设计原型

本目录实现四个可核对的SystemVerilog草案、代数证书和合成数值实验。核心是共享线性网络；512位输出不代表512位独立熵。

| 文件 | 内容 |
|---|---|
| `design.py` | 构造候选、搜索状态位连线、验证LFSR周期、测试短流、生成RTL |
| `check_design.py` | 检查有限域、矩阵秩、固定映射门数下界，以及生成RTL表达式 |
| `results.json` | 8个训练种子、16个留出种子的结果与逻辑计数 |
| `manifest.json` | 默认8位快速方案的映射矩阵、状态位排列、源和比较规则 |
| `reference_vectors.json` | 默认方案参考状态与64路输出字 |
| `checks.json` | 检查结果及其适用边界 |
| `rng32x64.sv` | 64×8位，两两联合满秩；输出516个XOR2、4层 |
| `rng32x64_area.sv` | 与默认方案完全相同的随机字；输出504个XOR2、6层 |
| `rng32x64_threewise.sv` | 64×8位，任意三路联合满秩；输出605个XOR2、8层 |
| `rng32x64_twelve.sv` | 64×12位，两两联合满秩；输出779个XOR2、7层 |

所有模块另有32位状态寄存器，以及本次选用的16步展开更新网络：61个XOR2、7层。表内输出网络不含这61个门，不含64个比较器、seed/enable/reset控制、时钟树与布线缓冲。它们是结构计数，不是工艺综合面积或功耗。

完整分析：[设计与数学推导](C:/Users/86134/Documents/a_P_BIT/pbit_llm_master_report_20261012/RNG32_TO_64_DESIGN_AND_PROOFS_ZH_20261015.md)。

## 运行

依赖Python与NumPy；不用GPU，不会加载或改写Qwen模型。

```powershell
& 'C:/Users/86134/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' 'C:/Users/86134/Documents/a_P_BIT/rng32x64_design_20261015/design.py'
& 'C:/Users/86134/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' 'C:/Users/86134/Documents/a_P_BIT/rng32x64_design_20261015/check_design.py'
```

`design.py`使用固定搜索种子重生成本目录结果。训练目标只使用合成序列，未使用留出种子或神经网络张量。随机连线基线是本地生成的基线，不是对Salehi论文算法的复现。

## RTL接口语义

`random_word`和`stochastic_bit`是当前state的组合输出，比较为无符号`random_word < threshold`；8位阈值Q表示Q/256，12位表示Q/4096，最高码不能表示概率1。消费者只在`enable && !seed_load && rst_n`时接收/计数。当enable关闭时state保持，组合输出可以仍为0或1，不能继续计数。

复位装入1。`seed_load`优先于enable，零seed被替换为1。逻辑上每次使能执行16步LFSR转移，硬件是并行展开的组合网络，不要求LFSR时钟为计算时钟的16倍。跨tile是否保持源状态或重装seed由外部调度决定，manifest应固定该规则。

默认方案的跨路、跨拍秩检查覆盖word lag 1、2、4、8；不代表检查了所有滞后。其结论仅适用于默认映射，不能直接转给另两个生成器。

秩保证指均匀32位状态下的联合分布；最大周期LFSR不访问零状态带来的事件概率偏差至多1/(2^32−1)。这不保证任意256或4096拍片段精确，也不保证自适应阈值与源状态独立。

`check_design.py`读取生成RTL，核对其直线XOR、连线、比较和next_state表达式，另检查控制优先级结构。尚未运行HDL编译/仿真或单元库综合，不能由检查通过推断PPA或Qwen PPL。

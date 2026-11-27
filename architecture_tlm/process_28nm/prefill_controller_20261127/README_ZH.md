# Prefill 控制原型：驻留权重复用与带行号的部分和

Issue225 / PR266，独立于现有 decode 默认配置。此目录实现并验证控制机制，不修改上游概率计算、Attention 或随机源模块。

## 一次任务怎样执行

```
16项命令FIFO → 组/K块依赖表 → 空闲CIM核
                               ↑ DMA加载8KiB权重
                               ↓ 同一权重连续处理1～32行输入
                       每核双结果槽（128路21位）
                               ↓ 4个32路结果beat
                   token行号 → 两路交错bank部分和流水线
                               ↓ 全K块完成 → 释放状态租约
```

一个矩阵阶段命令包含 GU/Wd 类型、采样数、输入行数、输出组数、K块数、权重基址、公共定点指数、任务标签与可用核掩码。命令满时 `valid/ready` 等待。每个输出组最多占用一个32行状态租约；不同组可并行，下一K块等待该组所有行的四个结果beat提交。计算核可动态分配，不永久绑定输出组。

每核仍是一块8KiB、16个32×128bit bank 的单权重区。加载一次权重后处理多行输入；每行结果进入双结果槽，最后一行被捕获时释放CIM。后续累加回压由结果槽承担，不能提前覆盖仍在计算的权重。Wd输入在接收握手时锁存，以满足上游阈值寄存器在下一拍LOAD的时序。

DMA复用现有共享16KiB返回池与4路64B事务端口。发出读请求前分配credit，数据写入CIM后归还；外部返回可乱序。取消停止新任务，冲刷计算/状态流水线，并排空已经承诺的外存请求再完成。该接口带宽是实现的端口能力，不能直接等同于LPDDR峰值。

## 状态SRAM组织

两路worker各32个64位累加通道，每路两个交错bank集合，每集合16个128bit、256行的1RW bank：共64×4KiB=256KiB。槽号为 `(group % CORES) × 32 + token_row`，行奇偶选择worker；槽中128个64位状态占1KiB。

流水线为同步读→指数对齐→加法→写回。读写同bank集合或同一状态地址仍在流水线中时暂停输入；输出回压冻结流水线。正确交错时每路II=1。六核最多192个有效状态槽，物理配置保留256槽。GU/Wd局部采样保持整数计数，未切换FP24候选。

## Prompt级控制

`prefill_prompt.sv` 先遍历所有prompt块的embedding，再逐层遍历这些块，最后仅对最后prompt位置发出final norm/LM head任务，得到decode起始位置。它通过服务命令及完成握手工作，取消时排空已接收服务。

此sequencer与矩阵阶段控制器分别验证；二者间的完整层任务展开、数字Attention/GEMM执行与统一激活物理映射尚未接成完整prefill Decoder。测试中的GU/Wd输入是合成定点码，通过原有真实RTL采样、门控和整数累加。检查采用实际事件的独立整数oracle，没有用理想FP32算子替换核输出。

## 使用方法

Python3.10+；通过 `--rtl-root` 指定现有 `rtl_stage2_integration_20261121` 依赖包。构建脚本读取外部Verilator/C++工具链，不复制工具或编译产物到Git。

```powershell
python -B tools/build.py --kind state --rtl-root <RTL包目录>
python -B tools/build.py --kind prompt --rtl-root <RTL包目录>
python -B tools/build.py --kind matrix --rtl-root <RTL包目录>
python -B tools/run.py
```

实际结果、命令、依赖源码SHA及边界见 `REPORT_ZH.md`、`results/RESULTS.json` 和 `results/RUN_MANIFEST.json`。这是RTL功能与周期验证；未综合、STA、PT或测量整机功耗，250MHz换算不等于时序收敛。

# ONNXim 实际接入试验

Issue116，2026-10-23。已在本人 5090 集群的 **CPU-only Slurm allocation** 内编译 [ONNXim 官方仓库](https://github.com/PSAL-POSTECH/ONNXim/tree/a1e86296e080fa1c82f8ad3f1b6de1079c192afc)，执行两个官方小例，并将一个自定义复合 Operation 接入原生 Tile / 指令 / Core / SRAM 依赖路径。最终作业 **2772，COMPLETED，ExitCode=0:0**。

这达到方案中的外部框架实际构建、官方小例和最小自定义操作探针阶段。不是完整 SC 算子、数值随机采样、整层迁移、全模型迁移或两个模拟器逐周期一致性证明。

## 可检查结果

官方 `SystolicWSTileExecutionTest` 与 `SystolicWSTwoGemmExecutionTest` 保持原有断言，分别通过 39 / 47 cycle 的原生 GEMM 小例。没有把整个官方测试集标为通过。

`PBitThresholdTransportProbeTest.cc` 派生真实 `Operation`，生成一个非 skip 的 Tile：两个 32-byte MOVIN 请求 → 64-byte COMP → 一个 32-byte MOVOUT 请求。Core / SRAM 分配、数据到齐依赖和 vector pipeline 由 ONNXim 原生实现决定。不是未知 ONNX op 的 Dummy 跳过路径；未注册完整 ONNX graph parser 自定义节点。

| 场景 | 外部窗口 | 内存延迟 | 向量位宽 | COMP active cycles | 完成 cycles | 拒收 cycles |
|---|---:|---|---:|---:|---:|---:|
| baseline | 8 | 2 | 64 bit | 8 | 17 | 0 |
| bounded_long_memory | 1 | 11 | 64 bit | 8 | 45 | 10 |
| out_of_order | 8 | 第一读11、第二读2、写2 | 64 bit | 8 | 25 | 0 |
| narrow_vector | 8 | 2 | 32 bit | 16 | 25 | 0 |

每例验证两读一写只接受/返回一次、请求 ID 与地址守恒、拒收时队头保持、窗口峰值受限、写请求晚于全部读返回、非 skip Tile 完成、watchdog 不触发。乱序例实际返回地址为 `0x1020 → 0x1000`。减半向量宽度增加 8 个原生 COMP 活跃周期，并使完成时间增加 8 周期。

## 精确边界

- 这是 ONNXim **计时/依赖** 操作。其 SRAM 保存有效性与请求计数；本探针没有数值 payload，因此不验证比较结果或 FFN/Attention 数值质量。
- 内存端是测试中明确实现的有限请求窗口、每拍一接收/一返回服务，不是 Ramulator、DRAMSys 或 DDR 命令模型。框架本体及所含模块已编译，不等于这些后端在本探针被执行。
- 外部响应先提交，随后 `core.cycle()`，最后接新请求，允许同沿返还窗口后再接收；原生 Core 内部也可能 finish 后 issue。这与本项目 cycle_v1 的严格 old-state/no-bypass 默认契约不同，不能直接比较总周期并声称一致。
- 有限窗口限制外部在途 descriptor，未把 ONNXim 内部请求队列改造成有限队列。完整 SC/随机源/采样计数/多时钟迁移仍需额外资源与协议模型。

## 构建和证据

固定源提交为 `a1e86296e080fa1c82f8ad3f1b6de1079c192afc`；主源码 archive SHA-256 为 `9e0923da0a5c29cf7def7d3679ecae5106f58cf901d482e98010d79da5f04323`。Conan 1.57、私有 cache、8 CPU、`CUDA_VISIBLE_DEVICES=""`。GitHub 依赖下载不稳定时，将官方 archive 经 SHA-256 与 recipe 对照后上传，只在 allocation 内以 `127.0.0.1` 临时镜像服务；只改本人 cache 的源 URL，保留源散列，退出时关闭服务。

GCC13 需要两个局部兼容性修正：Ramulator1 `StatType.h` 显式包含 `<cstdint>`；老 GoogleTest 的栈地址探针 `int dummy` 初始化为 0。它们没有改计时或数值算法；2770 / 2771 / 2772 source-edit 收据保存前后散列。另将 GoogleTest 下载指向同 SHA 本人 archive，并通过 CMake 显式指定已有 vendor 源。

恢复历史完整保留：2763 下载超时；2765 发现 Conan Boost 使用整机 `-j64` 后立即取消；2768 缺 `<cstdint>`；2770 GoogleTest 编译告警被当作错误；2771 已完成构建但测试路径指向非实际输出目录；2772 正确执行。之后显式设置 `CONAN_CPU_COUNT` 和 `CMAKE_BUILD_PARALLEL_LEVEL` 为 Slurm 分配的 8 CPU。

原始结果位于 `../../results/onnxim_probe_20261023/`；脚本、日志、首次终态、二进制与 source-edit 散列位于 `work/amlink1219/116/framework/`。远端个人成果根为 `/home/Weican_Chen/projects/tlm-cycle-issue116-20261023`，二进制保留在其 `ONNXim-archive/build/bin/`；依赖 archive / 环境不上传 Git。

仓库根目录可离线核验下载结果及状态：

```bash
python architecture_tlm/cycle_v1/external/onnxim/verify_results.py
```

原生测试命令（需先按保存的 sbatch 完成构建）为：

```bash
./build/bin/Simulator_test --gtest_filter='SystolicWSTileExecutionTest.*:SystolicWSTwoGemmExecutionTest.*'
ONNXIM_PROBE_OUTPUT=/path/to/new/results ./build/bin/Simulator_test --gtest_filter='PBitThresholdTransportProbeTest.*'
```

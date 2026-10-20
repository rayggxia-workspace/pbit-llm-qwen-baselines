# SwiGLU 单通道功耗面积表征

Issue #7 延续任务；独立分支 `task/7-epilogue-ppa100`，基于原 PR #8 的
`dac6e0426da6421ccc62077275e236532ca3c3da`。原运算 RTL 不变。

## 测量边界

- `swiglu_epilogue_q10`，OUT_W=24，16 位 Q10 输入。不是完整 FFN、随机矩阵或 BF16 等价算子。
- 100 MHz；TT=1.2 V/25 C，SS=1.08 V/125 C。以真实标准库 operating condition 核对，不修改电压缩放。
- DC 映射面积是标准单元面积之和，单位 um²，不是 floorplan/core/die 面积。
- VCS 使用综合网表、真实标准单元模型、零延迟功能模式；PT PX 用逐网 VCD。
  不使用 SDF/SPEF，不含真实毛刺、CTS、PLL、pad、外围 RNG/SRAM；不能用本结果证明后端时序。
- 包含模块所有流水线、valid、输出寄存器及其时钟引脚内部功耗，输出负载 0.02 pF/bit。
  `ce` 是数据使能，不把它误称为时钟门控。无强制 ICG/层级保护，不为分组而改变原架构。
- 10 ns 周期，setup uncertainty=2 ns（20%），hold uncertainty=0.1 ns；时钟/输入 slew=0.1 ns；
  输入/输出 delay max=1 ns、min=0.2 ns。都是此次表征假设，不是板级接口约束。
- 理想时钟不含时钟树，布局前线电容由工具/库模型估计；具体环境记录在 DC/PT 报告。

## 场景和能量

每个工艺角只综合/编译一次，随后 18 个场景串行：两种输入分布 × 三模式 × 三种子。
两角默认并行两个 Slurm array task，每个 4 核/8 GB/8 小时，均可覆盖。

| 维度 | 设置 |
|---|---|
| full | g/u 均匀覆盖有符号 16 位；约 75% 的 g 落入 sigmoid 饱和区 |
| central | g 原码 [-8191,8191]，即绝对值 <8；u 同 full；避免大部分 LUT 被饱和旁路 |
| active | 连续 4096 次输入，II=1 |
| burst | 每 256 拍前 64 拍有效，共 1024 次输入 |
| idle | 预热后不接收新输入，时钟继续，输入引脚继续变化 |
| 种子 | 20261017、7、1234567 |

每个场景先复位 4 拍，预热 64 次、排空 8 拍，以上全部排除；随后测量 4096+8 排空拍，
窗口为 [760,41800) ns，持续 41040 ns。默认包含运行开始/最终排空但不含预热。
每拍在下降沿驱动、下一下降沿核对上升沿之后的输出，逐笔核对数值/valid/饱和/舍入标志，
无效周期保持值也检查。端口上的 X 直接失败；测量 VCD 中任何 X/Z 也阻止 PT，不置零掩盖。

`E_window[pJ] = P_total[W] * duration[ns] * 1000`；
`E_output = E_window / 实际完成有效输出数`。吞吐一拍一笔，不把四级流水延迟当成四拍每笔。
同时输出不含 leakage 的动态能量；idle 无有效输出，单次能量留空，不能除以时钟拍数冒充操作能量。
这些是合成事务，不是 Qwen 激活轨迹/PPL，也不能称为最坏功耗。三种子各列原始值，不挑最优种子。

## 上传运行

将 `ffn_epilogue_ppa100_20261017.zip` 上传到个人项目目录，不需要上传 PDK、整个仓库或原始数据。

```bash
source ~/.bashrc
BASE=/public3/home/t6s011227/pbit_chimera_pipeline_20260920
cd "$BASE"
unzip -o ffn_epilogue_ppa100_20261017.zip
cd ffn_epilogue_ppa100_20261017
python3 ppa/package.py --verify .
bash ppa/submit.sh all
```

仅一个角用 `bash ppa/submit.sh TT` 或 `SS`。路径默认复用既有 55nm SC9T BASIC SVT；
找不到/找到多个库时显式提供 `STD_DB_TT`、`STD_DB_SS` 绝对路径，可覆盖 `STD_MODEL`。
例如 `CPUS=4 MEMORY=8G JOB_TIME=12:00:00 bash ppa/submit.sh all`。
提交时复制清单文件到独立 snapshots；已提交任务不受之后解压更新影响。

记录返回 array JOBID，日志位于 `logs/ppa-JOBID_0.out/.err`（TT）、`_1`（SS）。
结果位于 `results/JOBID_0/` 和 `results/JOBID_1/`；无论成功失败都会尽量生成
`results/JOBID_0.reports.tar.gz` / `_1.reports.tar.gz`，下载这两个报告包及 Slurm out/err 即可。
标准单元库/模型 SHA256、脚本源 manifest SHA256、配置和实际工具版本日志都保留。
Slurm 的 COMPLETED 只是程序退出状态；诊断包会保留当前已完成场景，即使后面的场景失败。

同一版本、相同配置/库可指定原路径恢复，完整阶段校验输出 SHA256 后复用；失败阶段保留为 `.failed-*` 再重跑。
必须一次只恢复一个角，不能两任务共用同一结果目录：

```bash
RESUME_WORK="$PWD/results/JOBID_0" bash ppa/submit.sh TT
```

改了脚本、配置或工艺库后不得复用旧目录，重新提交新任务。未授权自动删除任何旧结果。

## 验收与文件

- `configuration.json`：版本、库/模型 SHA256、场景、PVT 与边界。
- `dc/`：网表/DDC/SDC、面积/资源/单元清单、setup/hold/constraint 报告。
- `gate/<case>/`：整数黄金输入、波形、逐周期 PASS、测量窗口和 X/Z 审计。
- `power/<case>/`：PT 逐单元/总功耗、VCD 覆盖率、check_power、时序与库条件。
- `summary.csv/json`：各模式功率、每有效结果能量、覆盖率、slack；`area_breakdown.csv` 和 `power_breakdown.csv`：面积和功耗分布。
- `FLOW_COMPLETE` 仅表示流水执行并完成统计，**不等于 timing signoff**。
  必须核对 coverage/check_power/check_timing/constraints，负 slack 单独标为 TIMING_VIOLATION。
  注释覆盖不是 100% 时需要审查未注释网，禁止默认当作 100%。

分组可靠地归属输入、一级乘积/概率、二级乘积、输出、valid 寄存器；DC 可能优化寄存器，其他命名归 other。
匿名组合门归 `combinational_unattributed`，不把共享门硬分给 LUT/乘法器/舍入器。
精确的功能单元拆分需要后续受控层级版本，不能与原自由优化面积混为一谈。

本地验证为 Icarus 端口级 RTL 回归与脚本/报告解析测试，不是服务器 VCS/DC/PT 实测。
首次服务器运行后才能给出真实工艺面积和估计功耗；未上传任何工艺库/原始大型波形。

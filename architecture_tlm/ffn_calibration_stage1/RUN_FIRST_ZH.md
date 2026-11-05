# 先运行这两项

本包默认首轮只做 **64路、4档、64拍、单输出精确计数核** 和 **4档整数恢复核**。先看这两项的关键路径，再决定是否跑全部9配置。没有要求你第一次就仿真完整FFN。

## 1. 准备环境

把ZIP解压到你的Linux工作目录，进入 `ffn_calibration_stage1/`。需要Python 3.10+、VCS、DC和你已有的55nm标准单元 `.db`；PT可选，仅用于STA复核。本包不包含工艺库和EDA软件。

复制环境模板到包外，例如：

```bash
cp flow/env.sh.example ../ffn193_ss.env.sh
```

编辑这个文件：把你已有的EDA环境脚本填在 `source ...` 处，把 `STD_DB` 指向 **SS/1.08V/125°C** 的实际 `.db`。如果库里没有默认的 `INVX1_9TSVT`，将 `STD_REF_CELL` 改成该库确实存在的普通反相器单元。脚本会从实际库报告核验PVT和时间/电容单位，文件名不是唯一依据。TT另建环境文件，使用TT/1.20V/25°C库。

环境文件可留在你自己的目录，不要放token、许可文件内容或工艺库进Git。

## 2. 用Slurm提交最小两项

先只生成提交计划，核对路径、队列和资源：

```bash
bash flow/submit_smoke.sh \
  --env "$(realpath ../ffn193_ss.env.sh)" \
  --corner ss \
  --output-root "$(realpath ..)/ffn193_runs"
```

确认计划后，在同一命令最后加 `--submit` 真正提交。需要特定队列/账户时附 `--partition 队列名 --account 账户名`。默认并发1，不申请GPU，4CPU/16GB；这只是起始资源配置，不是实测耗时承诺。

每项会依次执行：**冻结源码和配置 → VCS功能验证 → DC综合和setup/hold检查 → 保存结果**。功能失败不会继续综合。若需要独立PT时序复核，加 `--with-pt-sta`；这一选项不会跑PT功耗。

也可在已有合法计算节点分配中单项执行：

```bash
bash flow/run_case.sh \
  --env "$(realpath ../ffn193_ss.env.sh)" \
  --case-id counter_b4_t64_m1 --corner ss \
  --output-root "$(realpath ..)/ffn193_runs"
```

不要在共享登录节点直接启动长综合作业。输出目录必须在源码包外。每次运行都有新ID，源码快照提交后不修改。

## 3. 结果交给我哪些

每个case保留其 `reports.tar.gz` 和SHA文件即可。包内含 `RESULT.json`、配置/源码manifest、命令退出码、功能回执、面积、setup/hold、约束、单元映射等小型报告。网表、库、波形不会自动装进返回包；原始完整目录留在你自己的服务器上。

| 字段/状态 | 如何理解 |
|---|---|
| `met` | 本配置、当前约束下已报告时序满足；仍是布局前估计 |
| `not_met` | 有负slack或约束违例；这是有效的失败结果，需要看路径后改流水线 |
| `failed` | 工具/功能/PVT/缺报告等问题；不能当作时序通过或功耗为零 |
| `power_W: null` | 还没有本轮活动功耗分析，不代表不耗电 |

**先把两个小配置的报告给我。** 我会按真实路径调整RTL、重新验证整数/握手一致性，再交第二轮。若两项都通过，可把 `submit_smoke.sh` 改为 `submit_all.sh` 扩展9项；SS和TT分别提交，不混用库。

默认100MHz、setup uncertainty 2ns、hold uncertainty 0.1ns、输入/输出max delay 1ns/min 0.2ns、输出负载0.02pF、输入转换0.1ns。同步复位正常计时，没有false-path或multicycle豁免。约束需与你现有参考模块保持一致后再比较；不要为获得正slack暗中修改。

本机已经用Icarus做RTL功能验证；VCS、DC/PT脚本尚需在你的许可环境首次执行。这里是第一轮校准交付，不是完成了55nm PPA。

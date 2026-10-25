# 第一轮：功能＋DC综合/STA；可选PT时序复核

**这是交付脚本，不是已运行的工艺结果。** 固定55nm、SS 1.08V/125℃或TT 1.20V/25℃、100MHz；没有活动依据的功耗分析，所有功率和能量字段保持null。第一次只跑smoke，检查报告后再显式运行all；不自动提交全套或TT。

## 1. 用户需要设置什么

复制 `flow/env.sh.example` 到源码包外的个人目录，接入自己的Synopsys环境setup，填一份角对应的 `STD_DB`。`STD_REF_CELL`默认`INVX1_9TSVT`。DC/VCS/PT默认通过PATH查找，可用`DC_SHELL`、`PT_SHELL`覆盖工具位置；Python需3.8以上。不需要复制`.db/.lib`进源码。

脚本读库的真实operating condition和单位，SS/TT名字、电压、温度以及1ns/1pF单位不符即失败；不会只根据库文件名猜PVT。每次执行记录库原文件SHA-256，不复制库。工具setup文件也只记录路径和SHA；涉及它再source的其他setup文件，应由使用方保留其版本，不宣称已递归冻结所有环境。

## 2. 从两个小case开始

在包根运行（以下只是命令示例，没有在本轮执行）：

```bash
bash flow/run_case.sh --env /personal/ffn193_ss_env.sh \
  --case-id counter_b4_t64_m1 --corner ss --output-root /personal/ffn193_runs
bash flow/run_case.sh --env /personal/ffn193_ss_env.sh \
  --case-id restore_b4_c20 --corner ss --output-root /personal/ffn193_runs
```

或者Slurm。**不加`--submit`只准备快照/脚本，不提交作业：**

```bash
bash flow/submit_smoke.sh --env /personal/ffn193_ss_env.sh \
  --corner ss --output-root /personal/ffn193_batch --submit
# 核对smoke后，才按需要显式运行：
bash flow/submit_all.sh --env /personal/ffn193_ss_env.sh \
  --corner ss --output-root /personal/ffn193_batch --submit
```

默认4CPU、16GiB、每个功能/DC/PT阶段超时3600秒、Slurm 03:15:00、并发1，没有GPU请求。这些是保护上限，不是已测运行时间；第一轮两个小case的真实编译时间由阶段回执记录，再据此安排全套。可加`--partition`、`--account`、`--parallel`、`--timeout`、`--time`，调整时保持作业总限时覆盖全部阶段。默认不启动PT；加`--with-pt-sta`仅做STA复核，绝不调用`report_power`。TT要提供TT的环境文件并另加`--corner tt`。

## 3. 固定接口和执行顺序

包根`cases.json`合同：`{"schema_version":1,"cases":[{"id":"...","top":"...","smoke":true}]}`；其它功能配置字段保留。top已固定参数，DC直接`elaborate TOP`并分析全部`rtl/*.sv`。所有top必须有`clk/rst_n`，复位同步低有效。

每个case先在当前服务器运行：

```bash
python tests/run_all.py --output NEW_RUN/work/functional \
  --case-id CASE_ID --simulator vcs
```

要求输出`summary.json`中`status=passed`、正确`case_id`，以及`source_sha256`覆盖全部`rtl/`和`tests/`原文件。成功后才进DC。驱动在阶段前后核对冻结源码，不用此前本机功能结果代替远端执行。可显式选`--functional-simulator iverilog`供工具齐全的本地站点使用；它不会跳过DC。

每次生成唯一UTC/case/corner/随机后缀目录；同一output-root/case/corner用排他锁避免重复执行。超时终止整个工具进程组并记录失败。进程被强杀可能遗留锁，须核对其中PID、run路径和Slurm状态后由使用方处理；脚本不会擅自打破旧锁。无覆盖旧结果或失败后自动大规模重跑。

## 4. 约束与判断

- 周期10ns；setup uncertainty 2ns、hold uncertainty 0.1ns。
- 输入/输出delay max 1ns、min 0.2ns；输入与时钟transition 0.1ns；输出load 0.02pF。
- **同步`rst_n`正常计时，没有reset false path、multicycle、case-analysis或hold豁免。**
- DC使用`compile -map_effort high`作为明确可重复的基线，非全局最优综合宣称。
- `met`：功能通过、PVT/映射/时序检查完整、setup/hold及约束均满足。
- `not_met`：完整结果存在但负slack或约束违例；保留真实数值，退出码3。不能把它换算成若干拍就称新流水线已验证。
- `failed`：缺slack、未知/不符PVT、未映射cell、工具Error、check_timing警告/未覆盖unconstrained检查、超时、SHA变化等；退出码2。

有正slack也仍是布局前证据，没有CTS/SPEF/SDF。面积记录库单位并按已知55nm库惯例标为µm²；本轮未做LEF单位交叉提取。PT面积为已映射标准单元求和，DC同时保留`report_area`，不假装PT执行了DC命令。

## 5. 请回传什么

每个run的`reports.tar.gz`和`ARCHIVE.json`，以及Slurm提交目录的`SUBMISSION.json`。小包包括`RESULT.json`、源码/配置/库SHA、功能摘要、DC/可选PT setup/hold/area/check_timing/映射报告和阶段回执。**不包含网表、库、库完整报告、波形或完整工具日志**；这些保留服务器个人run中。失败也生成小包，按error和原始服务器log诊断，不只挑通过项回传。

当前没有门级动态功能、功耗、面积外推或完整FFN/PPL结论。功能验证是RTL数值/握手；STA是映射后的时序，二者证据分开。

## 6. 脚本自测（不调用许可EDA）

```bash
python flow/test_flow.py --tmp-root /personal/ffn193_script_tests
for script in flow/run_case.sh flow/submit_smoke.sh flow/submit_all.sh flow/env.sh.example; do
  bash -n "$script" || exit 1
done
```

测试覆盖解析器正/负slack、未知PVT/单位、缺失证据、未约束/未映射/工具错误、功能SHA门禁、快照、超时回执及允许回传文件范围。Tcl解释器可用时还检查所有脚本语法完整性和PVT表/块解析；这不等于Synopsys命令已在许可环境验证。

PVT解析复用：本项目`digital_ppa8_ss_tt_100_20261024_v4/library_conditions.tcl`原字节，SHA-256 `7308e1dc6a1e59e786ccc0df1d1145ed957fd0b62cb6ad568d302398c670ba2d`。`common.tcl`根据原可靠检查逻辑改写，增加单位/映射检查并去掉不适用于同步复位的豁免。不捆绑任何工艺库。

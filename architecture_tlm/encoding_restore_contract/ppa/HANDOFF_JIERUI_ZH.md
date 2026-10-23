# 给 jieruiz 的 STA/PPA 执行交接（Issue123）

用户于2026-10-23指定由项目成员jierui负责EDA，GitHub账号已从项目历史确认是
`jieruiz`。本文件是次日执行待办。当前真实DC/VCS/PT/STA/面积/功耗全部**未运行**；
我们已准备固定顶层、精确参考向量、执行流程与失败门禁，不把功能周期当作100MHz达标。
请沿Issue123协作，保留Issue107与PR122原源码和证据，不重交其他成员仍在运行的任务。

## 1. 固定矩阵与计费边界

| driver --case | 功能 | 参数 | 每笔归属 |
|---|---|---|---|
| er_contract_k0_t0_d3 | BF16完整组编码 | FRAC7,N64,B4,DEPTH3,TAG_W32 | 64输入值/组 |
| er_contract_k1_t0_d3 | FP32完整组编码 | FRAC23,N64,B4,DEPTH3,TAG_W32 | 64输入值/组 |
| er_contract_k2_t16_d3 | 完整四档恢复 | COUNT_W11,T_LOG2=4,FUSED0,DEPTH3 | 1输出/64输入块 |
| er_contract_k2_t32_d3 | 完整四档恢复 | COUNT_W12,T_LOG2=5,FUSED0,DEPTH3 | 1输出/64输入块 |
| er_contract_k2_t64_d3 | 完整四档恢复 | COUNT_W13,T_LOG2=6,FUSED0,DEPTH3 | 1输出/64输入块 |

首批角SS1.08V125℃，之后TT1.2V25℃；固定100MHz，3seed=20261023/7/1234567。
全部完成为10次综合、10次门级编译、30个有效活动窗口；建议先SS/T32一个case跑通。
各case使用相同约束，每角/每case只综合一次，同网表跑三seed。

编码保留原q/256、true_one、符号、bin与top exponent。恢复计数总线为
`((bin*2+input_sign)*8+weight_bit)*COUNT_W`，bit7系数−128；不可直连
product-sign/magnitude总线。FUSED0逐bin先含除T的整数转FP32，再乘scale，再顺序相加。
完整编码每组替换旧447代理操作；完整恢复每笔替换旧72代理操作，不能再乘447/72。
包装测量已含结果槽/tag/信用状态，不与原nr_digital_probe面积能量重复相加。
跨k FP32 add、最终BF16收窄、SC采样、SRAM/CDC和全FFN不在本轮5case中。
当前Issue116接合的x和z均按FP32内存/算术口径；BF16编码是独立基线及未来可选配置，
测得BF16编码PPA不能据此宣称当前x内存减半或当前完整数据流已改成BF16。

## 2. 执行前由你现场确认的环境

在你的已授权个人环境确认：实际账号及canonical home、个人根所有权/授权、host节点
角色、Slurm分区与CPU allocation、工具许可、标准库与单元模型权限。全部写入/输出
必须留在该个人根。旧文档中的/public3路径不是本流程的默认授权，不替其他账号取库。

需要由你填入以下环境变量，所有文件路径必须绝对路径；不把凭据写入仓库：

```bash
export EDA_EXPECTED_USER='YOUR_VERIFIED_LOGIN'
export EDA_PERSONAL_ROOT='/absolute/verified/personal/root'
export DC_SHELL='/absolute/licensed/bin/dc_shell'
export VCS='/absolute/licensed/bin/vcs'
export PT_SHELL='/absolute/licensed/bin/pt_shell'
export STD_DB='/absolute/authorized/SS_corner.db'
export STD_MODEL='/absolute/authorized/standard_cells.v'
export STD_LIB_NAME='EXACT_LIBRARY_NAME_FROM_REPORT_LIB'
export STD_OC_NAME='EXACT_SS_OPERATING_CONDITION'
export CUDA_VISIBLE_DEVICES=''
# 只有工艺文档确认area的物理单位时设置；否则保留library_area_units。
# export STD_AREA_UNIT='um2'
# export STD_AREA_UNIT_EVIDENCE='/absolute/authorized/unit-evidence-file'
```

STD_DB单库、STD_MODEL及工具只读取与散列，不打包。库须有完整timing/power表。
库/工具环境配置继承你的合法设置；流程不安装系统软件、不改许可服务器或共享库。
切换TT时同时换STD_DB/STD_LIB_NAME/STD_OC_NAME，使用同prepared下独立TT结果目录。

## 3. 源码与功能前提

检出本次交付的准确Git提交；必须包含以下目录，保持原字节并记录commit：

- architecture_tlm/encoding_restore_contract（含sim、rtl、ppa）
- architecture_tlm/digital_ppa_v1/rtl及sim/validate.py
- 根目录format_conversion_rtl_20261016/rtl与sim/reference.py

本轮实际CPU Slurm作业2778已完成：45个RTL case通过，11667个有效输出、180个
reset-flushed在途操作，18源SHA核验。包含BF16/FP32编码、T16/T32/T64恢复、depth1/3/5、
三seed。证据是[VALIDATION.json](../results/rtl_2778/VALIDATION.json)、同目录
INPUT_MANIFEST.json与COMMANDS.json。PR122原记录只有T32；本轮真实扩展功能证据
不能当作DC/VCS/STA/PPA证据，也不能继承到后续改变的源码。

在你的CPU allocation内先运行Python流程预检；也可用已有个人Icarus复核以下命令，
新目录避免覆盖原结果：

```bash
cd /absolute/personal/checkout
python3 -B -m unittest architecture_tlm.encoding_restore_contract.ppa.test_flow
python3 -B architecture_tlm/encoding_restore_contract/sim/validate_ready_valid.py \
  --iverilog /absolute/personal/bin/iverilog --vvp /absolute/personal/bin/vvp \
  --samples 16 32 64 --depths 3 \
  --build-dir /absolute/personal/new-rtl-build --out /absolute/personal/new-rtl-evidence
python3 -B -m architecture_tlm.encoding_restore_contract.ppa.driver prepare \
  --out /absolute/personal/new-ppa-prepared
```

prepare只生成5固定顶层×3seed向量及PREPARED.json，不执行EDA。
源码闭包包含实际RTL、TB、exact oracle、driver/parser/Tcl与测试源，逐文件SHA绑定。
准备后不修改源码；修改需新的准备目录。

## 4. 在真实CPU allocation内执行

由你按实际Slurm分区提交CPU作业，设置显式 `--cpus-per-task`，不申请GPU并显式
隐藏GPU。请在脚本中保存 `id -un`、canonical home/root、hostname、scontrol allocation
与源码commit；提交前检查相关运行任务，避免重复提交。本流程不提供猜测分区/主机的
自动提交器。SLURM_JOB_ID/SLURM_CPUS_PER_TASK由调度器提供，不手工伪造。

最小SS/T32命令（上节环境已填妥）：

```bash
python3 -B -m architecture_tlm.encoding_restore_contract.ppa.driver run \
  --prepared /absolute/personal/new-ppa-prepared \
  --case er_contract_k2_t32_d3 --corner SS
```

成功审查后按矩阵逐case运行，其余命令只换`--case`；TT换实际库环境及`--corner TT`。
`runs/<corner>/<top>/`保存configuration/allocation、dc、build、gate_seed、pt_seed和RESULT。
完成阶段复用前逐hash核验；配置、工具或库变化拒绝复用。失败目录不自动删除/覆盖；
先读FAILURE/log，保留错误证据，再用新prepared执行修复版。RUNNING.lock遗留时须
先确认原进程/Slurm终态，不能把锁删掉就并发重跑。

门级VCS只编译生成mapped.v、统一TB及真实单元模型；黄金参考由原exact oracle生成。
固定top无参数，使用ER_DUT_TOP宏，保持全部端口。只有逐笔数值、顺序、反压稳定性、
信用守恒、复位flush和II检查PASS才允许PT。

## 5. 必查门禁与回填

1. 源/工具/库/向量SHA一致，PVT/库名/OC真实匹配；report_units为1ns/1pF。
2. DC全源码解析/link成功、无blackbox/未映射cell、真实mapped面积非零；完整端口受约束。
3. 保留setup/hold/约束/check_timing及clock报告。负slack照实登记，不能删路径/减小
   uncertainty使结果表面通过；后续改pipeline/频率需新的配置/功能验证与结果。
4. VCS真实模型零延时功能通过；active窗口VCD无X/Z。stage3连续32拍预热后取64拍，
   640ns、64接受/64完成，不含reset/drain；本轮不是idle/burst/真实Qwen活动表征。
5. PT检查power表/注释覆盖、功率单位、内部/翻转/leakage总和；缺失/错误直接失败。
   非全覆盖、Warning（含PWR-981等）、违反约束或负slack保持accepted_for_tlm=false，
   先人工审阅未注释网/告警再形成有理由的后续记录，不静默把100%写入结果。
6. 每seed单列功率与窗口能量，`E[pJ]=P[W]*duration[ns]*1000/completed`。
   面积是映射单元面积，不是core/die；无SDF/SPEF/CTS，不算后布局或硅实测。

按[RESULT_TEMPLATE.json](RESULT_TEMPLATE.json)填写每case/corner的摘要；seed_windows保存
driver.RESULT.json中的实际三条结果和原始report位置/hash。同步中央
digital_circuit_simulation_registry记录，并在Issue123关联执行提交、Slurm终态及产物索引。
首次看见终态立即保存，防止作业老化后丢失allocation/exit evidence。

GitHub只上传代码、公开配置/小摘要/验收与hash索引；标准库、Verilog工艺模型、工艺单位
证据正文、受限report_lib和大波形/网表留在原授权个人存储。原始归档应放源树外，核验
归档退出码和SHA后登记可恢复路径，不上传PDK、不重复打包动态日志。

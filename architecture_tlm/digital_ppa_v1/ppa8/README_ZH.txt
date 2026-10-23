8类数字算子 SS/TT 100MHz 工艺仿真包
版本 digital_ppa8_ss_tt_100_20261023_v2，Issue107后续分支（原PR109已合并）。

v2修正：VCD所有向量逐位展开，保留每位/别名/时间和X检查，不删除常量位。
PT的clk、out_valid及有效result位逐位对照VCD的翻转率和高电平占空比；
PWR-981若仍出现直接停止，不接受仅凭100%覆盖率通过。
功耗库超范围采用9位有效数字报告，并统计受影响单元的全部功耗占比。
该占比不是误差界限；不添加虚假负载/修改slew/关闭告警，保留PROVISIONAL。

已有38339971两角结果时，先只重跑PT（不要再次smoke全流程）：
  cd /public3/home/t6s011227/pbit_chimera_pipeline_20260920
  unzip -o digital_ppa8_ss_tt_100_20261023_v2.zip
  cd digital_ppa8_ss_tt_100_20261023_v2
  bash submit_power_recheck.sh /public3/home/t6s011227/pbit_chimera_pipeline_20260920/digital_ppa8_ss_tt_100_20261023_v1/results/38339971
不改旧任务目录。逐SHA核验v1源码/库/配置/DC和12功能阶段；原网表/VCD只读复用，
结果写v2/results/<新arrayJobID>_7或_15，每角9窗口PT，无DC/VCS重跑。
需要远端保留旧目录里的STAGE_COMPLETE、mapped.v/ddc/sdc、原VCD；小报告包不足以恢复。
成功回传新版两份reports包后再评估剩余14项，不因FLOW_COMPLETE自动豁免库范围。
v2本机仅做转换/守卫/语法验证，没有本机DC/VCS/PT授权，实际兼容性由该重检确认。

任务矩阵：索引0..7为SS，8..15为TT；各组KIND依次0,2,4,5,6,7,8,21。
0 FP32加法；2 BF16乘积/FP32累加；4 BF16分档编码64元素；
5 FP32分档编码64元素；6 四档计数恢复并求和；7 FP32近似SwiGLU；
8 BF16 V输入/FP32累加/末次平均窄化；21 FP32转BF16。
SS=1.08V/125C，TT=1.2V/25C，55nm SVT。两角电压不同，不是只改变温度。
实际库的report_lib必须吻合；TT不自动回退SS。可设置SS_DB/TT_DB/STD_MODEL。

上传到 /public3/home/t6s011227/pbit_chimera_pipeline_20260920/ 后：
  source ~/.bashrc
  cd /public3/home/t6s011227/pbit_chimera_pipeline_20260920
  unzip -o digital_ppa8_ss_tt_100_20261023_v2.zip
  cd digital_ppa8_ss_tt_100_20261023_v2
  python3 package.py
  bash submit.sh smoke
smoke为KIND21的SS/TT两项，但执行完整流程，不是假工具测试。
确认两项FLOW_COMPLETE及summary.csv后：bash submit.sh remaining
也可一次bash submit.sh all运行16项；不要与尚在运行的smoke重复提交。
默认4CPU/16GB/12h，每次最多2项。DC使用4核；VCS无FGP，不要求多核许可。
可覆盖 EDA_CORES=4 MEMORY=16G WALLTIME=1-00:00:00 MAX_PARALLEL=2。

每项1次DC、1次VCS编译、12次门级数值检查、9次PT：三seed17/43/101，
各有stress、stream、burst、idle；stress只功能不计算功耗。
RTL/ROM/转换依赖/数值参考/离线向量全部包含；不含受限制工艺库。
远端只需Python>=3.6标准库、DC/VCS/PT和已有标准单元库，无numpy/LC/SRAM。
每次提交复制只读快照。不要改snapshots里的文件。

结果：results/<arrayJobID>_<index>/；日志logs/dig8-<arrayJobID>_<index>.out/.err。
每项结束（包括失败）生成results/<arrayJobID>_<index>_reports.tar.gz。
下载这些小包及Slurm out/err即可；大VCD、网表、DDC和simv留远端供恢复。
若调度器强杀而没有包：python3 collect.py results/<arrayJobID>_<index>
恢复失败的同版本同库任务（示例只恢复索引3）：
  REUSE_RUN=<原arrayJobID> bash submit.sh 3
完成阶段逐SHA复核后复用；失败阶段改名保留证据。运行锁防并发写同目录。
源码或库改变必须新任务，不能伪称复用；不要清理正在运行的结果/快照。

计费口径：包括probe实际保留的输入/输出寄存器、控制及core内部状态。
power_breakdown.csv区分boundary/core逻辑和寄存器；分组依赖保留层级，
不等于精确逻辑锥归因。不含TB激励、PLL、SRAM、随机矩阵或真实CTS/布线。
DC用compile保留层级，非扁平化最优面积。面积为映射单元面积，不是版图面积。
VCS为零延迟门级功能验证，禁用timing checks；PT独立报告setup/hold。
10ns周期、setup uncertainty=2ns(20%)、hold=0.1ns，输入转换0.1ns、负载0.02pF。
STA负slack不会被称为100MHz达标；已算功耗标PROVISIONAL，供定位结构成本。
没有SDF/SPEF，不计实际毛刺、时钟树、布线，不能称后布局/硅片功耗。

功耗窗口排除复位。stream/burst包含全部有效事务和16拍排空，idle在预热完成后。
burst每16有效拍停48拍，不是有ready接口的背压测试。idle输入静止，不是随机噪声输入。
三seed为合成激励，不是模型真实张量；stress覆盖原参考边界值/NaN等，但不用于平均功耗。
累加帧为1/14/76/128/512；KIND8按mean_log2=7(512帧为9)缩放，
短帧是部分和/协议测试，不声称14或76项的真实除法平均。报告为混合帧流，
不能直接当作单独S128或S512单位成本。需对应真实TLM流量再做加权。
能量window_pJ=P(W)*duration(ns)*1000；除以实际接受输入数/完成输出数。
KIND4/5一个输出是64元素一组；KIND6一个输出已含四档/全部恢复，不再乘64/72。
idle单位操作能量为空，不能除以0。原始总能量不扣漏电/接口。
SwiGLU是PWL sigmoid候选，局部数值参考通过不证明模型质量或完整FP32数学等价。

统一台账先登记本地功能/脚本验证及PPA待运行；收到结果后新增执行任务记录。
记录准确快照SHA、库SHA、PVT、活动窗口、功能/STA/功耗各阶段，保留失败记录。

# 128候选赢家保持反馈／仲裁控制

2026-10-28，Issue198 / PR199，rayggxia。用户本轮仅授权此控制边界，概率驱动、随机源本体、V读取和累加不纳入，也不对这些模块施加串行调度假设。

以已验证control_v2为父实现。全候选位图可在固定概率下提前准备；每次提交仍使用实际前一赢家，不用推测状态。接受全零保持、多hot时旧赢家为1则保持，否则无偏均匀选择active地址。按ceil(log2(active_count))位拒绝重取，64次拒绝后显式failed，该query无成功结果，不能将失败前的部分输出当完整估计。

8个top：G8/G16/G32融合准备；G16两级；G16提前保持；G16一热反馈；G16计数器32位；G16串行参考。其余采用10位样本/更新计数器，支持总更新1..1023，覆盖S64/128/256/512及burn32；不声称支持任意S。算法及仲裁不变；32位对照用来隔离控制位宽成本。原512源码和结果不改。

功能：独立flat-list周期oracle；每top三seed复位/回压压力、rank-cap失败、零/单/多/全1、稀疏p=1/32、dense p=.5，S64/128/256/512及burn0/32。相同frame/fair逻辑序列在分组/流水/回压变化后地址序列一致；提前保持和串行因省略随机消费单列序列类别。全部是合成控制激励，不是新增真实模型/PPL或物理源独立性证明。

首轮PPA：每top sparse三seed、all、dense、外部stall与clock-running idle共7窗口；query窗口含start/config/流水填充及排空，避免把初始化成本删掉。功能另外保存首帧→首输出、输出间隔、rank retry及外部等待。全1/全零只能测吞吐极限，不代表有效独立样本。S数量和控制更新次数不是ESS。

沿旧SS SVT1.08V125°C/100MHz、slew0.1ns、load0.02pF、setup uncertainty2ns/hold0.1ns、core IO delay0。保留原约束并单列内部reg-reg路径和边界路径；不靠false path或放宽hold宣称修复。DC/VCS门级零延迟/PT averaged，无SDF/SPEF/CTS；未完成报告不视为通过。原始面积×0.81另报55nm折算；功耗/时序不缩放。电源库/连接资料留授权私有存储。

流程：build.py生成隔离RTL/flow；vectors.py生成原字节输入与golden；local_check.py本机Icarus；服务器冻结快照后Slurm runner.py执行DC与VCS/PT。精确源、执行manifest、作业、原件和统一台账记录见work/rayggxia/198/CONTROL128_*。

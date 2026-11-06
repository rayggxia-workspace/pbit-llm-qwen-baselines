# 最新模块交接预算

2026-11-06，负责人rayggxia，接续Issue225/PR248，task/225-norm-stream-20261106；独立目录沿tmp/norm-stream-issue225-20261106。只读取198/204模块交接，不修改其源码或已提交作业；旧norm6/compact9执行源不改。

正式入口architecture_tlm/current_handoff_budget_20261106/REPORT_ZH.md及estimate.py，INPUTS为派生小价格表/计数/源SHA，不复制其他模块原交接包或输入。实际公开提交及回读见PUBLICATION.json；没有回执不能称已推送/合并。

## 当前预算

640路/40FMA16、K并行8、4context、提前补货，归约仍128个FP32加法器；FFN12公共C20/T64、64位跨K、GU状态96KiB候选，SRAM1952KiB/488宏、norm32KiB；独立512路QK、Attention8×128KiB、K128/IsingS64/PV ADD及DMA24KiB保留。

覆盖面积57.573748mm²；假定50ms/token，片上24.204832mJ/0.484097W，含4pJ/bit外存197.369327mJ/3.947387W。640但保留152KiB状态/502bank则57.950534mm²。50ms是计价窗口，45/55ms仅敏感性；不是新联合TLM时间，96候选的完整pair与640整token/lm_head仍待验证。

MAC次数不变，不乘640/1024削减动态能量；归约29,312,640→3,256,960次ADD按动作计费。SRAM不打容量比例动态折扣；norm装载392192B、headnorm显式读及96分批观测的额外读都计入。GF64/SNG已在C20核内，不重复加。所有面积已按原口径折算，不再次×0.81。

未预扣：Attention64KiB、普通池共享QK、激活128KiB、CIM24槽、DOT8融合。新增owner/input-hit/供数/结果槽/归约连接/译码互连尚无独立PPA；表是覆盖边界内预算，非完整die或功率实测。新K分组改变FP32求和顺序，不能继承PPL。

## 实际验证

6项CPU检查通过：16项旧能量分项重建、640面积与独立QK保留、MAC动态不随lane数折扣、归约次数与物理归约器分开、14宏差值单次0.81、能量/面积分组及功率单位守恒。运行`python -B -m unittest discover -s architecture_tlm/current_handoff_budget_20261106 -p test_estimate.py -v`；重算`python -B architecture_tlm/current_handoff_budget_20261106/estimate.py`。

构建输入时12个本地原件按SHA绑定；其中ordinary mapping640前缀、FFN96三seed确认和Attention64仅方案均分开登记。没有新模型/权重/tokenizer/训练文本下载，相关版本不适用：本轮只重计已有硬件工作量，不执行数值推理。

另只读收取旧38614103已封存的6/9完整norm结果（三resident、三stream2p5），逐SEAL/源SHA守恒检查通过；剩余三项不能算完成。该动作不是新任务，不重交/取消任何作业；当前联合640+96未提交新native、GPU、RTL或PT。

## 下一步

先把ordinary_mapping.install(lanes640,k_parallel8,early_refillTrue)与FFN96候选接同一宿主，保留最新bank布局，完整token及lm_head回放后，用真实时间/计数替代本预算窗口和两层额外读外推。不要将各模块前缀时间相加，不接管204完整pair或修改198冻结run默认。必要时再补新增控制/连接的代表性PPA，不重做已有PRNG和SRAM单价。

根报告目录是同字节阅读副本；长期备忘录canonical/root同步，但不把其他并发任务的未提交备忘录一起公开。Issue225保持open，PR待审不自动合并；Projects无写接口待维护者同步。

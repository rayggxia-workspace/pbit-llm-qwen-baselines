2026-10-29新增：[128字阈值寄存器与全部Q头预算](regbank_20261029/REPORT_ZH.md)。真实门控与128路比较器7top/84PT，含装载能量；16位hold/比较器库表外推未签核。

2026-10-28最新128节点控制结果：[面积/能量/时延联合比较](control128_20261028/RESULTS_ZH.md)。G16融合主候选，336回放/56PT完成，保留hold与活动映射告警；不含概率驱动/V通路。

2026-10-28补充：[KV读取与经典数字Attention基线](KV_DIGITAL_BASELINE_ZH_20261028.md)，含旧轨迹布局核算与后续验收，不是新硬件/模型仿真。

2026-10-28补充：[普通数字Softmax周期/面积调研](SOFTMAX_DIGITAL_SURVEY_ZH_20261028.md)，文献与条件换算，无新增EDA。

2026-10-28更新：服务器采样控制评估见[最新结果](control_v2/eda_20261028/RESULTS_ZH.md)，其余旧阶段保留原始日期和限制。

# Attention单query首轮实现与结果（Issue198）

2026-10-27；rayggxia；main@d83eeb1f；task/198-attention-compare。当前是第一阶段交付，后续验收仍开放。

已读取用户PDF/交接、最新远端规则/README、本人187交接，以及78/87/186状态；PR88已合并，PR192/197仍待审。

本轮新增六方案数值对照、有限tile宏调度和完整校正拒绝数字控制。108个合成案例全部完成；6项机制检查通过；N16/64/512×三seed的22500拍RTL与独立oracle逐拍全等。RTL为外供比特控制，未综合/STA/PT，不是完整QK到V的硬核。

## 固定预算观察

同一合成BF16 QKV输入、L2048/d128、S128、三seed均值；数字算术FP64数学参考，宏调度不是逐位BF16硬件。K/V字节为本head准确burst集合；summary/state本地流量另计。

|方案|条件周期|K字节|V字节|相对完整输出L2误差|
|---|---:|---:|---:|---:|
|D0|33586.00|524288|524288|0.0000|
|P0|21450.00|524288|32768|2.4499|
|P1|9953.00|131072|131072|1.7710|
|P2|8924.67|131072|30635|2.5656|
|P3|33651.33|131072|24064|3.2761|
|P4|10979.67|131072|24320|3.5106|

合成V近零均值时相对误差易显大，不能转成PPL；QUALITY.json同时保存绝对MSE、目标分布单样本方差归一化误差、筛选误差及采样误差。二者平方误差存在交叉项，不声称可直接相加。

## 探索性质量匹配

固定以上输入，以完整分布IID128的解析期望MSE（约0.99772）为全输出阈值。扫描S32/128/512/1024；下表是三seed均值首次过线的测试网格点，不是置信保证/精确最小预算/模型验收。D0/P1无采样预算，表中S列不适用。

|方案|首次观察预算|条件周期|
|---|---:|---:|
|D0|不适用|33586.00|
|P0|128|21450.00|
|P1|不适用|9953.00|
|P2|128|8924.67|
|P3|512|117264.00|
|P4|512|22180.67|

校正拒绝为达此探索阈值要S512，条件周期117264，约为D0的3.49倍；赢家S512约22181拍。不能用固定S128的省流量数字宣传同质量收益，更不能据一次合成输入确定最终方案。

## 实现合同与限制

- D0/P1分块在线max/分母/非归一输出，末尾统一归一化；无需长度L的概率行，更无L×L概率矩阵。
- P0/P2准确softmax＋systematic CDF，保留全局归一化、第二遍扫描和直方图费用。P3/P4直接复用已合PR88，地址只映射一次，无二次PV抽样。
- P1–P4共享max4/64块、首末2强制、Bernoulli＋固定配额修复。此轮中心0/温度1为合成校准，非已训练Qwen筛选器。summary生成是fixture预处理；warm路径计追加更新/存储/读出，cold全K读量与生成加法另列，不能声称首次查询也无需全K。
- 2有限K/V tile槽、有限本地容量、共享memory_link/MAC/vector/local_sram资源和在线依赖。V按唯一地址读取，以重复加法保留次数，d64按L7反馈限制发起率。QK/PV吞吐是并行点积归约宏假设，不将独立L14 MAC直接当同状态II1。
- PR88采样时序仍为该接口的条件FSM；本次RTL实际实现与其源/配置等待尚未逐边沿绑定，因此没有用RTL小例冒称更新完整TLM。此模块实验未改unified_v6、PR192新存储或其sink检查。
- Link不是DRAMSys，不含bank/NoC/DRAM命令级、GQA多头调度；kv_union只提供同组物理并集检查。没有新增平行整机模型或修改主入口。
- 完整能量/面积为null：MAC、Softmax、RNG、LUT/驱动转换、时钟门控/idle、互连与有效外存未同边界闭合；文献跨工艺PPA未套为本次实测。
- RTL具有配置valid/ready、流水singleton、m反馈、精确低m位全零校正、proposal cap和1条有限输出寄存。cfg_ready表示后端已稳定；独立随机性由外部源保证。cap失败之前可能已输出部分地址，消费者只在done且!failed时提交整query，失败时丢弃其部分和。
- 未实施D1/ITA移植、赢家控制RTL、完整V gather/累加RTL、后训练Qwen捕获/匹配BF16/PPL、同吞吐面积和真实PPA；不自动恢复暂停116/123或启动昂贵任务。

## 复现与后续

从仓库根运行，输出目录必须不存在；Python3.12＋NumPy2.3.5用于正式数值结果：

```sh
python -B -m unittest architecture_tlm.attention_compare_20261027.test_core -v
python -B -m architecture_tlm.attention_compare_20261027.run --output NEW_SWEEP
python -B -m architecture_tlm.attention_compare_20261027.quality --output NEW_QUALITY
python -B -m architecture_tlm.attention_compare_20261027.validate_rtl --iverilog /path/iverilog --vvp /path/vvp --ivl-lib /path/lib/ivl --output NEW_RTL
```

Icarus10.1在Windows沙箱内WinError623，已通过自动审批在沙箱外完成上述短功能验证；无许可EDA/服务器/GPU任务。原失败日志/快照保留，rtl_v4是最终功能版本；v3与v4属于同控制源码的覆盖补充，不计为两个独立电路run。

精确输入/源码/文献入口见work/rayggxia/198/INPUTS.json。原始逐case结果、事件、比特轨迹与编译日志在RAW_ARCHIVE.json指向的本地ZIP，逐成员SHA已核；Git保留小型汇总和manifest。后续优先绑定RTL时序与源接口、用后训练真实QKV验证质量，再扩GQA和D1/存储/成本。

统一台账本任务仅新增attention-rejection-198-20261027。main尚无完整registry工具，聚合check/render在本人辅助目录进行，并增量同步根阅读镜像；依赖PR197不混入本PR。Projects权限未核实/待维护者同步。发布回执见PUBLICATION.json；PR待审不关闭Issue。


## 2026-10-27 完整反馈与仲裁电路v2

新增[专门报告](control_v2/README_ZH.md)：124RTL项、3门级回放、8个55nm库映射面积。这是控制边界的新证据，STA/PT/完整Attention能耗仍未知；上述v1冻结结果保持原标注。

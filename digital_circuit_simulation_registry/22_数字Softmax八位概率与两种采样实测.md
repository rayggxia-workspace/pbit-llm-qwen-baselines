# 数字Softmax八位概率与两种采样：同工艺基线

2026-10-29，Issue198 / draft PR199，owner rayggxia。两条4lane门控基线已完成，100MHz、SS1.08V125C，128候选、128采样预算。均包含FP32输入转换、定点近似Softmax、保质量P8存储、控制及后端；随机源为紧凑Bivium，外部物理熵和KV读取/累加不含。

|完整路径|概率就绪 / 全部计数输出（拍）|工作功率 mW|每查询 nJ|原始面积 µm²|55nm等效 mm²|空闲 mW|
|---|---:|---:|---:|---:|---:|---:|
|Softmax＋概率流|132 / 166|0.4975|0.8301|88347.24|0.071561|0.2084|
|Softmax＋systematic|132 / 166|0.5133|0.8565|94850.28|0.076829|0.2211|
|Softmax＋独立R8比较|132 / 294|2.1603|6.3703|165121.56|0.133748|0.4021|

每拍10ns；systematic完整输出1.66µs，独立比较2.94µs。每查询能量为8查询工作窗口总能量/8，包含查询间控制间隙，不含一次播种/预热（分别约0.0650/0.5540nJ）。面积只乘0.81一次，功率和能量不缩放。前端单列价格含概率流发射，不能用集成总价减它当作后端精确独立价格。

前端使用FP32→signed11/F4、max、Q1.15指数LUT、sum、一次公共倒数及归一化。概率按累计CDF向下取整后作差，总质量256；概率1有共享flag/index，费用已含。它是近似数字Softmax，不是完整FP32精确运算核。

两条采样质量不同：systematic总数固定128、样本相关；P8/S128仅1个相位bit影响计数。独立比较一轮可0/多命中，最终按固定128平均，不能按实际命中数重归一。合成高斯σ2的P8对FP32平均TV约7.44%，四峰约6.66%；没有模型PPL，不能因Ising输入阈值8位就认定P8概率够用。

实际使用182/189/353个ICG，寄存器时钟与空闲仍计费。原未门控4lane两后端为6.1849/18.8641nJ且有时序违例，不能作为最优数字基线。v3门控Bernoulli原始复位recovery为−0.366158ns；v4保持原网表，只验证启动停钟释放复位、等待20ns再启钟的合同，仅rst_n setup2/hold1；最终setup最小0.000469ns、hold0.145801ns，ICG检查非负。余量很小，无CTS/SPEF/SDF/复位树，保留PT低slew/load表外警告，非后布局签核。

正式[详细报告](../architecture_tlm/attention_compare_20261027/digital_p8_20261029/REPORT_ZH.md)、[算法与复现](../architecture_tlm/attention_compare_20261027/digital_p8_20261029/README_ZH.md)、[中央run](records/attention-digital-p8-198-eda-20261029.json)。本机报告：C:/Users/86134/Documents/a_P_BIT/tmp/attention-compare-issue198-20261027/architecture_tlm/attention_compare_20261027/digital_p8_20261029/REPORT_ZH.md。

已归档80次完整配置RTL/门级回放、81920计数比较和78PT窗口；另12次16lane RTL预检通过，补充16lane综合作业38459583_2/_4/_6仍运行，状态见SUPPLEMENTARY_STATUS.json。原失败、原负时序和进行中范围均保留；未合并PR或关闭Issue。RAW_INDEX/COLLECTION/EVIDENCE保存原字节SHA，v3完整RAW在本机归档，其余大波形保留授权服务器，三个REPORTS本机均已逐成员SHA核验。

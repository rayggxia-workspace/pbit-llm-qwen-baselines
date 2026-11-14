# Fig.5 四部分安排建议

用户询问KV traffic和Attention energy能否合并，因为都比较相同六方案；本轮先提交PPL补测，没有改原工作PPT。

建议保留四个字母面板，把原Component costs拆成两个更清楚的部分：

|分图|内容|绘制方式|
|---|---|---|
|(a) K/S sensitivity|固定K_WH128权重，K64/128/256三条PPL曲线|横轴S16/32/64/128；突出K128/S64，主线统一seed0，三seed统计另保留|
|(b) Sampler costs|数字Softmax+R8与Ising采样核|能量和面积两个独立小坐标轴，使用当前28nm250、K128/S64来源|
|(c) Value aggregation costs|Weighted PV与Sampled PV|能量和面积两个独立小坐标轴；保留原算术面积代理与活动能量不同边界的正文说明|
|(d) KV traffic and attention energy|完全相同顺序的六方案|上为K/V堆叠流量，下为总能量；两轴共用X分类与Dense=100%归一化，各自标清纵轴|

六方案为Dense、无K筛选Ising S64、K256完整PV、K256 Ising S64、K128完整PV、K128 Ising S64。合并的是版面和横轴，不把不同指标相加。d中K蓝/V绿，能量沿原完整PV蓝/采样红；同一个百分比不代表同一种量。

若一个坐标轴同时放KV堆叠柱与能量折线，读者可能把六种互不连续方案读成演化曲线，因此优先上下对齐两个小图。图d可适当宽于其他面板，整图稍宽于4:3也可再由用户选择。

a展示参数选择的历史固定权重证据，不将旧S12-first/Philox称为当前max-first/GF实现。b/c/d仍是已有硬件/访存估计，不能宣称本轮5项PPL已证明整套最新硬件与质量完全对应。PPL结果未完成前不提前填入数值。

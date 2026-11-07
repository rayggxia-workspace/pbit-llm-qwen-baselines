## 2026-11-07 Issue225：100MHz SRAM缩减默认1088KiB，1056候选较慢

用户授权缩减100 SRAM。已删旧32KiB DMA逻辑区（16KiB返回寄存器/信用不变），Attention8×64→48KiB，100 QK转置scratch48→34KiB、输出至47KiB；两80KiB投影槽、6核GU16/Wd32/CIM256/状态96/640FMA/PV128/r32不变。初轮1216/1184/1056冷层1.207620/1.245500/1.244230ms，直接删除8个前端bank使QKV/O FIFO等待11.64→26.04、7.69→17.46µs，1056慢3.03%。保留负结果，未称无损。

默认选compact1088bw：176前端＋96Attention＝272个4KiB/16B1RW/10ns bank，逻辑对象1056KiB＋32KiB分散未分配容量保端口，未恢复DMA缓存；全部宏计价。第二轮同源原1216/1088完整冷层1.207620/1.206150ms，时间持平；覆盖面积34.14593→33.28471mm²，少.86122/2.52%。1056仍显式可选，额外省.21531但较慢。四项新＋八项旧检查通过，动作/帧/外存地址字节/输入SHA一致，队列排空；每轮源/15原件SHA保留。89bb0b9f初轮、c2d860f6第二轮执行源。

CURRENT_100MHZ与host100指向新默认；历史采样/FFN6默认1216未改，100/250分隔，250960/3核和时序失败门禁不改。范围解析136.4606GB/s30ns、冷第0层含embedding无head，36层地址分配；完整head只查tile形状，非原生整token/PPL/新RTL/PT，无新电路台账run。正式module_refresh_20261107/SRAM100_ZH.md与SRAM100_RESULTS.json；PR248交付及依赖PR249同步以PUBLICATION/DEPENDENT_SYNC为准，不自动合并。Projects待同步。

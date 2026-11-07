# 100 MHz DMA返回保持改为16 KiB

2026-11-07，Issue225 / PR248。用户选择16 KiB；当前100MHz默认入口由宿主CURRENT_100MHZ.json指向`architecture_tlm.ffn6_100mhz_20261107.ingress16.make_model`。原24 KiB工厂/核数对照/封存结果、250 MHz均保留。

## 时间的含义与本次对照

此前0.26%是旧DDR4、旧资源配置下的完整单层（含embedding、不含lm_head）时间增幅，不是DMA局部时间，也不是最新36层TPOT的实测增幅。本次重新执行当前100 MHz、6公共核、GU16/Wd32、640路共享FMA/QK、1216 KiB/304bank的完整冷第0层；保留36层地址分配，包含embedding，不含lm_head。相同seed17及原representative/SAMPLES输入；外存为136.4606 GB/s、30 ns解析服务，不是原生LPDDR重跑。

|项目|24 KiB参考|16 KiB当前|变化|
|---|---:|---:|---:|
|完整冷单层时间|1.19425 ms|1.19475 ms|+0.00050 ms / +0.04187%|
|100 MHz周期数|119425|119475|+50|
|64B数据槽|384|256|-128|
|返回数据保持面积代理|1.188795 mm²|0.792530 mm²|-0.396265 mm²|
|整体已覆盖面积代理|33.692039 mm²|33.295774 mm²|-1.176%|
|返回保持数据漏电代理|1.558613 mW|1.039076 mW|-0.519538 mW|
|片上SRAM|1216 KiB / 304bank|1216 KiB / 304bank|不变|

面积和漏电按原寄存器bank标定随容量缩放，不是新16 KiB整体DMA综合/PT。数据捕获次数未减少，不能把捕获动态能量按16/24缩小。完整36层原生LPDDR时间/能量未重跑，本次0.04187%不直接当作其结果；原0.26%与本次属于不同配置。

## 实际改动与验证

只将返回保持设为16384B/free_slots256。请求仍满足pending×64+returned_not_landed≤holding_bytes；全局请求信用256、每通道3条返回、八通道、100 MHz、目标SRAM真实bank排队/写入及全部计算/编程/状态端口不变。数据全部写完目标bank才释放槽，未引入无限外部缓冲或免费SRAM暂存。

完整冷单层配对均完成：pending/返回占用/事件/SRAM队列/预取排空，全部数据槽归还；GU/Wd帧、算术/采样动作、外存读写量及各类地址sum/xor一致。分阶段时间和原件SHA见INGRESS16_RESULTS.json，执行源和保留历史源SHA见任务索引。32 KiB DMA相关SRAM预留暂不回收；保持仍按原门控寄存器代理计价。

复现：`python -B architecture_tlm/ffn6_100mhz_20261107/ingress16.py --project C:/Users/86134/Documents/a_P_BIT --out <新输出目录>`。依赖原同SHA runtime/inputs/owner，输出24/16原始JSON、SEAL、SUMMARY。无GPU/训练/EDA/新电路台账run。

# 28nm / 250MHz概率版完整三seed结果

2026-11-10，Issue225 / PR249。三项均Slurm COMPLETED/0:0，原件SEAL、RESULT/BUDGET/VALIDATION SHA及完整36层工作量已核验。不是旧一/两层外推；此前46.01856ms估计保留历史，本次结果优先。

|口径|时间ms/token|片上能量mJ/token|含外存4pJ/bit情景mJ/token|
|---|---:|---:|---:|
|包含lm_head|51.132604|15.267553|188.432048|
|扣除lm_head阶段|43.594377|12.623289|160.896686|

已覆盖核心子系统面积6.480303mm²，均含同一常驻硬件；扣head只按同一次执行的final_norm前缀分账，不删除硬件或重启内存。时间标准差0.003457ms，三seed为代表性采样地址，不是三颗芯片。

配置：Qwen3-4B后训练revision1cfa9a7208912126459214e8b04321603b3df60c，B1/2K，36层/151936词表；3核GU16/Wd32；SparQK128、Ising/PVS64、A/S12先量化分数；832KiB/178宏；共享256FMA。原生Ramulator/LPDDR5-derived8533时序保持，不是厂商8533签核。

|seed|作业ID|时间ms|片上mJ|
|---|---|---:|---:|
|17|38644798|51.136596|15.267732|
|503|38644799|51.130608|15.267475|
|1009|38644764|51.130608|15.267452|

能量账本按gross活动减活动idle，再加全部驻留idle；各行能量与总计闭合。存储、随机源、采样器及代理项沿冻结价卡；外存能量为4/6.6/8pJ/bit情景，非原生桥测量功耗。PHY/pads/CPU/package、完整CTS/SPEF等在边界外；面积与能耗不是完整物理芯片签核。

原始JSON本机归档project_archives/tlm28p250_full225_20261110/，远端根/public3/home/t6s011227/pbit_chimera_pipeline_20260920/tlm28p250_full225_3c811d6efe58。逐文件大小/SHA、源/配置SHA和分项见同名JSON及work/rayggxia/225/full250_20261109/COLLECTION.json。不重写任何冻结源或原封存文件；本轮没有新GPU、PPL或RTL/PT。

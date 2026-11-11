## 2026-11-07 Issue225：两频率接合FFN补测与Attention有限供数

当前100MHz入口改为module_refresh_20261107.host100.make_model，保持6核/GU16-Wd32/16KiB入口/1216KiB。SS100短T C19实测每核1.306552mm²，GU25.40625/Wd26.06844pJ/DOT64，等待2.267mW；按gross活动＋非活动驻留去重，GF64/SNG已含。新增10KiB投影FIFO、离线word-interleaved权重、显式两遍读max差值u8F4/P8前端，保留原100QK供数。当前单层解析回放1.19475→1.20762ms（+1.077%），动作/外存地址守恒；面积小计33.76037，加前端宏预留0.38556为34.14593mm²，旧采样器准备面积未拆，非die。

独立250仍3核/2核、256FMA/PV64/r16/24KiB入口；新Attention替代旧v1，返回4ns/TT SRAM、8KiB有限FIFO、显式前端替代旧65拍并删除5.2µs/层预算与额外读费。3/2核新完整冷单层解析1.085992/1.114148ms，覆盖面积22.99104/22.02156mm²含旧C20面积参考，TT250短T功耗仍null。父循环1e-6ns容差触发模块1e-7ns检查的负例保留，宿主改整数周期审计，重复服务/离边沿拒绝；私有源和健康任务不改。

正式报告architecture_tlm/module_refresh_20261107/README_ZH.md；100结果RESULTS_100.json、250 REFRESH_RESULTS.json。外部10源码SHA锁定，公开只接合/数值/摘要/索引，不复制私有执行包/轨迹/库。100与250工作树/PR248、249分开，发布以PUBLICATION.json为准，未合并。无新GPU/训练/PPL/RTL/PT/台账run，两版完整原生新TPOT待后续快照；Projects待同步。

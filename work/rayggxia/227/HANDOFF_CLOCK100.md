# Issue227统一100MHz版本交接（2026-11-01）

用户要求保留100MHz专门版本并统一片上时钟，沿task/227-shared-memory / PR228，独立tmp/shared-memory-issue227-20261101，不改原3650/source和旧结果。当前共享后端默认chip100；旧复现必须显式--clock-profile legacy_mixed。不是改整个项目历史TLM的默认，也不是500MHz目标实现。

QKV/O/lm_head、QK、PV、GU/NL、SRAM、DMA前端均100MHz，DDR4时序独立。固定2048MAC/拍/2拍阵列宏，峰值0.4096TOPS；GU/NL66拍/660ns不变，QK14拍、PV反馈7拍，跨K/量化/出口/argmax原周期合同按10ns换算。SRAM消费者和DRAM写完成在下一个片上边沿捕获。20机制/回归检查通过，完整阵列STA及部分宏PPA仍未知，FMA2标量hold限制保留，不宣称统一时钟等于物理签核。

正式实现unified_v6/shared_clock.py、shared_decode.py、shared_memory.py；检查test_shared_clock.py与fixtures/shared_clock_legacy.json。正式说明/配置/结果architecture_tlm/shared_memory_20261101/clock100/，汇总器build_clock_report.py。读取RESULTS.json区分completed与未封存；新命令python -m architecture_tlm --shared-memory --clock-profile chip100。

单层配对Slurm3651统一100MHz、3652新源码legacy_mixed；共享同官方DDR配置/代表输入/随机地址，未更改精度/采样/容量/资源。完整3653依赖3651成功后运行36层+lm_head；原3650仍是混合时钟。四者每个执行source不可变，禁止重复提交健康任务。身份/实际状态/源SHA在clock100/RESULTS.json及本机*_SUBMISSION.json。个人CPU/8GiB、无GPU、完整6h上限。

收集：先本机deploy.py status --phase all；已完成后collect --phase official_chip100 / official_legacy_clock / wholeofficial_chip100。随后python -B -m architecture_tlm.shared_memory_20261101.build_clock_report --root .；只有新结果sealed后才报具体时间。旧v3回归、两配置同地址/动作/SRAM动态、每相位整拍的assert保留。原3650如完成按原HANDOFF继续核验，不混入chip100结果。

新完整3653验收：36层GU/NL帧218880/1751040、lm_head151936、status=completed、全局排空、源码/配置/输入/结果SHA；chip100总周期×10ns=总时间。双方资源容量同但时序不同，运行长短会影响漏电/DDR背景；不能直接把动态能量按频率放大五倍，不拼接旧全芯片功耗预算。

新增数值统计仍是代表流量，不是PPL/物理芯片。无新EDA或run，不公开本地module_handoff、原fixture、工艺或凭据。原20文件发布历史不改；本轮PR发布回执CLOCK100_PUBLICATION.json。Projects无写接口待维护者同步；根正式长期MEMORY由Issue28接收此窄增量，不上传本地union。

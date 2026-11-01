# DMA扩展与8通道吞吐验证（Issue227 / PR228）

本增量保持片上100MHz、8MiB SRAM、原计算阵列、采样次数、官方DDR4-1866时序与电流表；扩大有限DMA资源，并实际连接8个原生TLM入口。数值与身份见`RESULTS.json`，中文分析见`REPORT_ZH.md`。

| 资源 | 旧配置 | wide16 | wide24 |
|---|---:|---:|---:|
| 64B请求/片上拍 | 8 | 16 | 24 |
| 前端峰值GB/s | 51.2 | 102.4 | 153.6 |
| 全局在途额度 | 64 | 128 | 256 |
| 返回FIFO KiB | 8 | 16 | 32 |
| 返回FIFO可用bank | 128 | 256 | 512 |
| 原生TLM入口 | 1 | 8 | 8 |
| 人为请求间隔 | 1ns | 0 | 0 |

额度是全局总额，8个入口不各复制256。返回FIFO取自同一8MiB SRAM的空闲容量；512个bank仍分别是128bit/1RW、100MHz。FIFO读写、目标写入、bank冲突、双缓冲、依赖与计算活动全部保留。现有SRAM面积总额不变，新增控制/互连的物理成本待标定。

`bridge/bridge_async.cpp`使用真实BEGIN_REQ/END_REQ/BEGIN_RESP/END_RESP；8个initiator绑定DRAMSys原生multi-target，按地址bit6/7/8路由到channel。被一个通道阻塞的请求不阻止其它通道发起。原生FRFCFS、bankwise队列、64个每initiator活动额度与JEDEC时序不改。0ns额外间隔只是移除人为节拍，实际请求仍受100MHz前端、END_REQ和额度限制。

构建：`cmake -S bridge -B build -DCMAKE_BUILD_TYPE=Release`，随后`cmake --build build -j2`。可用`-DDRAMSYS_SOURCE=/path/to/DRAMSys`指定兼容源码；默认固定9f15aaf1fe6f05ff16a2e521a20a96f3bfe29d52。实际Slurm3662复用了原冻结工程的DRAMSys/SystemC/DRAMPower共享库，只重编新桥；精确命令与依赖SHA见BUILD_INDEX.json。上述新CMake入口未另跑一轮全依赖下载构建，不把它写成已验证构建。

公开可运行的无模型带宽探针：

```bash
python -m architecture_tlm.unified_v6.shared_bandwidth_probe --binary ./build/pbit_dma_async --config ../configs/DDR4_OFFICIAL_POWER.json --out ./probe8 --bridge-lanes 8
```

在仓库根运行；按实际位置传入绝对binary/config路径，输出目录须不存在。4MiB连续流、三种有限资源、实际DRAM命令/功耗、100MHz SRAM回写都执行，不用理想GB/s替代DRAM。

模型回放推荐显式命令：

```bash
python -m architecture_tlm --shared-memory --clock-profile chip100 --dma-profile wide24 --weight-layout tile_packed --binary /path/to/pbit_dma_async --dram-config /path/to/DDR4_OFFICIAL_POWER.json --input /path/to/representative.json --layers 1 --no-lm --out /path/to/new_result
```

旧桥/旧结果复现：`--dma-profile legacy --bridge-gap-ps 1000`配gap-only桥；多端口桥的同名控制再加`--bridge-lanes 1`。老的不支持可配gap的桥用legacy原生参数，勿传新特性。新adapter会检查特性，缺少时不会静默退回理想DRAM。

`tile_packed`将每个实际输出/输入tile连续存放：GU为64×64的g/u各矩阵块，Wd为8×64，数字矩阵为64×1024（尾块按实际尺寸）。它是离线地址重排，权重值/量化/尺度/采样/运算均不改。独立unique-index oracle检查排列双射、尾块和读回元素；实际回放核对同工作量、字节数和SRAM事件。物理地址变化明确记录，不宣称排布消融具有相同物理地址。

25项机制检查：`python -m unittest architecture_tlm.unified_v6.test_shared_memory architecture_tlm.unified_v6.test_shared_decode architecture_tlm.unified_v6.test_shared_clock architecture_tlm.unified_v6.test_shared_dma -v`。原件逐字封存在任务已有共享归档，Git只保留小型汇总与SHA索引；代表输入沿历史交接限制不在本增量公开。完整36层新作业3673与旧3650/3653各保留不可变快照，按HANDOFF_DMA.md收集，不重复提交。

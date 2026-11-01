# 片上统一100MHz估计版本（Issue227 / PR228）

**新共享后端默认使用`chip100`：片上计算、SRAM与DMA前端均为100MHz。旧版显式选择`legacy_mixed`，不改已有结果或运行中的冻结源码。外部DDR4继续用独立DDR4-1866时序。**

| 模块 | chip100 | legacy_mixed |
|---|---:|---:|
| QKV、O、lm_head数字矩阵 | 100MHz | 500MHz |
| QK、PV加法 | 100MHz | 100MHz |
| FFN GU、随机非线性-Wd | 100MHz | 100MHz |
| SRAM、DMA请求前端 | 100MHz | 100MHz |
| 跨K、量化、最终BF16、argmax宏 | 100MHz整拍 | 原500MHz宏延迟 |
| 外部DDR4 | 独立DDR4-1866 | 独立DDR4-1866 |

统一的是时钟，不是所有单元具有相同流水深度：QK保留14拍排空、PV保留7拍反馈；FFN核每帧66拍/660ns，采样T64不变。普通数字阵列2048MAC/拍，100MHz峰值为0.4096TOPS（2op/MAC），旧500MHz为2.048TOPS；阵列数量、bank数、容量和访问数据保持。数字阵列仍是吞吐宏，FMA2周期锚点有标量hold限制，尚无2048lane完整STA。

逐项修正旧快速宏：GU跨K 5拍=50ns（原10ns），Wd跨K2拍=20ns（原4ns），GU出口量化4拍=40ns（原8ns），BF16出口3拍=30ns（原6ns），argmax7拍=70ns（原14ns）。这些是保留原周期合同后换算，未冒称新RTL。其它100MHz宏向上取整成10ns整拍，TopK旧非整数ns代理分别164/815拍。

SRAM内部2.8767ns库延迟仍保留，但片上消费者在下一个10ns边沿捕获；DRAM写完成也在片上边沿被观察。Attention输入采样事件只对齐时间，不改地址/次数/顺序；PRNG就近接口与原随机性/采样合同不变。DMA前端8×64B/拍的额度不变，异步桥1ns请求保护间隔属于外存接口传输模型，不作为新的计算时钟。

因此不能把旧整机时间直接乘5：此前500MHz数字计算经常被SRAM/DRAM供数遮住；真正时间变化需要同地址回放。也不把动态动作能量按频率乘5：动作数不变时沿用相同动作单价，运行变长只重新计漏电/DRAM背景。没有宣布新全芯片功耗/面积。

## 实际回放

| 版本 | Slurm | 状态 | 时间ms | SRAM mJ | DRAM core mJ |
|---|---:|---|---:|---:|---:|
| official_chip100 | 3651 | completed | 5.418380 | 0.431049 | 49.454646 |
| official_legacy_clock | 3652 | completed | 5.459883 | 0.431708 | 49.802673 |
| wholeofficial_chip100 | 3653 | 已提交/未封存 | — | — | — |

配对已通过：同算术/采样次数、同外部地址与字节、同SRAM读写和动态能量；统一100MHz相对旧混合版时间变化-0.760%。新源码legacy_mixed还复现旧v3的实际DRAMSys时间、全部SRAM与DRAM结果。

普通数字MAC理想活动时间从25600ns增至128000ns，确为五倍；端到端没有同步放大，说明当前供数瓶颈遮住了大部分计算。小幅正负差来自请求到达/行局部性/仲裁顺序变化，不能宣称降频本身加速。SRAM事件数逐项严格相同；动态累计浮点尾差-4.66e-15mJ，通过次数×单价独立复算而不改原结果字节。

单层配对含embedding与一层、无lm_head，B1/2K、K128/S64、seed17代表流量。完整36层+lm_head另跑新作业；原3650保留为旧混合版，不重复提交或改source。20项机制/时钟检查通过，其中旧合成时序fixture精确回归、地址/动作守恒及片上相位整拍检查。无新EDA/PPL。

命令：`python -m architecture_tlm --shared-memory --clock-profile chip100 ...`；旧复现用`--clock-profile legacy_mixed`。配置快照为本目录chip100.json/legacy_mixed.json，执行源码/配置/输入/结果SHA见RESULTS.json。

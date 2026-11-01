# Issue227 DMA扩展交接

负责人rayggxia，独立tmp/shared-memory-issue227-20261101，分支task/227-shared-memory，PR228/main。当前HEAD与发布回执见DMA_PUBLICATION.json；本地Git历史落后远端API提交，禁止直接force-push。此次依旧沿原Issue，不另开重叠任务。

正式说明architecture_tlm/shared_memory_20261101/dma_expand/README_ZH.md和REPORT_ZH.md；机器结果RESULTS.json；编译BUILD_INDEX。推荐--clock-profile chip100 --dma-profile wide24 --weight-layout tile_packed，使用8端口新版桥；旧控制必须显式legacy/gap1000/lanes1或对应旧桥。不是更换DDR/采样/计算阵列。25检查通过，负面结果保留。

本机work/rayggxia/227/deploy.py保留不可变快照提交/收集：python -B deploy.py status --phase all；collect --phase <phase>。构建3662完成，新桥root在BUILD_INDEX，二进制SHA e7b2e071df221f0fa5a3e3e41cf3c52c41b411baa8466edef7f690eb7deed9bd。不要重复submit已有SUBMISSION。快照SHA/共享归档原件及原字节索引在各SUBMISSION/COLLECT；Git只放小型汇总与身份。raw fixture继续本地授权限制，不在此次发布。

额外seed配对：lanesofficial_base_s503/1009（3669/3670），lanesofficial_packed24_s503/1009（3671/3672）；只读completed封存JSON后跑build_dma_report.py。状态以RESULTS准确列项，不把某个seed的V地址当全部seed相同。

完整推荐whole_lanesofficial_packed24：Slurm3673，source15f6d5ca8ff2e5950778016dc57bfd1e71a99c17ef244d54c371531d3d571ae5，root /home/Hongjie_Zeng/projects/pbit-shared-memory-20261101-issue227/whole_lanesofficial_packed24_15f6d5ca8ff2。1CPU/8GiB/6h，无GPU；依赖3668成功，已提交。预计1–2h。旧100MHz3653和混合3650保留健康，均不得重复提交/改source。

完整验收：status completed、36层GU/NL帧218880/1751040、lm_head输出151936、5,354,946,560B权重与源/配置/输入/结果SHA、全局pending/FIFO排空、chip_cycles×10ns、36层所有相位覆盖，单全局DDR背景只计一次。对照同资源控制；不简单拼单层或复用旧时间。只是在3个代表场景上循环地址，不是数值PPL。

所有模块动态、容量、bank数、工作量守恒通过；8MiB SRAM价格不变。更大的DMA描述符/仲裁/互连/时钟成本未知，不能说免费；不把memory-only表当全芯片PPA。没有新EDA run。继续在同PR更新Issue、本人STATUS、HANDOFF和MEMORY增量，发布后逐文件回读；完整未验收故不关闭Issue/不合并，Projects无写接口待同步。

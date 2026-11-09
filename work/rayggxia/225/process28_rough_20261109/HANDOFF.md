## 2026-11-09：28nm Qwen3-4B已有可复算条件整机初估

Issue225 / PR249，rayggxia。用户要求大体面积/时间/功耗；保持严格缺价null，另建process_28nm/rough_estimate_20261109。250三核/500两核、GU16/Wd32、B1/2K/K128/S64、960KiB：核心面积中心6.86/6.89mm²，情景5.4–10.2/5.4–11.0；含head45.90/40.99ms，去head39.29/35.29ms。片上9.74/9.79mJ、.212/.239W；外存4pJ/bit下总182.94/183.00mJ、3.99/4.46W，6.6pJ约295.5/295.6mJ。不是板级功率或含PHY/CPU/pad的die面积。

沿v3有限bank/DMA小回放投影36层，新六head1024/1152/2048探针均SEAL，拟合完整词表593×256+128尾。没有新36层native运行/PPL/RTL/PT。公共CACTI短CPU作业38638027已12s完成0:0，28/55同组织4KiB128b1RW300K结果和SHA已收；28原始240bank面积1.3250mm²，跨工艺55校准残差迁移中心1.6735mm²，明确不是28foundry校准。PV时序失败组成代理保留每头128FP32状态，500FMA用28nm250价代理；DMA/FIFO按实测28寄存器外推，向量/CIM/布局预留显式，缺项不暗当零。

22输入SHA/六headSEAL/两层结果SEAL、面积一次、SRAM动作、能量时间单位/外存对账通过。原v3封存/55默认不改，PR待审不合并，Projects待维护者同步。发布状态以本目录PUBLICATION.json为准；没有把本地完成当远端已完成。

恢复：先读同PR最新head与STATUS；运行architecture_tlm/process_28nm/rough_estimate.py，再verify_estimate.py。SOURCES绑定本地既有原件；PUBLIC_FILES只列本任务小型证据，不含工艺库/大轨迹。六探针无需重复；CACTI_SUBMISSION保存唯一作业，不重新submit。500FMA、PV紧凑实现、28SRAM及原生完整36层是下一步；补价可重计价，改服务需新冻结回放。最初CACTI辅助导入和登录节点Python3.6参数错误都在sbatch前，随后仅提交38638027，没有重复健康任务。

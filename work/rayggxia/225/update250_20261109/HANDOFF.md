# 28nm250最新TLM交接

## 2026-11-09 28nm250 TLM最新价卡已接入：本地完成待发布

Issue225/PR249，rayggxia；task/225-tlm-unified250-20261107，base task/225-norm-stream-20261106，工作目录tmp/tlm-unified250-issue225-20261107。新SC/FMA/整数GU零余量价、主数字参考、17Attention卡可用，选原Ising/R8，S12优先分数前端保持；PV新实测参考按保留固定状态的2/16结构代理，V控制按真实miss/reuse，平台宏显式闭合，无旧“PV缺价”。不是全芯片PPA。

六CPU回放封存：250两层+384head2.2118ms与原逐项不变，500单层.99729ms且BUDGET不变；新250单层及1024/1152/2048head探针通过；六账本/来源/防覆盖检查通过。面积6.480303mm²，较6.566340少1.31%。一/两层及head条件外推完整46.01856ms、扣head阶段39.408936ms，核心15.016133mJ、4pJ情景总188.191138mJ；不是实际完整36层/原生LPDDR运行。head分账保留前缀重叠预取64KiB，硬件常驻面积不变。

来源与原件SHA见本work/PLAN、EXTRA_PLAN、ARCHIVE_INDEX、UNIT_TESTS及正式250MHz/UPDATED_TLM_20261109.json；报告UPDATED_TLM_20261109_ZH.md。3新归档SHA核验。原冻结任务、55/500默认不改，无新EDA/GPU。当前本地完成，发布回执见本work/PUBLICATION；PR待审未合并，Projects待维护者同步。下一步完整回放用新绑定冻结新目录；数字R8整链必须按可变输出实际轨迹，不能强塞S64。

---


复现：先运行process_28nm/refresh250.py更新250价卡（读取现有PRE_REFRESH基线，不动500）；运行test_refresh250.py。已有执行不能覆写，原件zip恢复后按PLAN/EXTRA_PLAN冻结命令改--out到新的绝对目录。run_validation.py是本轮一次性冻结/执行工具，collect.py核验后产生明确外推；finalize.py是本地一次性归档/交付，不重复覆写归档。

物理面积/芯片签核仍未完成，按选定边界条件账本闭合；新profile中的full_system_ready=false不能解读为模块尚未仿真。严格保留PV负hold、紧凑宽度和16bank控制到9bank runtime代理。量化A/S12与B/FP32都已有价，当前按用户要求选A，不能只换价不换两遍读与周期。新小面积Ising只注册可选，不自动换；新R8更费能不换。全部CPU执行已完成，无需GPU/Slurm查询。

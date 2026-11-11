## 2026-11-08 Issue225：TT250 v3已接主线，能量账本在声明边界内闭合

用户要求接入最新核并核对整机能量。复用PR249原250主线，3核/960KiB/16KiB入口及有限FIFO、预取、回压、真实bank/DMA不变；FFN delta_pipeline_v3已验收，单核1.374062065mm²（raw×.81一次），GU16/Wd32服务19/35拍、76/140ns，共覆盖22.086073mm²。原SS100配置语义不变，历史失败及旧封存不改。活动gross＋剩余核时idle，本来已正确；没有查出旧FFN gross/idle重复计费。本轮补逐资源26行、两种FFN等价公式、门控归属、外存和总和校验，ENERGY_LEDGER明确CLOSED_WITHIN_DECLARED_MODEL_BOUNDARY、silicon_complete=false。

原生LPDDR冷单层38629484完成：1.195020ms，片上0.550405mJ，4pJ/bit外存4.120609mJ，合计4.671014mJ；不是整token。5件封存＋SEAL逐SHA、矩阵工作量/32维SparQ核对通过，4项新单测＋11项catalog隔离检查通过。原件project_archives/tlm_energy225_20261108/gate，小汇总/账本CSV/输入SHA在work/rayggxia/225/tt250_v3_energy_closure_20261108。完整36层＋head三seed17/503/1009为38629485_[0-2%2]，各1CPU12GiB8h、最多2并发、0GPU，当前运行/待并发；不重复提交或改冻结快照。snapshot SHA c1820e20bc732959bef691b1ba79ced2037dc3b1e8460331dfffebf9753b3187，manifest6d4c40c2b8ff02e1ee7e59c0d5d3d4dffba27c35f7c7255923750e9e5f8166c5。

重要纠正：配置末尾r16是16路FP32归约，不是SparQ维数。SparQ一直32维、单层2621440 QK MAC；此前245/247文档所谓r32→r16筛选维度缺口是误读，本条明确撤销该项，并非改变算法。仍须对齐跨模型试接的实际供数/访存/计费，24pilot不是整模型。原profile job/ICG标签和incremental/frame兼容字段已整理，执行profile精确字节单存；用到的数值输入不变，原远端快照不改。

尚未标定的CIM并行读出/编程接口增量、全NoC/CTS/PHY和FIFO控制泄漏明确列边界；部分向量/格式/PV2为已有代理，外存4/6.6/8pJ每bit是情景，不是原生LPDDR功率实测。v3仅前布局且有库表告警，非流片签核。正式sram1216_20261106/250MHz/ENERGY_CLOSURE_ZH.md。发布与逐字回读见本目录PUBLICATION.json；PR249保留依赖248、待审不合并，Issue225 open，Projects无写接口待维护者同步。完整token结果待收齐，不造最终数据或冒充已合入main。

---


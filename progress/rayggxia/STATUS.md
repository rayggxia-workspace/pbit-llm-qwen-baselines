## 2026-11-08：28nm已有数据足够先搭组件接合版

用户询问现有28nm数据可否先搭TLM、等待补测确认。已只读消费204/198最新5份JSON，新增process_28nm/prepare_bindings.py与250/500 BINDINGS：FFN18/34拍、250/500服务72/136和36/68ns、同一GU/Wd后端；state/codec/scale、1KiB暂存代理及13/12张Attention合格卡已收。显式A前端＋gap输入Ising，32加载握手不双计，旧ab_both仅参照；不暗用55价格、28面积×1。已补4项CPU集成验证，无新TLM整机/RTL/PT/EDA/GPU任务。

后续可沿成熟bank/DMA/credit/重叠执行器，存储与公共服务先给显式宏，再用PPA替换；不用等全部PT才能搭。当前缺SRAM28组织/2或4ns/价、DMA向量、PV紧凑价与共享FMA新流水绑定，整机值保持null。250可用旧合格FMA16/C4，500仍待合格数字结果；FFN0setupunc与Attention10%period分别标注。未确定最佳核数、未宣称完整28芯片结果，不改55默认和健康冻结任务。正式process_28nm/README_ZH.md；4检查及输入SHA见VALIDATION；发布以本目录PUBLICATION为准，PR249待审不合并，Projects待同步。

---

## 2026-11-08 22:51：独立250MHz完整评估2/3seed已完成

38629485的seed17/503已完整36层＋head并0:0完成，SEAL/VALIDATION/工作量/账本与原字节SHA通过，已归档project_archives/tlm_energy225_20261108/0和1。时间均50.418948ms，片上25.206577/25.206643mJ，外存4pJ情景总198.370253/198.372088mJ，覆盖22.086073mm²。末seed1009已完成36层及finalnorm、head运行，预计CPU墙钟20～60分钟，不承诺。

正式250MHz/FULL_PARTIAL_20261108.md/JSON，仅部分结果、未算三seed最终汇总；不与245不同胶合源混seed。三模型245目前7/36已核，5健康＋3恢复worker运行，暂无新错误。未重提/改冻结源，无新GPU/RTL/PT/PPL。PR249仍draft/open未合并，Projects待同步。

---

## 2026-11-08 用户决定：小前端成本缺口先沿用，不阻塞现有任务

当前FP32→S12/握手尚未独立拆净的增量PPA可以先用宏预算；已完成结果保留，健康任务继续，不因本项重跑PPL/训练/全TLM。以整个实测A作偏大的额外情景（非严格物理上界），100/250MHz面积.131731/.076112mm²，占当前覆盖.396%/.345%；全程工作逻辑压力计入输入读约占整机能量.061%/.115%。全部服务额外串行.7488/.308736ms，按现8/4实例均摊.0936/.077184ms，非集成延时保证。当前已经有前端非零预留，不再叠加整块A。

正式local_integration_A/PROVISIONAL_USE_ZH.md和PROVISIONAL_BUDGET.json，数值路径A仍S12/F4→整数max-gap→U8/P8；冻结较宽前端时序/成本＋S12地址轨迹的组合标签保留。ready=false只表示未整链PPA，不再作为禁止宏级评估的门槛；不宣称B继承A的PPL。没有改默认/冻结源码或重跑健康任务。另有245残差地址执行bug独立修复，不混为成本近似。发布见PROVISIONAL_PUBLICATION，PR249未合并，Projects待同步。

---

## 2026-11-08 Issue225：侧对话A适配补充已隔离复核

已找到根交接local_integration_A，保留原字节并收录。25来源SHA/192查询24576分数、27组旧S12/P8及6912固定激励递推回归通过，新VALIDATION与原回执字节相同；不是RTL/GF64/PPL/PPA。旧后端仅128全有效，当前固定2K/K128适用；通用mask另列，不重做整核。

数值接口/计费合同已明确，但未补四路FP32→S12转换＋握手增量PPA或匹配去重gap后端、集成握手/分窗，全链仍null/ready=false。未改运行源码/默认/冻结任务，不交新EDA/GPU；发布看LOCAL_ADAPTER_PUBLICATION，PR249不合并，Projects待同步。

## 2026-11-08 Issue225：新前端PPA已核，当前PPL对应A

已读取198/199新交接55e06025，公开profile blob及四张价卡单位/STA/读字检查通过。当前完整PPL明确S12/F4先量化→整数max-gap→U8/P8，后续接入依据选A=s12_max_gap，B仅对照；新版A100/250面积.016466/.019028mm²、gross.176562/.302215nJ、65/67拍。旧审计“B仅宏价”已更新为新实测，旧原文保留。

旧ab_both已有S12 scores/max/gap，优先复用其后端并接FP32/S12转换；不得整块加A或扣A。提供方全链replacement_ready=false，净价待去重；本轮仅消费核验和文档，不改runtime/default/冻结作业，无新TLM/PPL/PT。公开及交接见score_front_audit_20261108/LATEST_PPA_PUBLICATION.json；PR249不合并，Projects待同步。

## 2026-11-08 Issue225：Attention分数前端成本审计已整理

用户要求给其他对话的文件已写：module_handoff/attention_score_front_compare_20261108/HANDOFF_ZH.md。关键：S12后整数差转U8只是clip；已有A的SS100独立PPA为.015050059mm²/.166291667nJ/65拍；B仍宏价，比较／减法／专用转换／存储组织／旧准备资源／代理价卡未配对。FP32差→U8可专用融合，不能直接断言需完整FPU或固定面积倍率。四正式文件、13来源SHA及单位校验通过，根同字节镜像；发布见本任务PUBLICATION。

没有改默认/冻结任务/owner源码，没有新TLM/RTL/PT/GPU/PPL；保留S12为参考是建议，非用户已授权切回。Issue225/PR249接续，关联198/199；PR不合并，Projects待维护者同步。

## 2026-11-08 28nm目录已发布

源23807efcfc338d214047b574103a7b033a8bb8a0，10文件逐内容回读一致；Issue225评论6720845666及PR249已同步。PUBLICATION.json记录回执，PR仍draft/open/unmerged，整机TLM未启动、整机值仍null；Projects待维护者同步。

## 2026-11-08 Issue225：建立独立28nm准备目录，未运行完整TLM

用户要求先建对应工艺文件夹。新增architecture_tlm/process_28nm：250MHz已标定FFN/BF16/同步A9组件、500MHz诊断及零uncertainty条件索引、缺项与来源SHA。28HPC+ TT0.9V，面积×1，不套55的.81；28原C19门限缓存18/34拍与55delta_v3隔离。PROCESS_PROFILE整机时间/面积/能量null、full_system_ready/default_enabled均false，无整机运行入口。四来源SHA/三组件PVT/面积/同步A9/无整机值核验通过。

沿Issue225/PR249/task/225-tlm-unified250-20261107，未改55默认或38629485/38631668冻结运行；无新TLM/EDA/GPU/PT。源与公开状态见work/rayggxia/225/process28_setup_20261108/PUBLICATION.json，未有回执前仅本地完成。Projects待维护者同步，PR不合并。

## 2026-11-08 Issue225：28nm250MHz 44功耗窗口消费端复核

用户问新矩阵结果是否需调TLM；确认44窗口为28HPC+ TT0.9V250MHz，非55nm新价格。复核3主归档及1715报告成员SHA通过：FFN8/BF1615/A921窗口，A9 PT hold−.099703仅诊断。合格FFN .373801302mm²、GU/Wd10.1625/9.254021pJ/DOT64，18/34拍、72/136ns，停源等待.6209mW（漏电.279mW）；28面积×1，不套.81。BF16/FMA16/C4 .06245379mm²、continuous3.304622pJ/FMA；mixed QK wrapper及其他系统模块需独立边界。

正式module_refresh_20261107/tsmc28_review_20261108：报告、review.py、CANDIDATE_COMPONENTS/COMPARISON/SOURCE_INDEX/VALIDATION。候选default_enabled=false；固定旧冷层工作量/时长，三FFN核47.34→13.21µJ/少72.10%，3核面积4.122→1.121mm²，不是新28整机TPOT/PPA。TIE功耗未知null、面积已计；500三配置待收。读取最新POWER_RESULTS而非老profile null；不修改owner204资料或55默认/冻结38629485，不新交TLM/EDA/PPL。接28整片时需同时调服务周期、数字价格/等面积、存储和其他模块，不能混工艺宣称全片收益。发布以本任务PUBLICATION为准，PR249待审不合并，Projects待同步。

---

Published source 07bc39de3f75b3a10628862879921bfde8ae91a4;30 explicit files content-readback verified. PR249 open/draft/unmerged;full38629485 pending. Issue225 comment6718333560,PR247 r16 correction6718334719. Projects pending maintainer sync.

## 2026-11-08 Issue225：TT250 v3已接主线，能量账本在声明边界内闭合

用户要求接入最新核并核对整机能量。复用PR249原250主线，3核/960KiB/16KiB入口及有限FIFO、预取、回压、真实bank/DMA不变；FFN delta_pipeline_v3已验收，单核1.374062065mm²（raw×.81一次），GU16/Wd32服务19/35拍、76/140ns，共覆盖22.086073mm²。原SS100配置语义不变，历史失败及旧封存不改。活动gross＋剩余核时idle，本来已正确；没有查出旧FFN gross/idle重复计费。本轮补逐资源26行、两种FFN等价公式、门控归属、外存和总和校验，ENERGY_LEDGER明确CLOSED_WITHIN_DECLARED_MODEL_BOUNDARY、silicon_complete=false。

原生LPDDR冷单层38629484完成：1.195020ms，片上0.550405mJ，4pJ/bit外存4.120609mJ，合计4.671014mJ；不是整token。5件封存＋SEAL逐SHA、矩阵工作量/32维SparQ核对通过，4项新单测＋11项catalog隔离检查通过。原件project_archives/tlm_energy225_20261108/gate，小汇总/账本CSV/输入SHA在work/rayggxia/225/tt250_v3_energy_closure_20261108。完整36层＋head三seed17/503/1009为38629485_[0-2%2]，各1CPU12GiB8h、最多2并发、0GPU，当前运行/待并发；不重复提交或改冻结快照。snapshot SHA c1820e20bc732959bef691b1ba79ced2037dc3b1e8460331dfffebf9753b3187，manifest6d4c40c2b8ff02e1ee7e59c0d5d3d4dffba27c35f7c7255923750e9e5f8166c5。

重要纠正：配置末尾r16是16路FP32归约，不是SparQ维数。SparQ一直32维、单层2621440 QK MAC；此前245/247文档所谓r32→r16筛选维度缺口是误读，本条明确撤销该项，并非改变算法。仍须对齐跨模型试接的实际供数/访存/计费，24pilot不是整模型。原profile job/ICG标签和incremental/frame兼容字段已整理，执行profile精确字节单存；用到的数值输入不变，原远端快照不改。

尚未标定的CIM并行读出/编程接口增量、全NoC/CTS/PHY和FIFO控制泄漏明确列边界；部分向量/格式/PV2为已有代理，外存4/6.6/8pJ每bit是情景，不是原生LPDDR功率实测。v3仅前布局且有库表告警，非流片签核。正式sram1216_20261106/250MHz/ENERGY_CLOSURE_ZH.md。发布与逐字回读见本目录PUBLICATION.json；PR249保留依赖248、待审不合并，Issue225 open，Projects无写接口待维护者同步。完整token结果待收齐，不造最终数据或冒充已合入main。

---

## 2026-11-07 Issue225：100MHz SRAM缩减默认1088KiB，1056候选较慢

用户授权缩减100 SRAM。已删旧32KiB DMA逻辑区（16KiB返回寄存器/信用不变），Attention8×64→48KiB，100 QK转置scratch48→34KiB、输出至47KiB；两80KiB投影槽、6核GU16/Wd32/CIM256/状态96/640FMA/PV128/r32不变。初轮1216/1184/1056冷层1.207620/1.245500/1.244230ms，直接删除8个前端bank使QKV/O FIFO等待11.64→26.04、7.69→17.46µs，1056慢3.03%。保留负结果，未称无损。

默认选compact1088bw：176前端＋96Attention＝272个4KiB/16B1RW/10ns bank，逻辑对象1056KiB＋32KiB分散未分配容量保端口，未恢复DMA缓存；全部宏计价。第二轮同源原1216/1088完整冷层1.207620/1.206150ms，时间持平；覆盖面积34.14593→33.28471mm²，少.86122/2.52%。1056仍显式可选，额外省.21531但较慢。四项新＋八项旧检查通过，动作/帧/外存地址字节/输入SHA一致，队列排空；每轮源/15原件SHA保留。89bb0b9f初轮、c2d860f6第二轮执行源。

CURRENT_100MHZ与host100指向新默认；历史采样/FFN6默认1216未改，100/250分隔，250960/3核和时序失败门禁不改。范围解析136.4606GB/s30ns、冷第0层含embedding无head，36层地址分配；完整head只查tile形状，非原生整token/PPL/新RTL/PT，无新电路台账run。正式module_refresh_20261107/SRAM100_ZH.md与SRAM100_RESULTS.json；PR248交付及依赖PR249同步以PUBLICATION/DEPENDENT_SYNC为准，不自动合并。Projects待同步。

---

## 2026-11-07 Issue225：100/250资源利用率复核（只读）

当前100/250数字池QKV/O有用MAC槽利用率83.0/87.6%、91.8/92.0%，含流水服务占时88.6/93.1%、97.5/97.7%；没有明显大量闲置数字lane。整层37.3/41.5%因FFN等分阶段工作，不可按整层空闲比例砍核。FFN GU/Wd采样利用率100为49.2/89.7%、250为40.2/75.3%；100GU多结果信用等待、250GU多等权重，核池按更忙Wd配置。6/3核合理；旧100 6→5核FFN多22.8µs省约1.30655mm²，旧250 3→2整层慢2.593%省旧价.96948，均有代价，960版2核未测。

100仍有DMA SRAM32KiB未使用，Attention64→48/组可迁移候选128KiB，合计160KiB/1.0765mm²（1216→1056候选），须100真实重排回放；其投影两槽80KiB确实用满，不能套25032KiB。两版激活128区最高地址96KiB、跨K96区最多76活跃组，可试省32+16KiB/.32296mm²，但状态原高水位到96须改槽映射。跨阶段普通Attention暂存与FFN跨K状态可研究共享bank，未验证，定制CIM权重不得当普通SRAM免费混用。

默认与算子不改，无新仿真/PPL/RTL/PT。250960KiB/3核参考20.87233仍非最终die；TT短T setup−.421007时序失败、合格核价null，失败映射仅诊断；全片CTS/互连/CIM/PHY等也未闭合。正式250MHz/RESOURCE_REVIEW_ZH.md/JSON；Issue225/PR249交付见同任务PUBLICATION.json，不把审阅当新测量。建议100补SRAM迁移、250先收合格核价后冻结论文架构基线，后续小优化做消融。

---

## 2026-11-07 Issue225：250MHz SRAM实际缩至960KiB

已读最新204/198交接：TT250短T/C19 setup−0.421007ns仍失败，去掉0.5uncertainty的＋79ps只作条件解释，未接受新核价/未改约束。用户授权执行上轮SRAM候选，本次250默认1216→960KiB：普通QKV/O/head权重两槽80→32KiB、删未使用DMA SRAM32KiB、八组Attention64→48KiB。16KiB寄存器返回保持/信用、3核GU16-Wd32、256FMA及FFN256权重/96状态KiB不变；100代码/默认/健康冻结任务不动。

真实bank由304→240（前端176→144、Attention128→96），16B/1RW/4ns，输出搬至47～48KiB，粗分数旧对象失效后复用，128项V缓存保留。四项布局/数据/冲突/全词表tile检查通过。三版同源同seed17完整冷单层：1216/1088/960分别1.085980/1.086184/1.085700ms，近似持平；动作/帧/外存各类地址与字节一致，实际SRAM读多400B计费，写入一致，队列排空/4ns通过。解析136.4606GB/s30ns，含embedding无head，按36层分配地址；非完整原生token/PPL。

按已折0.81的宏面积，SRAM8.18162→6.45918、旧TT核参考覆盖面积22.59477→20.87233mm²，少1.72245。SRAM动态约.189587mJ基本不变，漏电.65149→.51420µJ；含4pJ/bit外存参考4.701432→4.701292mJ/冷层，主要省面积。250物理4ns未签核、无新RTL/PT/GPU/PPL/台账run。正式250MHz/SRAM_COMPACT_ZH.md/RESULTS.json；源执行a63cf1de246fb59a6da939cacfca3b76940d4f14，九原件SHA及恢复命令在sram_compact250_20261107。原目录名保留，默认compact960；reference1216/compact1088显式可选。PR249交付/回读见PUBLICATION.json，待审未合并，Projects待同步。

---

## 2026-11-07 Issue225：250面积审查及TT短T时序失败标签

用户询问250还有何缩面积、是否漏接改动。本轮只审查/更正证据，不改资源或bank，不新跑TLM/RTL/PPL。确认250投影tile256×K64×BF16=32KiB，仍继承100两槽各80KiB，多留96KiB，按现4KiB宏约0.645918mm²；历史DMA返回SRAM32KiB另可回收约0.215306；Attention64→48KiB/组是未实施候选，另省128KiB/0.861224。合计1216→960KiB、参考22.59477→20.87233mm²仅容量计价，不是已验证设计；删bank必须重排并回放。2核已有对照慢约2.593%、旧核价省0.96948mm²；不优先256→192数字池，理想权重吞吐128→96GB/s。PV算术减半也只约省0.222，状态不能减半。

最新204交接已收TT250短T/C19，setup−0.421007ns未过，失败映射1.498438mm²/核。公共FFN_PROFILE/bindings与250模型/计价从pending改timing_failed，有效core仍null，失败价格不能替代达标价；100有效价不变。按失败映射面积作敏感性3核24.18165，不能据旧核参考许诺最终20.87。建议先闭合FFN加载侧门限路径并优先整理投影缓冲/历史SRAM。正式AREA_AUDIT_ZH.md/JSON位于250目录；当前304bank/1216KiB/3核/default16与所有冻结原件均不动。

归档SHA、单位、guard及100保留价验证见area_opportunities250_20261107的EVIDENCE/VALIDATION；无新电路台账run。上传以PUBLICATION.json为准，PR249待审未合并，Projects待同步。

---

## 2026-11-07 Issue225：250MHz也改为16KiB返回保持

用户决定250版本也降为16KiB。model.make_model / run.py均默认16，24可显式对照；未改100、1216KiB/304bank或32KiB历史DMA SRAM预留。最新有限FIFO/宽前端宿主下，3核完整冷单层1.085992→1.085980ms，2核1.114148→1.114144ms，只有1～3周期差别，视为时间不变。相同seed17和输入SHA，GU/Wd帧、算术/采样、外存字节/地址摘要守恒，队列排空，4ns tick通过。已返回未落地峰9792B，不包含额外在途预留；原有限信用断言始终保留。

寄存器保持面积代理1.188795→0.792530mm²，少0.396265；3/2核覆盖面积22.594773/21.625293mm²。只随容量减少保持面积/等待漏电，不缩捕获动态能量。TT250短T/C19 PPA仍待收，旧C20面积参考不冒充实测。测试为136.4606GB/s/30ns解析外存完整冷第0层（含embedding无head，36层分配），非完整原生LPDDR token。正式250MHz/DMA16_ZH.md及DMA16_RESULTS.json；旧原件/健康作业不动，无新GPU/EDA/PPL/台账run。发布以PUBLICATION.json为准，PR249待审未合并，Projects待同步。

---

## 2026-11-07 Issue225：两频率接合FFN补测与Attention有限供数

当前100MHz入口改为module_refresh_20261107.host100.make_model，保持6核/GU16-Wd32/16KiB入口/1216KiB。SS100短T C19实测每核1.306552mm²，GU25.40625/Wd26.06844pJ/DOT64，等待2.267mW；按gross活动＋非活动驻留去重，GF64/SNG已含。新增10KiB投影FIFO、离线word-interleaved权重、显式两遍读max差值u8F4/P8前端，保留原100QK供数。当前单层解析回放1.19475→1.20762ms（+1.077%），动作/外存地址守恒；面积小计33.76037，加前端宏预留0.38556为34.14593mm²，旧采样器准备面积未拆，非die。

独立250仍3核/2核、256FMA/PV64/r16/24KiB入口；新Attention替代旧v1，返回4ns/TT SRAM、8KiB有限FIFO、显式前端替代旧65拍并删除5.2µs/层预算与额外读费。3/2核新完整冷单层解析1.085992/1.114148ms，覆盖面积22.99104/22.02156mm²含旧C20面积参考，TT250短T功耗仍null。父循环1e-6ns容差触发模块1e-7ns检查的负例保留，宿主改整数周期审计，重复服务/离边沿拒绝；私有源和健康任务不改。

正式报告architecture_tlm/module_refresh_20261107/README_ZH.md；100结果RESULTS_100.json、250 REFRESH_RESULTS.json。外部10源码SHA锁定，公开只接合/数值/摘要/索引，不复制私有执行包/轨迹/库。100与250工作树/PR248、249分开，发布以PUBLICATION.json为准，未合并。无新GPU/训练/PPL/RTL/PT/台账run，两版完整原生新TPOT待后续快照；Projects待同步。

---

## 2026-11-07 Issue225：用户选定100MHz DMA16KiB

当前100MHz默认6核/GU16-Wd32/共享QK/1216KiB，返回数据保持24→16KiB；CURRENT_100MHZ.json指向ffn6_100mhz_20261107.ingress16.make_model。原24KiB model/PROFILE/RESULTS与250MHz不改。全冷单层（36层地址分配、含embedding无head）解析136.4606GB/s/30ns、seed17：1.19425→1.19475ms，+0.04187%/50拍；算术/采样/外存字节和地址sum/xor一致、队列排空。非原生LPDDR整token；历史0.26%是旧DDR4完整单层增幅。覆盖面积33.692039→33.295774mm²，保持1.188795→0.792530mm²，沿原bank校准缩容量，无新PT，不按容量缩捕获动态能量。32KiB DMA SRAM预留保留，控制器/PHY/路由未知成本不置零。报告architecture_tlm/ffn6_100mhz_20261107/INGRESS16_ZH.md，原件/SEAL位于work/rayggxia/225/ingress16_20261107/replay。

修改/单层校验本地完成；远端状态见同任务PUBLICATION.json，PR248待审不合并。无新GPU/EDA作业或电路台账run；Projects待维护者同步。

---

## 2026-11-07 Issue225：Attention最新v2复核与可转交下一步文件

用户要求查看Attention最新改动、整理文件给其他对话。已核PR199 head4ed760ffd3742add846d211900e9e866e2039418、PR248的100MHz六核默认、PR249早期整机快照。正式文档architecture_tlm/module_handoff/ATTENTION_NEXT_ACTIONS_FOR_AGENT_ZH_20261107.md，根镜像同字节。

已完成内容明确复用：250 v2返回wake4ns和同宏TT SRAM单价、有限QK/PV与原生模块回放；256三seed586.136us/378.57uJ/13.61588mm²，含共享池+672KiB SRAM的首层至O范围，非整token。下一步只列三项：普通投影按MAC消费节拍的有限FIFO/信用、返回写/计算读仲裁、宽分数max差值→8位LUT/P8前端宏事件/合同。48KiB/组与PV64/128均后续可选，不作为新前置门槛，不重做Ising/训练/全片RTL。

宿主接合差距有源码证据：PR249/root250 bootstrap仍bind早期attention_unified250_20261107 vendor；unified_clock只改mem/request/common，不含v2 ingress wake；计价也仍旧SS。整机对话需新快照接v2/TT计价并逐tick验证，旧健康任务不改/不重交。100MHz6核/16-32/640FMA/PV128/归约32与250的256/64/4采样/16归约分隔，不套TT价或直接改100资源。

本轮只读审阅和文档/索引，无新服务器/GPU/native/RTL/PT/PPL、无新数字台账run，不修改198/249源码或100/250默认。来源记录源文件SHA与公开blobSHA、两默认隔离检查；任务辅助work/rayggxia/225/attention_followup_20261107。文档发布以PUBLICATION为准，PR248待审不合并，Projects待维护者同步。

---

## 2026-11-07 Issue225：用户选定100MHz FFN六核，SRAM维持1216KiB

新增architecture_tlm/ffn6_100mhz_20261107，真实构造默认6公共核，组合现100MHz sharedQK/有限供数；前16/后32分层、18/34拍，8核回退/12核对照。CURRENT_100MHZ.json在sram1216宿主下指向新入口；旧冻结参考和250目录不改。目标C19、GU18/Wd19bit、外传20bit及跨K64bit仅宏合同，按旧C20每核价，不假称新C19实测。

同实际1216KiB/304bank/32权重槽/两state口两信用的冷完整形状FFN，本地解析外存136.4606GB/s30ns：5/6/8/12核589.06/566.26/568.40/576.48us。四配置帧6080+3040、算术/随机动作和外存地址sum/xor守恒，写量相同，输入缓存读随核数真实改变；12类检查通过。非新原生LPDDR整token/PPL/PT。5核比6核慢约4.03%；粗权重吞吐5核120.47、6核144.56GB/s，峰值136.46理想最少6核，额外串行开销余量约20.19ns/帧；实际110GB/s理想可5，不能称通用全系统最小。

SRAM维持1216KiB：32槽256KiB/写并行、GU96KiB、24KiB入口保持及其他分区不动，核内两结果槽已经随核价删除不重复扣SRAM。GU峰值76KiB、Wd20KiB顺序复用；未来96→80KiB仅省16KiB/.108mm²，未实施。新覆盖面积33.692mm²（上一12核41.562），完整新TPOT留null。未提交服务器/GPU/EDA任务，无新电路run。

顺带修复PR248审核P2：活跃fastsim只支持原profile带宽的采样数扫描，100/10GB/s现在拒绝，固定带宽参考保持；核数扫描用实际worker，不更改校准profile互相抵消。原封存执行源不改；root旧fastsim为owner SOURCES固定引用而保留，新修复位于本任务checkout及PR。首次namespace导入/漏math两小错误已修，不称有效实验；6/8/12原runner字节及仅CLI扩到5的差异保留。发布以PUBLICATION为准，PR248待审，Projects待维护者同步。

---

## 2026-11-07 Issue225：100MHz共享QK真实bank供数接入

用户授权由宿主完成，不再追加Attention模块交付要求。新增architecture_tlm/qk_supply_100mhz_20261107：现有16B/1RW物理bank、1KiB转置SRAM＋128B转置暂存/组；另加四槽32B粗K操作数FIFO/组并分别计价。四Q广播、四context反馈、粗K64token分块、精K四8x8微块16B整字搬运均展开；SRAM仍1216KiB/304bank，组内固定8KiB划出，不扩容。原100MHz32成果、250MHz6文件SHA不变。

本地12配对（单/八组×三seed×旧宏/新供数）＋反馈8拍/FIFO1槽两敏感性完成，10类检查通过；MAC/ADD/样本/唯一V及外存字节/地址sum/xor守恒，队列排空。八组Attention均值128.43→154.62us，供数增26.19us/层、36层投影+.94284ms。条件覆盖面积41.463→41.562mm²，含新2KiB寄存器代理；供数额外SRAM动态.01416mJ/36层，加捕获及已知背景约.06717mJ已计小计，不是完整新能量。

含先前资源缩减prefix/head增量的整机条件外推约53.95ms含head、46.53ms扣head，不是新原生LPDDR完整运行。外存为136.4606GB/s/30ns解析代理，片上bank实际；反馈L4/II1沿既有宏合同。控制/布线/广播及新寄存器idle未独立标定。首次无前取串行诊断208.28us、仅单操作数198.71us及源码保留，不作推荐调度。无新服务器/GPU/RTL/PT/PPL或台账run，不干预198另一套2KiB暂存native/TT250结果。发布以本任务PUBLICATION为准，PR248保持待审，Projects待维护者同步。

---

## 2026-11-07 Issue225：250MHz在本人宿主下独立建目录，不提供完整TLM

用户明确250MHz结果与100MHz分隔，250尚不完整，可先不给完整模型。已建architecture_tlm/sram1216_20261106/250MHz/：README、模块证据目录MODULE_CATALOG、组装状态ASSEMBLY_STATUS和独立validate_catalog。无运行入口/默认导入，整机时间/能量/功率/面积均null；普通池320/640仅候选，未定核数、SRAM时钟或共享QK调度，不影响100。

TT1.2V25℃250MHz，项目55等效面积由rawx.81一次；功耗/能量不随频率猜。204八模块8/8报告来源已验收，本轮核8归档大小/整包SHA、沿用3119成员SHA记录，包含GF64/完整C20T64/前端/后端/state32/数字CIM/OS/WS；整核与组件不重复计费，向量与DOT64单位分开。T8/T32及GU74/Wd53未做新TT250PPA，不改名套价。

198旧九模块18项17正常退出、FMA64/250超时缺3窗；自动归档也超时，无完整报告包SHA，当前只元数据索引，不作完整系统价格。新PV4先闭100门级X，再TT250；共享QK包装/真实K供数/归约32单价II及其他250接口未绑定。已有数据“未绑定”不表示未仿真。若池320不能借512QK，需重映射；外存LPDDR带宽不乘2.5。

11项目录隔离/PVT/单位/缺项校验通过，100MHz宿主/采样/Attention候选三历史manifest的32成果SHA全部不变。无新任务、EDA/GPU/PPL/RTL/PT，不改198/204源或队列。100MHz优先候选combined32未作已验证默认，原因是PV门级X和QK真实供数尚未闭合，不是算法已否定或要求所有电路都做完。

辅助work/rayggxia/225/tt250_catalog_20261107/build_catalog.py、HANDOFF、ISOLATION_VALIDATION和SOURCE_MANIFEST；同Issue225/PR248/工作目录，根250MHz目录为同字节阅读镜像，发布以PUBLICATION为准，PR待审不合并，Projects待维护者同步。

---

## 2026-11-07 Issue225：Attention资源候选接入审计与面积

用户要求核对新Attention可否接入TLM及面积。已读取198最新resource_compaction/resource_rtl交接，combined32为PV128＋归约32＋普通640池借512做QK，100MHz/1216KiB。宏接口可接，新增attention_candidate_20261107/integrate.py显式适配，并修正继承executed_resources仍报512QK/512PV/128归约的旧资源账本。9项本地检查、原模块10个原生报告SHA复核通过；没有新任务/RTL/PT/PPL或候选完整整机运行，不改正式默认。

按旧已标定组件价，整机覆盖52.621712→41.463021mm²，省11.158691／21.2055%；独立QK省7.835847、PV净省2.432451、归约省.890392。PV16KiB状态保留、2KiB暂存计入，全部1216KiB SRAM保留；模块19.126924含普通池＋672KiB，不误当整个芯片，普通池不重复计价。

PV4新RTL通过但门级首帧X未解决，失败DC0.085667mm²/头未用于正式价；QK共享切片门级过，但真实K重排/供数尚未native集成，新mux/route/PV状态选路门控PPA未知。因此41.46是可用架构候选预算，不是新硬件验收；正式当前参考52.62仍保留。原模块首层至O+5.77%、冷head+4.85%，不能当整token百分比。TT250普通池320不能照搬借512映射。

同时收齐昨日本人38617087完整两项：旧Attention、1216KiB/640下T64/64为51.43301ms含头、7.07502头、44.35799扣头；T8/32为51.40648/7.07546/44.33102。RESULT/SEAL/冻结源核验，8个prefix/full原件逐字节归档project_archives/sampling_latency225_20261106/native。完成态覆盖旧RUNNING及外推；不重跑。新完整T64profile快估T8=51.38117ms，单点差−.02531ms/−.0492%，非通用精度承诺；不含本次新Attention候选。

正式architecture_tlm/attention_candidate_20261107/README_ZH.md及INPUTS/RESULTS；sampling_latency_20261106/COMPLETED_RESULTS_ZH.md/JSON和COMPLETED_CURRENT_PROFILE/CHECK登记完成结果。接续Issue225/PR248、同工作目录；交接work/rayggxia/225/attention_candidate_20261107/HANDOFF.md，源发布以PUBLICATION.json为准，Projects待维护者同步，PR不自动合并。198原件和运行任务只读，不接管PV X/许可证修复。

---

## 2026-11-06 Issue225：T8/T32快速时序工具和1216KiB原生配对

用户要求Wg/Wu8次、非线性三AND直连Wd32次，快速改变T估算时间，并分列含/不含lm_head。已实现architecture_tlm/sampling_latency_20261106/fastsim.py：有限32权重槽、12核、2结果信用/核、2状态端口、K依赖和GU均衡窗口的tile事件模型，原T64阶段校准偏移保留；六组扫描本地约0.7秒，无GPU/原生库依赖。不能按T比例缩整机，当前FFN权重约2.69GB/token，136.46GB/s理想搬运19.71ms，已测FFN约21.8ms，故降T主要减核内工作而非大幅加速。

服务器已恢复，38616054两项完整COMPLETED/0:0与SEAL SHA重新核验。旧1952KiB/1024普通池T64/T64为49.93827ms含头、6.95415ms头、42.98412ms扣头；不是最新1216/640配置。“扣头”保留final norm和已重叠的少量lm_head预取，不等于取消全部头权重的硬件重跑。

当前1216KiB/640新快照4528b0b42a97：T64/64与T8/32两层38617086均完成，2.46395→2.46201ms（−0.0787%），FFN1.25171→1.24790ms；外存257484544B一致，MAC/跨K/Attention守恒，GU R8动作1/8、后级1/2已核。7本地＋7EDA门禁38617085通过，原始两层RESULT/SEAL已逐字节归档project_archives/sampling_latency225_20261106/native/prefix。

新完整38617087_[0-1]已RUNNING、0GPU/各1CPU、最多2并行，预计约2—2.5小时；不重交健康任务，不改冻结源，无自动化。最新实际状态见同任务STATUS/交接，不能凭本备忘录断言以后仍运行。旧1216失败计划未另行重复提交。当前两层外推＋旧head代理粗估前64后64约51.30/44.35ms、前8后32约51.25/44.29ms；不是新整token结果，需完整T64/T8结束后替换profile并验证快估误差。

实际delay按(T+2)×10ns改变GU/Wd帧，其他阶段保持；20依赖只读固定，SHA a633d11f4a52d47611a96cd8016695f47294d154cb900bec2b4edac914d90291。无新PPL/训练/RTL/PT/能量价格，不把T64 PPA按T打折。正式README/REFERENCE_PROFILE/CURRENT_PREFIX_PROFILE/NATIVE_PREFIX_RESULTS与QUICK_SCAN；辅助入口work/rayggxia/225/sampling_latency/HANDOFF.md和ops.py。沿Issue225/PR248，发布回执为准，Projects待维护者同步。

---

## 2026-11-06 Issue225：用户保留1216KiB，更新各模块面积主表

用户明确先保留约1.2MB，即1216KiB/1.1875MiB；不继续压992KiB等候选。当前本地面积参考compact1216，2K/K128/赢家S64、640路普通池、12个C20/T64、96KiB GU保持；旧CLI/冻结源不静默改写。未重试故障EDA，无新作业/PPL/RTL/PT。

正式architecture_tlm/sram1216_20261106/AREA_BREAKDOWN_ZH.md及JSON/CSV，15面积项归6组一次求和：FFN15.949424、共享数字池与归约10.981999、Attention14.782192、SRAM8.181625、DMA入口1.188795、格式向量/数字保持1.537678，合计52.621712mm²。55等效已单次x.81，不再次缩放；FFN随机源/比较器已含C20核价，零额外proxy不表示硬件免费。

SRAM内部按用途512/160/256/128/96/32/32KiB拆分，等价304宏；前端176bank交织共享，按容量摊分面积不意味着另外独占宏；内部表不能再加到总面积第二次。沿上一轮既有逻辑价格，仅更新主表与归属；新增紧凑译码/互连、完整NoC/CTS/PHY/IO/pad等仍缺项，不称最终die面积。

长上下文不使所有SRAM线性增长：FFN/权重tile/norm通常可保持，KV主体片外；若K128→256并整份保留候选V，单组V缓存32→64KiB，当前64KiB/组不能容纳全部原工作区，需要加容量或新流式/缓存调度。未运行长上下文适配，不将条件推断当结果。

生成与核算入口work/rayggxia/225/sram1216/build_area.py、AREA_VALIDATION.json；来源SHA、15项归属无重复、SRAM1216KiB/304宏及子面积守恒已核。沿Issue225/PR248，同工作目录，发布回执AREA_PUBLICATION.json为准；PR待审不合并，Projects待维护者同步。

---

## 2026-11-06 Issue225：1216KiB SRAM本地候选已实现并初步验证

用户要求落实Attention缩容并尝试约1.2MiB；已读取198的SRAM64方案（此前只有文档），在新adapter实际映射全部transfer/直接读/DMA回填；八组各64KiB，640数字池两个80KiB槽，激活区128KiB，GU96/CIM256/norm32/DMA32保持，合计1216KiB=1.1875MiB、304个4KiB/1RW宏（前端176+Attention128）。没有保留旧488个端口。旧198/204/225执行源和在跑任务只读。

8项CPU检查＋三配置完整形状一层机制回放通过。解析外存和合成600拍/查询采样时序，1952/1440/1216KiB为1.14172/1.14457/1.16366ms，+0/.250%/1.922%；关键计算actions和外存128907264B一致，SRAM读词4038373/4038373/4038238，写均8645664。不是原生LPDDR、完整token/PPL或新PPA，不能声称所有SRAM动作不变。

按已有宏价覆盖面积57.573748→52.621712mm²；条件50ms计价片上24.133492mJ/.482670W，含4pJ外存197.297987mJ/3.945960W。存储小37.7%不等于动态能量同比降低。新增译码/互连PPA未标定，完整新组合同样未测TPOT。

EDA首次脚本语法失败后修复，后续SSH执行通道连续超时；只读恢复检查无对应快照/任务，没有成功作业号。用户随后确认服务器故障，要求本地初估；本轮停止EDA重试，不等待远端，不创建自动化。后续原生计划仅待办，恢复先核查PREPARED/回执，不能盲目重交或误报仍在运行。

正式architecture_tlm/sram1216_20261106/README_ZH.md及RESULTS/BUDGET_ESTIMATE/DEPENDENCIES；本地原件project_archives/sram1216_225_20261106/LOCAL_SYNTHETIC_SMOKE.json及只读14文件依赖。交接tmp/norm-stream-issue225-20261106/work/rayggxia/225/sram1216/HANDOFF.md；Issue225/PR248保持原任务，发布以PUBLICATION.json为准。根正式目录同字节阅读镜像。

---

## 2026-11-06 Issue225：按最新交接重计功耗面积

沿PR248/task225，正式architecture_tlm/current_handoff_budget_20261106。实际计入640/8-K/提前补货、norm32KiB及GU96KiB候选/1952KiB/488宏；128个归约器和独立QK/PV/8×128KiB Attention保持。覆盖57.573748mm²；50ms假定窗口片上24.204832mJ/0.484097W，含4pJ外存197.369327mJ/3.947387W。非联合native时延/新PPA/PPL；45/55ms仅敏感性。

6检查与16旧分项重建、12来源SHA通过；普通MAC次数不乘640/1024折扣、ADD63→7按动作、SRAM不按容量折扣动态；RNG已在C20内。未预扣Attention64、共享QK、激活128、CIM24或DOT8。96完整pair与640整token仍待组合验证，新增仲裁/供数/连接PPA缺项保留。未修改198/204源码/任务，旧6/9norm完整封存仅只读核验，3缺项不冒充完成。精确源码/验证/回执见work/rayggxia/225/handoff_budget_20261106；发布以PUBLICATION.json/PR为准。Projects待维护者同步。

---

## Issue225/PR248紧凑预检完成

502bank前缀38615021已COMPLETED/0:0封存，14项EDA检查通过。计算/采样actions及外存字节同旧512bank，时间2.36845→2.38926ms（+0.879%），前缀能量9.75525→9.75733mJ，覆盖面积64.09655→63.82742mm²；不冒充完整token。Attention交接与紧凑源码d10ed86c已公开，11文件逐字回读；PR248待审未合并。旧完整任务不动，后续只读COMPACT_PREFIX_RESULTS和交接。

---

## 2026-11-06 Issue225：Attention缓冲交接与删除40KiB空闲

沿task/225-norm-stream-20261106 / PR248，新Attention任务文件在architecture_tlm/module_handoff/attention_buffer_compaction_20261106/HANDOFF_ZH.md；只交接不接管198，不预扣其512KiB目标。COMPACT_ZH.md说明数字/CIM、激活和152KiB宽状态的分步优化。

compact.py已将40KiB空闲实际删为2008KiB/502bank（不是保留512免费端口）；14项本地及EDA38615020通过，原生两层38615021运行。新9份源identity0578fe2e2b1e冻结，旧norm6源及38614103原样保留；新完整性能未知。只compact_ops status，未封存不称完成；出处/映射/所有物理word无别名与宏面积见COMPACT_VALIDATION/COMPACT_SOURCE_MANIFEST/HANDOFF。实际上传增量以COMPACT_PUBLICATION为准，Projects待维护者同步。

---

## Issue225/PR248实际发布与预检

PR248 ready/open未合并，源d428823e9e18832937a968db236b6ad5a6de15de，16份文件逐内容回读。原生三配置两层预检均完成封存，actions相同，norm额外32256B已计；2.5MiB常驻/流式2.36889ms，2MiB2.36845ms。完整38614103九项待封存，不能报整机完成；只status/collect，冻结六源不改。

---

# 2026-11-06 Issue225：norm逐层双缓冲与2MiB候选

负责人rayggxia；task/225-norm-stream-20261106；base main8cd4fba；独立tmp/norm-stream-issue225-20261106。用户确认采用无损逐层加载，不再全模型gamma常驻。正式architecture_tlm/norm_stream_20261106，默认stream_2m，旧resident_2p5及stream_2p5配对保留；源码d3acb0ee，执行identity dd115edf65dd。383KiB→32KiB，声明2008KiB/2MiB，每token多读392192B；BF16参数/数学不变，非PPL或新电路PPA。

本地8项和EDA38614101八项通过；prefix38614102三配置两层门禁运行，full38614103九项依赖门禁，尚无完整封存结论。512个16B/1RW bank及12核/T64、1024FMA、8Attention组不减。共同显式展开旧宏内QK-headnorm gamma读取，不能声称新参考逐拍等于旧49.563ms。

交接/来源/命令/作业在work/rayggxia/225/norm_stream。恢复只status/collect，不重复submit或改冻结源；原225/236目录和健康任务保留。上传及PR状态以PUBLICATION.json为准；Projects待维护者同步。

---

# Issue95 九项预算整理

2026-11-02，rayggxia；task/95-nineway-power-20261102，main0320f486，工作区tmp/rng-nineway-issue95-20261102。

本地完成27行（九结构×K1/64/128）100MHz功率/J每输出bit条件表，81项算术与确定性重建通过。PR215已核实合并，本次不新增EDA/run，不改已有原件/其他任务。正式结果random_service/digital_pbit/nineway_20261102，中央summaries同字节镜像。共享q8价格仍代理，不称独立实测。精确版本/发布及下一步见work/rayggxia/95/nineway/HANDOFF.md、PUBLICATION.json；Projects待同步。

---

## 2026-11-02 Issue230：55 nm/100 MHz纯数字基线仿真清单

负责人rayggxia；分支task/230-digital-baseline-plan，目标main。独立稀疏目录tmp/digital-baseline-plan-issue230-20261102。正式文档digital_circuit_simulation_registry/41_纯数字基线仿真清单_55nm_100MHz.md；根a_P_BIT同名阅读副本按SHA核对。

本轮仅文档：盘点13份已读台账record，区分复用、补测、宏估计和TLM重放；新增建议包括FMA反馈/供数切片、完整数字SwiGLU、在线Softmax、归一化/转换及局部DMA/SRAM外围。既有A9W8/端点、FMA时序限制、P8与完整Softmax差别均保留；不把筛选后准确PV当完整数字Attention。

本地引用存在/JSON解析、UTF-8 LF及阅读镜像字节检查通过，SOURCE_INDEX.json绑定文档及13份record的SHA。没有新RTL/EDA/GPU/Slurm/PPA/PPL，未修改#198/#204/#210/#227代码和冻结任务。尚未执行清单中的补测，未知成本不填0。

发布前已读远端main@7d42c7d30fa9c729c899ba7f815332dd6ed5671a及规则。Git网络fetch失败，局部准备基于已存787489192ebfcdb61ad72edde406818f450aa3dc；通过API只把本任务4份文档增量接到核验后的main，不推送本地历史。主体已发布提交6d137fdbcb2d79db416e084558ccc24dd0c59feb，PR #231 ready/open、待审未合并；四个PR文件逐项blob SHA及零删除核对通过。具体本地回执见work/rayggxia/230/PUBLICATION.json；待审不等于合并。Projects看板未同步，待有接口的维护者处理。

下一步先决定并实现最小代表模块，再按功能→STA→三seed PT逐项推进；不要把本任务当作自动启动许可EDA的指令。

---

## 2026-10-29 Issue204：用户要求继续SRAM存内比较主架构

双随机结构继续SRAM驻留、本地SNG并行比较，阵列输出随机权重bit；不默认搬整组权重到DFF，不默认每采样走普通窄口完整读。两颗全局LFSR32（输入一颗/权重一颗）、T32/8×4与原共享尺度保持；P8输入/P7权重各需5位抖动。ICG DFF及普通宏预读保持仅作对照。已更新12方案页，新增13_SRAM存内比较估算口径与证据.md并同字节同步根阅读镜像。

历史框架可以延续：真实宏库/尺寸/面积/保持与装载＋SRAM邻近标准单元SNG/驱动表征＋存储节点带载接口增量。旧四32×144宏2.25KiB、576bit预读Q保持不是完整64×64存内比较；S0–S5保持/读写有原件但CE关闭动态缺表/hold/XZ边界限制保留。Issue146实际N64/M1/seed17/T32数字前端SS100MHz115.3µW、340ns/39.202pJ，含一颗LFSR/输入比较/固定W门控，不含物理SRAM，功耗表告警保留；不可直接当新W-SNG价格。真实定制存储位/位线比较尚未表征；新最小探针应是7幅值存储位+W7比较/必要隔离，旧模板只有bitcell/AND/BUF。不能将缺接口能量填0，或每拍重复收费全普通读；按真实本地模式收费。普通宏外围也不能任意扣除成裸cell成本。

只读核实Issue146与本机原件；旧source508bdaa4当前workspace GitHub ref404，未伪造远端可见、不重跑/接管其任务。源码/证据阅读SHA见SRAM_CIM_VALIDATION.json。rayggxia继续Issue204/PR209/task/204-bf16-baseline，源基线06b14a96fef58533c5af85851a2a6eae17d07aee；本轮仅合同/历史证据整理，无新RTL/EDA/SPICE/PPL，不新增run，完整根union保留。实际发布见SRAM_CIM_PUBLICATION.json，PR待审未合并、Projects待维护者同步。

## 2026-10-29 Issue204：用户指定输入/权重各一颗全局LFSR32

用户进一步明确：全部输入共用一颗LFSR32，全部权重共用另一颗LFSR32，分层计数器独立生成层号。主候选据此固定，连接独立只作数学精度对照，不按每连接完整PRNG计成本。P8输入/P7幅值权重且8×4时，仅各需5位格内抖动；两颗32位状态共64位、单5位格计数器合69位（不含概率/权重保持、累计和广播）。T64/128/256分别5+4、4+4、4+3位抖动。只广播所需低位与层号，不把32位全部拉给比较器；K64/M输出仍有64个X-SNG及64M个W-SNG。

先单乘法T32/64/128/256，再64对乘累加与M输出复用；当前只是用户方案记录，未启动实现/EDA/模型。两轴不同非零seed、实际抽头/反馈与短窗联合/时间相关性、帧间连续推进另验；普通LFSR5缺零/31周期不能直接替代32值均匀抖动。全局共享改变点积协方差，不能继承连接独立PPL；先精确归约、OR4单列，原尺度不改。已更新功耗面积目录12方案页并逐字同步根镜像，不新增run、旧台账不改。rayggxia，Issue204/PR209、task/204-bf16-baseline，源基线f5d22ac4470c9a423bbba238994957f1a4491cd0；本补充发布见TWO_LFSR_PUBLICATION.json，PR待审未合并、Projects待维护者同步。

## 2026-10-29 Issue204：双随机双轴分层架构分析（未启动EDA）

用户要求保持输入及权重各自共享尺度，思考两侧随机比特流、双分层（非DS-CIM互斥映射）及待评估模块。已只读核实PR207@05d7d986的尺度合同/dual_gu数值参考：x每64共享原四档PoT、W每64×64共享PoT LSB，码[-127,127]不变、pW=abs(q)/128；T32沿已有8×4联合格，非32²拍。原数值参考W按连接独立，硬件分组/列共享改变协方差，不能继承PPL。未修改Issue201/206源码、模型/尺度默认或运行其他任务。

方案入口digital_circuit_simulation_registry/12_双随机分层矩阵架构评估计划.md，论文与项目Git blob在references/dual_stochastic_20261029/SOURCES.json，根镜像两文件同字节。主候选一套signed popcount64+13位累计，OR4近似分支popdiff16+11位累计，均为每输出一个状态而非每权重位平面一套；9/10位饱和另验。双分层不会消除OR碰撞：4个相同pX=pW=.5共用二维点时，精确和1、OR4仅.25，手算/32格枚举一致，非新电路仿真。两侧SNG可拆高层判断/低5位边界比较；收益待测。必须计2D调度/真实抖动分发、X8/W7比较、驻留SRAM/ICG DFF、符号AND、归约/累计、组间PoT对齐舍入及M扩展广播，不能把旧69pJ除6当新功耗。

DS-CIM、DATE2017 Sobol、ICCAD2018 LD、uGEMM及Frontiers2023一手正文已读；原生方案与论文映射/条件推进不同。当前仅分析建议，不预设T32精度/能效，不新增run、无新RTL/PPA/模型/PPL，全部旧record字节不改。建议先同尺度/同事件数数值与共享拓扑消融、再功能和同PVT集成PPA；未自动启动这些后续实验。rayggxia，继续Issue204/PR209/task/204-bf16-baseline、复用原checkout；文稿科学源69f1503894becdddbb1440bd2d24ed2d43b237f5已推送PR209，10文件tree与3关键内容/blob读回一致；回执见DUAL_PLAN_PUBLICATION.json；PR待审未合并，Projects沿既有限制待维护者同步。

## 2026-10-29 Issue204：功耗面积文件夹补齐模块长期索引

用户要求把此前模块的功耗、面积、时钟及具体文件地址统一整理，避免遗忘。已在digital_circuit_simulation_registry新增11_矩阵与算术模块功耗面积时钟索引.md及summaries/20261029_matrix204/MODULE_INDEX.json、MODULE_MODES.csv，覆盖Issue204六批66配置/209运行模式：四档首轮8、单尺度16、参数模块33、BF16五核、四lane INT8两核、64路INT8两核。固定读取提交4175c5565fcd714b0648d97a15c1697b5fbcee05；6源汇总/源码逐字及66原始报告归档SHA核验，保留每项活动/idle、raw与×.81等效面积、100MHz/10ns、操作定义/平均周期/原生延迟和II（未知留空）、STA负值/告警、源码Git地址与本机绝对原件路径。旧04页保留原始表值并加新入口和面积口径说明，README补导航。

同3份新文件已逐字同步根阅读镜像；各自README/04原有内容保留，旧record字节不改、不用67条任务子集覆盖89条完整根union。无新EDA/模型/PPL、不新增run。复现build_power_index.py，核验POWER_INDEX_VALIDATION.json；未来新增模块需同时更新中央run与阅读索引。rayggxia，继续Issue204/PR209、task/204-bf16-baseline，复用tmp/matrix-t32-issue204-20261028；本补充科学源4207651c9cfd2cbabfc4c3572a83e21e07d25998已推送PR209，13文件tree及5关键内容/blob读回一致；回执见POWER_INDEX_PUBLICATION.json；PR待审未合并，Projects待维护者同步。

## 2026-10-29 Issue204：按用户要求完成同64路并行INT8对照

rayggxia，task/204-bf16-baseline / PR209（base main），复用tmp/matrix-t32-issue204-20261028；执行base158e489816bde1547d07cd3f9e377b809055f63f+明确未提交冻结快照。用户澄清重点为整体面积/功耗、要求同SC的64路物理输入并行度，主比较已改为64个动态signed8×8并行乘法+六级平衡树+32/22位结果寄存，不以四路复用替代。旧四路/BF16/SC原件完整保留。正式入口architecture_tlm/int8_parallel64_20261028/results/REPORT_ZH.md与FINAL_SUMMARY.json。

SS1.08V125℃100MHz，面积raw×.81一次。64路32位结果：raw34842.96µm²、等效0.028222798mm²；满速2.126333mW/21.2633pJ每完整N64点积，原生1拍结果、II1=10ns；每35拍接受一帧且100MHz时钟自由运行时0.1148mW/40.1800pJ。22位结果raw34756.92µm²、等效0.028153105mm²，满速2.118333mW/21.1833pJ，同35拍0.108933mW/38.1267pJ。固定N64无bias的22位精确，非任意K累加器，外部均32位；综合高符号位复制/合并，缩位面积差约0.247%。

同原SC54操作数匹配：从原ZIP恢复X/W并逐项SHA核验，每帧W行f%8、absW上限127、X原signed8。SC54原0.0055240704mm²、0.198466667mW、69.4633pJ/350ns。相同64并行度SC面积小5.109倍、各自满速功率低10.714倍，但数字原生吞吐高35倍、满速能量低3.267倍；同350ns完成工作率下SC能量/功率为数字1.729倍。可以支持同64路SC面积优势，不能宣称目前SC相同工作率能耗优势。SC OR4/T32/去LSB近似、数字精确，合成输入匹配不等于模型质量匹配；无新模型/PPL。

最终两top/三seed各164事务，984 RTL及984映射门级输出逐项oracle/四态valid通过，24PT窗口mapped端口/leaf活动100%。v1另24窗口已算出但hold−.061165ns，原件保留；v2核验源/配置/库绑定/原网表后，DC原生hold-only实际插buffer，每核面积仅+raw1.44µm²（等效1.1664）。不重编译算术/retime、不放宽约束；最终setup/hold：32位1.429668/.032151ns，22位1.881098/.027525ns，parser flags空。数据delay1/.02ns、slew.05、load20fF、uncertainty.5/.05，reset4.5..5.5ns释放，无false/multicycle。无CTS/SDF/SPEF/完整毛刺，不是物理签核。

两执行ZIP/8报告/24传输文件/全部成员SHA已核验；准确作业与命令RUN_LEDGER，v2manifest f39df885a073d53ac9c5a7584d78e97906122722b29664ba0155f8e6cd434c8d，原件project_archives/matrix204_parallel64_20261029，私有配置/SDC/库模型指纹单列EXECUTION_FINGERPRINTS。Slurm38447564/38447584/38447776/38447785及两只读DC命令帮助作业均COMPLETED/0:0，不重交。权重/概率存储、SRAM/RNG/比较器/格式/真实广播/ICG仍在核边界外，paced不称最佳数字门控能量。

中央run matrix-int8-par64-204-20261029，任务分支67、完整本地根镜像89，分别保留原66/88个record字节并check/render，不以小子集覆盖全union。新run原件/成员全可访问；历史不可达项见LOCAL_REGISTRY_CHECK.json。科学源48be94077e14a668be0633d44a8dbc7694e505e3已推送PR209，47文件tree及8关键内容/blob远端回读一致；实际回执见同目录PUBLICATION.json；PR待审未合并，Issue保持open，Projects连接器不支持写待维护者同步。

## 2026-10-28 Issue204：经典INT8本工艺结果及SC面积质疑复核

rayggxia，task/204-bf16-baseline / PR209接续，基线6435de8854d8ddb93375e03085ed1eea9c3f9002，复用tmp/matrix-t32-issue204-20261028。用户明确要求按成熟参考计算INT8，随后质疑“无论怎样SC面积肯定更小”；已核查源/映射库存，不根据期待反改结果。入口architecture_tlm/int8_classic_ppa_20261028/results/REPORT_ZH.md、AREA_EXPLANATION_ZH.md及完整SUMMARY。

经典四lane signed8×8→16位乘积寄存→17/18位平衡归约→输出驻留累加；INT32主参考和固定N64无bias精确INT22。一帧64项点积一个输出，不是64×64全矩阵。三seed216完整帧+6 reset中断功能与对应门级通过，18PT窗口全映射leaf/端口活动核验；matched48帧来自BF16原INT8派生数据，整数结果/128与BF16/FP32逐位同值。无新模型/PPL。

SS1.08V125℃100MHz：INT32 raw3825.36µm²、等效0.003098542mm²、0.2151mW、40.869pJ/帧；INT22 raw3621.96µm²、等效0.002933788mm²、0.207mW、39.330pJ。正常18拍valid/19拍帧间隔=180/190ns；位宽收缩省5.32%面积/3.77%能量，不截断有效结果。setup/hold分别3.082494/.082897ns与3.299786/.082897ns，parser未列警告。前布局无CTS/SDF/SPEF，不是物理签核。

面积复核：SC54寄存器77个/449.064µm²，组合1860个/5075.006µm²，总5524.070µm²；INT32寄存器109个/785.279µm²，组合793个/2313.263µm²，总3098.542µm²，全部已乘.81一次。SC寄存器更小但六平面并行符号/OR/计数/累加/恢复组合网络更大；整数只4个乘法器复用16拍。两核都未放整组权重/概率存储，未发现因漏权重DFF或双乘.81导致排序。旧64路全并行INT8约0.04621mm²确实比SC大，但20ns帧间隔不同；N64问题长度不等于物理并行度，不能宣布SC所有实现必然更小，也不把当前SC54称面积下界。

当前粗比SC54相对四路INT32面积1.78倍、能量1.70倍、帧间隔1.84倍，不能支持相对INT8已有巨大优势。对同批数值BF16556.2pJ参考，INT32能量低13.61倍、面积低14.50倍。SC输入/近似精度不同；SRAM、供数、随机源、格式与广播/时钟边界未闭合，不宣布整片胜负。未来可优化SC符号/计数路径，但需独立质量与PPA，不因用户直觉覆盖负结果。

v1/v2门级X失败保留，v2去重定时仍失败，故不能归因于重定时本身。波形定位同步reset时控制计数LSB停留X；v3真实异步控制reset、同步sum、valid保护无reset产品寄存，v4相同电路强化四态ready/valid拒收后完成门级/PPA。数据delay1/.02ns、slew.05、load20fF、uncertainty.5/.05；reset下降沿附近4.5..5.5ns释放与BF16补充契约相同，未加false/multicycle、未force初值、未改库模型。最终set_fix_hold core后compile_ultra，不重定时。

4执行ZIP/14报告/42传输文件和成员SHA核验，配置/SDC/库模型指纹单列EXECUTION_FINGERPRINTS；准确作业见RUN_LEDGER。v4 manifest6523fbde32b9d8cad460f09f1ccf9892466788071fc20aa37a931d86d507255f。实际执行为base6435de88+未提交冻结快照，不伪造执行提交。原件project_archives/matrix204_int8_classic_ppa_20261028，本轮无运行作业；私有控制器不发布。

中央run matrix-int8-classic-204-20261028，任务/完整根镜像各自增量union check/render，准确数见REGISTRY_CHECK。旧record字节保留，不用任务子集覆盖全镜像；本run所有产物可访问，旧94路径仍不可访问。科学源fe060b5a26bfa5281b8a61b353cb8b5bd33f47d9已推送PR209，49文件tree及8关键内容/blob远端回读一致；准确回执见同目录PUBLICATION.json；待审未合并、Issue保持open，Projects工具不支持写待维护者同步。

## 2026-10-28 Issue204：成熟BF16本工艺N64 PPA完成，INT8经典划分已核对

rayggxia，task/204-bf16-baseline / PR209接续，源起点99bf019c。用户明确要求按经典流水划分做本工艺PPA，再查INT8；这是新授权，已实际运行EDA，不沿用上轮“无EDA”的历史结论。复用tmp/matrix-t32-issue204-20261028，未接管Issue107。结果入口architecture_tlm/bf16_ppa_20261028/results/REPORT_ZH.md、FINAL_SUMMARY.json及INT8_CLASSIC_ZH.md。

CVFPU77811635/common_cells9afda9ab精确上游，BF16×BF16/FP32乘加及独立乘/加；四lane非融合DOT4树+四FP32交错上下文，N64正常29拍valid、帧间隔30拍=300ns。五top45个三seed窗口、27696标量+108整帧功能比较及对应门级回放已完成；48个INT8派生帧另用Fraction精确点积核验。合成数据，无模型/PPL；不称单轮舍入fusedDOT4或最佳生产矩阵引擎。

N64原始面积55454.76µm²，raw×0.81等效0.044918mm²，normal平均1.923333mW、577.000pJ/完整64项点积；INT8派生输入556.200pJ。相对SC54(0.005524mm²/69.4633pJ/350ns)约8.13倍面积、8.31倍能量，SC帧间隔长16.67%。这是异精度/不同合成激励的计算核对照，不能宣称整片或同质量优势；既有INT822.19/38.80pJ仍比SC省能。

原共享reset0.02..1ns约束导致async removal负余量。相同SHA网表补充STA明示下降沿附近4.5..5.5ns释放，数据约束不变、无false/multicycle，N64setup/hold 0.000027/0.143288ns；四独立标量en→valid仍−0.061165ns hold，未修复。功耗表范围、高扇出和极小setup余量保留；无CTS/SDF/SPEF或复位分配实装，不称物理签核。

v1..v7负结果/源包/原始报告保留，原字节、远端SHA和全部报告成员核验。v6标量完整，v6 N64仅TB time变量裁剪失败；v7只修波形裁剪并核验全部RTL/bench/fixture/库绑定/约束后复用相同网表，未重综合。补充STA独立冻结。执行是base99bf019c+uncommitted快照，后续源码提交需按ZIP逐字绑定，不伪造执行提交。准确批次见work/rayggxia/204/bf16_ppa/RUN_LEDGER.json；本轮作业已结束，不重交。

中央run matrix-bf16-204-20261028；分支与根镜像分别向各自最新record集合增量登记，旧record字节均保留，绝不用分支子集覆盖完整镜像。准确数量、check/render及原件校验见REGISTRY_CHECK.json。科学源5d21923c7dc7268e2cb19cf393bd858dc3dfb52b已推送PR209，70文件tree与8关键文件内容/blob回读一致；实际回执见同目录PUBLICATION.json。PR待审未合并、Issue不关闭，Projects沿既有限制待维护者同步。

INT8经典实现采用signed8×8→16位积，output-stationary INT32反馈累加，或DOT4/8平衡树后累加；固定N64无bias最坏范围可用22位精确，但可复用长K/带bias经典基线应保留32位，再把22位列独立消融。Gemmini/NVDLA一手源码/文档已核查；推荐100MHz先用乘法级+累加级，是否树内增级交STA决定，无新INT8 PPA冒称。

## 2026-10-28 Issue204：已找到完整28nm BF16数字阵列功耗证据

rayggxia，task/204-bf16-baseline / PR209接续，源起点d6aa128997072acd837508c7703844bf950603ec。用户要求确认是否没有28/55nm BF16数字矩阵依据、缺乏时再自建仿真。二轮已找到MFSA完整正文和FlexBlock作者PDF，纠正首轮检索不足；两原PDF及表II/V原图已下载、SHA绑定、渲染核对。当前入口architecture_tlm/bf16_baseline_20261028/README_ZH.md、LITERATURE_RECHECK_ZH.md及literature_recheck.py。

MFSA2026-10-14预印本：28nm SS0.72V/125℃/1GHz，16×16全格式数字阵列，BF16输入/FP32累加；后布线RC+LLM门级轨迹稳态估算1.85W/1.024TOPS，排除reset/预装/排空。两op/MAC由256PE×两项×1GHz核验，得3.61328pJ/MAC、231.25pJ/64MAC；对SC54核69.4633pJ为3.329倍，仅异工艺/异精度/异边界归一，非N64冷启动延迟或整片节能。原73pJ摘要换算保留低完整度版本，不作为唯一参考。

FlexBlock作者文件头为2203.06673v1：65nm BF16 SA128×128、333MHz、9.84W、1.77TFLOPS；P/T约711.59pJ/64MAC，但吞吐只占乘法器理论峰值16.22%，属含利用率/周期模型的负载归一，不能据此宣布10倍优势；SRAM另CACTI。外部65nm面积不套本项目0.81。55nm严格同PVT/数据/接口仍未找到已核验匹配项，不断言不存在。

有了可用28nm参考，用户“确认没有才自建”的条件未成立，本轮未启动新RTL/EDA/Slurm/GPU/PPL，中央台账84条不变。后续本工艺表征仍是独立工作，不冒称已测。实际追加提交/回读见work/rayggxia/204/bf16_baseline/LITERATURE_PUBLICATION.json；PR209待审不合并，Projects沿既有限制。

## 2026-10-28 Issue204：BF16数字基线调研与可复算预算
发布切换：原PR205已于2026-10-28T10:51:05Z合并；本BF16补充改用task/204-bf16-baseline，基于main@7874891，准确新PR查PUBLICATION.json。原成果不重跑。

rayggxia，同task/204-matrix-t32 / PR205，复用tmp/matrix-t32-issue204-20261028；本轮读取既有证据及一手论文，无新RTL/EDA/Slurm/GPU/PPL，中央台账84条不变。结果architecture_tlm/bf16_baseline_20261028/REPORT_ZH.md及ESTIMATE.json；estimate.py核验旧SS/TT两份summary SHA、三seed单位和负时序，绑定旧RTL，重算预算。

主比较合同BF16×BF16、FP32累加。28nm Li等TCAS-II论文作者机构摘要可核实1761.41GFLOPS/W；条件按2 FLOPs/MAC为1.13545pJ/MAC、64项72.6691pJ，非55nm已测事务，全文累加/舍入/FLOP计数/面积/N64延迟未核验，不按工艺或0.81换能量。与本SC54计算核69.4633pJ接近，不能据此宣称巨大节能。SC需数字>1.08536/5.42682/10.85365pJ/MAC才分别持平/5倍/10倍，均未计两侧缺失前后端成本。

旧本工艺BF16标量KIND2在SS100MHz setup−26.219376ns、TT−10.537953ns；原731输入/5变长帧不是N64。其通用转换和26次依赖规格化循环值得优化，但未做新网表关键路径归因，不能用旧失败实现代表成熟基线。建议补专用乘法、树LZC FP32加法、融合MAC、共享处理DOT2/4/8与真实N64反馈/归约封装，验证35拍/350ns附近预算；两个算术lane不自动保证32拍。旧原件保留，不接管Issue107；BF16与SC W8/T32/OR4精度不同，匹配量化数字控制仍需保留。

研究稿/脚本本地完成；实际推送状态查work/rayggxia/204/bf16_baseline/PUBLICATION.json和PR205，不宣称新BF16 PPA已完成。Projects沿既有限制待有权限维护者同步。

# Issue204：参数化模块能耗完整交接（2026-10-28）

rayggxia；task/204-matrix-t32，同PR205，base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166。执行基线9f762ced3d25b47bf3963fbf38ff8d321850854b；复用tmp/matrix-t32-issue204-20261028。新目录architecture_tlm/module_energy_20261028，不改旧冻结PPA或模型/整机默认。

用户授权测试不同输入/输出精度popcount和不同位宽移位相加，补时间累计器与组合验证估算边界。33个固定top全部VCS功能PASS，99次RTL回放/162396逐周期比较；另完成对应门级回放和396个PT窗口（3seed×sparse/dense/replay/idle）。全部所报setup/hold非负，最小2.643270/0.007787ns，功耗表范围警告保留；无CTS/SDF/SPEF。

关键结果：pop8/16/32/64 full输出dense单次0.05251/0.09941/0.19720/0.39630pJ；pop64少一个输出LSB面积只降约0.54%、dense能量约1.20%。9位饱和累计4.8554pJ/33拍（清零+32次）；六平面9位固定恢复1.3190pJ/35拍驻留一次。77/54/50状态位组合分别84.6883/69.4633/67.9817pJ/35拍，55nm等效面积6647.90/5524.07/5447.09µm²；54→50只省2.13%能量，48点积相对OR基线额外NRMSE0.969%→1.538%，非模型质量。

未经校准的独立模块和对bank高估约23%、对单平面约26%–27%；统一独立端口20fF与内部连接负载不同，且有相关性/综合/控制差异。用bank54校准后预测bank50，三seed最大绝对误差0.637%，仅是N64/同输入的位宽配置留出验证，不能宣称跨规模/全芯片普适误差。popcount+恢复树两项不足；必须补mask/OR、累计器、时钟/控制、调用次数与组合校准。共享输入计数属于随机输入量化+数字后端的独立对照，不能冒充本OR4路线收益；匹配确定量化数字参考仍待独立开展。

V1 manifest f454a321，349归档成员：旧Python不支持Path.write_text(newline=...)，38441318共33任务在EDA前失败，全部日志保留。V2仅修复driver，manifest cb9fb058b35c723970752bde9fd4e6ee4496808b2a380ad626e899c68ef5b8da，350成员。成功Slurm38441385功能、38442559四类pilot、38442655其余29类（全量4并发）；无遗留任务，勿重交已完成33/396。Windows Icarus DLL错误623导致本地功能工具不可用，pyslang0错225警告，实际功能门禁来自服务器VCS。

67报告归档、2源包原字节、远端/本地大小SHA和全部成员SHA已核验，stable project_archives/matrix204_module_energy_20261028。报告/完整JSON：architecture_tlm/module_energy_20261028/results；执行索引EXECUTION_INDEX.json；传输TRANSFER_VERIFICATION.json；中央新run matrix-modules-204-20261028，84条union check/render、83旧record原字节保留。源码和结果已推送，科学源080729c314e2e0e62efada3e32d4c27c7eac4bb5，68文件完整tree及10关键回读核验，实际回执PUBLICATION.json；PR205待审未合并，Projects既有权限限制待维护者同步。

边界：组合top没有人为I/O寄存器；顺序top含真实计数/控制/结果寄存器，CE非ICG。bank为预解码7幅值位W和乘积符号，abs(W)显式限127；SRAM/概率保持、RNG/比较器、编码/符号预处理、物理广播、最终格式恢复在外。pop缩输出位是丢LSB、单位2^DROP；固定移位与可变对齐分开。非16 pop的replay为IIDp=.35，align replay为随机字，其余由旧M8合成回放派生，均不是模型数据。原PT samples字段0为占位元数据错误，派生表按stim en补32样本/帧，原始字节不改。

后续：先用这组数据估相同接口/频率/负载附近的算术配置，扩大输入规模时补signed-popcount/增量宽度（当前累计器D6只对应OR后16路），并做新组合校准；新存储/随机前端/真实ICG/物理连线独立补齐。报告不按状态位比例推功耗，不把纯算术表当整机PPA，无新PPL/GPU。

---

# Issue204：计数器缩位分析（2026-10-28）

负责人rayggxia，沿用task/204-matrix-t32和PR205，base main@d83eeb1f。分析基线a288901fa783277a134bf7052e49d4e09437308f；既有EDA科学源5dcef4fd99200418f804cbd51f3bf325d1cbea60。独立目录architecture_tlm/matrix_counter_precision_20261028，不修改单尺度或四档冻结执行输入。

用户要求统计32拍各权重位平面累计，研究饱和/截断和低位舍弃，查论文是否必须全按最大值位宽。本轮只做冻结合成数据的数值回放与一手论文核查，不新跑模型、RTL/DC/PT或改变台账83个硬件run。BF16复跑/模型语料字段不适用：未做模型推理/PPL比较；Issue206只读权重量化合同和已封存源码成员SHA，不继承其质量或PPA。

已完成：功耗432输出、功能432输出全部独立重构等于原OR oracle，60个原始输入SHA核验；主M8统计384输出、24条驻留W行，各32拍。B0–B6平均绝对累计53–58、99分位166–220；B7平均1.36、最大32。9位饱和额外NRMSE0.242%；B0–B6用9位、B7用7位为70位状态；删除B0后61位、额外NRMSE1.063%。均以原OR输出RMS归一，不是模型准确率。全8位饱和10.681%、回绕74.642%，负面结果与极值功能退化均保留。64位混合校准例在seed1009留出误差1.072%，尚非模型候选验收。

理论修正：严格signed [-512,512]需11位，但10位只在最后一拍+512缺1；每平面误差≤1、8平面加权原始误差≤255。固定权重支持Gp个OR4组时，精确计数范围±32Gp，可依位平面进一步收紧。逐拍饱和不等于帧末饱和；截计数LSB会丢失逐拍小增量，相关断言已通过。

论文：REX-SC §II-C明确6位饱和对照；SC-DCNN §4.1/Fig7近似并行计数（非直接缩时间计数）；DS-CIM §III-D四拍latch缓存后更新宽累加器。原文链接和适用范围在SOURCES.json/REPORT_ZH.md，不把论文PPA移植成我方收益。Issue206冻结aa43d00d的PoT量化clamp(-127,127)，7个幅值平面；仅在采用这一接口后B7可无损删，不改旧完整INT8边界。

成果REPORT_ZH.md、RESULTS.json、MANIFEST.json、WEIGHT_CONTRACT_REFERENCE.json；复现命令python architecture_tlm/matrix_counter_precision_20261028/analyze.py、report.py。分析已推送，科学源904068b9e70bab558f93c93ff2c230216164cf51；13文件完整tree与6关键回读核验，PR205待审未合并；回执PUBLICATION.json。无新服务器作业；Projects既有权限限制待同步。

后续建议：11位精确对照，10位保守端点饱和，9位/低位删除候选；先补真实权重/激活分布和独立模型质量，再按同条件RTL/DC/PT测饱和与门控成本，不按状态位数直接推功耗。不要重跑已完成96窗口或启动昂贵模型任务。

---

# Issue204 单尺度INT8完成回执（2026-10-28）

发布确认：单尺度科学源5dcef4fd99200418f804cbd51f3bf325d1cbea60已推送PR205，217文件完整tree与8关键逐字/blob回读通过；Issue204正文已同步，PR ready/open未合并，本任务无遗留作业。

负责人rayggxia，task/204-matrix-t32，PR205 open/ready/unmerged，base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166，科学输入基线cc04dee9890ea6dcfbeee872b0cab914d3b1c2c6。本地目录tmp/matrix-t32-issue204-20261028。沿用原Issue/PR，不改旧四档冻结输入、其他任务或整机/模型默认。

用户决定：64路共用一个尺度、真正signed INT8[-128,127]、N64/T32；每幅值位平面和符号先OR4，64→16个事件，再做精确并行计数。实现3版：V1直接实现；V2把每组正负各6位改为一个signed7时间计数；V3使用专用无符号popcount并隔离末端恢复输入，保留signed7组计数。mode3每拍popcount16再时间累计；mode6每组独立累计后求和，二者同事件OR oracle全等。SC内部20位，数字22位，输出符号扩展32位。

全部完成：V1 672帧、V2 96帧、V3 288帧，共1056帧功能PASS；16个综合变体、96个active/idle PT窗口，SS1.08V125C100MHz。3原始执行包和22报告归档远端/本地SHA/大小及逐成员校验；Slurm全部COMPLETED/0:0，本任务无遗留作业。执行索引EXECUTION_INDEX.json，结果architecture_tlm/matrix_single_scale_20261028/results/FINAL_SUMMARY.json和REPORT_ZH.md；源包/报告在project_archives/matrix204_single_scale_20261028。不得重复昂贵测量或改写冻结输入。

M1：精确树179.906pJ、OR4-popcount16优化版101.932pJ（能量-43.34%、面积-16.51%），16路signed7独立时间累计优化版348.483pJ；数字位串行38.797pJ。M8优化OR4 790.767pJ/帧、数字位串行262.133pJ/帧，每帧8点积。还不能证明SC能效胜数字。共同尺度省去bin选择/移位，但新旧码域、刺激及位宽也改变，不能作纯尺度消融归因。

主PPA为16帧驻留权重、uniform signed INT8输入、公共R8，三seed均值；SC原始期望=数字点积/4。OR损失另报，时间计数硬件改动不改变OR结果；真实模型单尺度质量未验。面积raw×0.81保留双列，不缩放功耗/时间。外部权重存储/保持读口、RNG/比较器、输入量化/尺度选择、最终浮点恢复、物理广播线及CTS/SDF/SPEF在外，CE未冒称ICG。全部时序与功耗警告保留。

中央新run matrix-single-scale-204-20261028，增量union check/render并保留其他record；结果见REGISTRY_CHECK.json。源码/结果已推送，科学源5dcef4fd99200418f804cbd51f3bf325d1cbea60；发布回执见PUBLICATION.json和最新PR205。Projects既有权限限制仍待维护者同步。下一步审阅计数实现、hold/功耗表告警；真实ICG、SRAM驻留端口及真实后训练模型同质量验证独立开展，不自动启动昂贵模型实验。

---

# Issue204：T32矩阵改进验证

更新时间2026-10-28；负责人rayggxia。分支task/204-matrix-t32，PR base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166；独立目录C:/Users/86134/Documents/a_P_BIT/tmp/matrix-t32-issue204-20261028。未修改Issue193/186源码或其执行快照。

本地首轮完成：六算法×M1/M8×三seed×15帧，v1/v2各540帧VCS功能通过；8个固定top完成综合、门级及48个SS1.08V125C100MHz PT窗口。恢复时队列已空，不重交EDA。27原始报告归档远端/本地SHA/大小与逐成员SHA均核验；9个执行包原字节保存。报告architecture_tlm/matrix_validation_20261028/results/REPORT_ZH.md及FINAL_SUMMARY.json，精确执行/终态见work/rayggxia/204/EXECUTION_INDEX.json。已推送PR205（ready/open、待审未合并），科学源f19b603578ba215433ae68809c7eed3f30c7bf55；144文件完整tree与本地一致、8关键文件逐字/blob回读通过，回执work/rayggxia/204/PUBLICATION.json与REMOTE_VERIFICATION.json。

M8共享输入计数相对S0：1331.137→479.067pJ/帧（−64.01%），174255.20→168423.79µm²（−3.35%），37→40周期（+8.11%）。M1位平面省能16.88%、面积多37.80%；M1先计数反而多耗能18.40%。普通OR4共享源同号同位权例低估75%。D1确定位串行34.467pJ/帧、11周期、22054.00µm²，低于M1 S0的165.994pJ/帧；尚未证明随机整体胜数字，M8数字同规模尚待扩展。

面积均已按用户要求raw×0.81并保留原始列。S0两尺寸hold−0.041792ns；S2 M8 setup仅0.000099ns，功耗表范围等警告保留。前布局，无CTS/SDF/SPEF、真实模型质量、存储/RNG/比较器/编码/最终浮点尺度及实际广播线成本。D0是未优化q9参考，不称成熟最佳INT8。SRAM/门控权重与内部位宽收紧属于后续，不伪称本轮全链路完成。

中央台账新增matrix-t32-204-20261028，82记录联合check/render、81旧record逐字保留；main缺全台账，本PR只交付增量record及校验回执，不复制别人记录。失败波形/别名/调试可见性版本保留；v3旧数字后处理实际已跑1分34秒后取消并由v9替代，如实记录。Projects既有权限限制待同步。下一步：审阅本轮PR，修hold/功耗表范围，M8数字控制、SC位宽/真实ICG及驻留权重端口验证；不自动启动新模型或昂贵作业。


公开回执：源码提交aebf0e4c86f348092886cf5a3c26bd6f79903ff2的13文件已逐内容回读一致，见PUBLICATION.json；PR248待审未合并。

## 2026-10-25 Issue95：全路时间／空间相关长流已完成

用户要求具体数据，接续同PR188/分支task/95-ideal-quality-20261025、tmp/rng-ideal-quality-issue95-20261025。执行源2dd9ec33fa321174f3891b0cd684bc5aac4b589a，7执行文件及本机C++二进制SHA冻结。已有三条Spectre理想阈值序列各20k/1us，raw/VN两路径、三后端、两个实例；18物理播种案例+18同形状PCG64统计对照，每路连续131072帧，100MHz约1.31072ms。只按需消费启动种子前缀，不把全20k都说成驱动输出；默认1s换种未触发。没有同时物理阵列通道，物理空间相关留空，不能把三个noise seed充作空间lane。

R8、五阈值q4/13/64/128/192、8个bitplane测全部路；时间lag1..128/256/512/1024，R8/阈值空间lag0/1/2/4/8/16/32/64/128，bitplane空间仅同拍。两个实例分别1/64/20lane，区分实例内与实例间；504组观测、3024峰值记录、17124432相关系数，具体路号/lag及短窗T8..128方差/MSE全部保留。

q128/raw三个seed总体max|rho|：LFSR时间.010121/同拍跨实例.003200/错拍.006666；GF64时间.012355/同拍.010972/错拍.013372；Bivium时间.010807/同拍.009977/错拍.012212。不同测试对数不可据max直接排名；同形状IID对照已实跑。GF64四路XOR仍恒0，稀疏命中约.69而IID约.370780；Bivium对应q13接近.377306参考。物理种子改善不消除固定联合结构。

5新增单测、22524运行时核验、6122归档/矩阵审计通过；18案例前4096帧逐字对上轮Python原件，C++中段/尾段/状态另验证。1440/390浏览器和下载链接检查通过。新报告远端上传/rng_correlation_20261025.html；完整CSV包rng_correlation_20261025_tables.zip（63284726B）；原始流/矩阵/JSON在project_archives/rng_correlation_20261025。中央run rng-correlation-95-20261025，仅DESIGN_PROOF，PPA未知。恢复work/rayggxia/95/correlation_20261025/HANDOFF.md，实际远端增量发布见PUBLICATION.json。不改旧225例、Issue184/152模拟任务；无新Spectre/RTL/EDA/LLM；Projects待权限同步。

## 2026-10-25 Issue95 / PR188 已发布

理想读出分层质量已通过 PR188 发布并待审，未合并：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/188 。科学提交413e786fd1a8d08c1825f1886a3000929aff5bc0；完整tree 38b2634008ef6db09b53a7e9872df0faf7ad60bd与本地一致，报告远端读回逐字符一致。225案例与验证结果不变；新增台账与根镜像已同步且保留并行记录。恢复见work/rayggxia/95/ideal_quality_20261025/PUBLICATION.json。Issue95保持开放，Projects待有权限维护者同步。

## 2026-10-25 Issue95：理想读出20k的定时分层质量

用户同意等待实际比较器数据时，先用三条理想阈值读出做基线。task/95-ideal-quality-20261025，tmp/rng-ideal-quality-issue95-20261025，base d6d33995754fcdcea99286e4ce43f91647aa231a；执行本地提交 bdbab3e38ff56e267783af9ac327dbba67a0e169，冻结5文件SHA。已有ideal_and_old_20000_v1三seed32003/32009/32027，各20000bit、1us，仍带旧比较器负载；无新Spectre。216主例+9重复种子对照全完成，每端点4096帧；四个固定5000bit冷启动段，不是12独立物理轨迹，也不触发默认1e8拍/1s周期换种。

理想原始rho1 −0.0037～0.0101，V128为1.208～1.596，不能凭lag1认定IID。VN理想保留约25%；旧比较器VN保留约12%，仍负rho1 −0.236～−0.187。分发逐bit保持，仅截断包末尾；LFSR每端32状态bit，Bivium192总线bit→177状态bit/15丢弃。理想直通双端首次请求63.03us/383.08us，VN为213.03～275.03us/1461.08～1617.08us。GF64前四路q128 XOR恒0，理想直通q4恰一路命中0.685～0.706，对比IID约0.371；Bivium q13约0.362～0.396，对比约0.377。较好种子不消除固定联合关系，PRNG不增加物理熵。

6单测、8956项可复现审计、独立只读复核及1280/390浏览器检查通过。归档project_archives/rng_ideal_quality_20261025（225NPZ、完整JSON、执行bundle、源码zip）；中央run rng-ideal-quality-95-20261025，仅DESIGN_PROOF/PPA未知。报告architecture_tlm/random_service/quality/results/ideal_20261025/REPORT.html，本机远端上传/rng_ideal_quality_20261025.html。HANDOFF/PUBLICATION位于work/rayggxia/95/ideal_quality_20261025；发布状态以回执为准，未自动合并/关闭Issue95。当前在仿真的物理任务Issue184/PR185及他人Issue152只读未改；Projects待有权限者同步。

# 2026-10-23 Issue95 分层随机质量首轮

负责人rayggxia；本地已完成，待上传。分支task/95-rng-quality，base pbit-tlm-attention-details-20261016@6966739a；目录tmp/rng-quality-issue95-20261023。189案例/9测试/1269核对及浏览器通过；无新EDA/PPL。正式入口architecture_tlm/random_service/quality/README_ZH.md；交接work/rayggxia/95/quality/HANDOFF.md，发布回执同目录PUBLICATION.json。GitHub发布前HTTP传输异常，Projects无可用操作；不写远端已交付。根记忆canonical/mirror已保留原增量同步，中央台账仅添加新run并重建总览。下一步恢复网络后刷新远端，保留其他record合并catalog，再上传PR。

# rayggxia 当前任务

## Issue112 资源预算与片上存储探索计划

- 更新时间：2026-10-22；负责人：rayggxia（本轮连接器已核实）。
- 分支：task/112-resource-budget-plan；PR base：pbit-tlm-attention-details-20261016@eb317e4f6fb1b0d8844887401f3275f128ef8a83。
- 工作目录：C:/Users/86134/Documents/a_P_BIT/tmp/resource-budget-issue112-20261022，独立最小稀疏worktree。
- 阶段：中文实施计划已上传PR114，ready/open待审、未合并；来源提交18c2a62f4a6cee4cf2a7df62594510a35073639d，4份来源文件远端回读一致。最终回执见work/rayggxia/112/PUBLICATION.json及Issue112，不自动合并/关闭。
- 成果：architecture_tlm/resource_budget_plan_20261022/PLAN_ZH.md；本机pbit_llm_master_report_20261012/PBIT_LLM_ASIC_RESOURCE_PLAN_ZH_20261022.md为同字节阅读副本。
- 验证：12个固定Git文件链接解析、四份封存结果数值、FFN/KV容量/带宽下界、UTF-8/LF和阅读副本SHA通过；记录work/rayggxia/112/VALIDATION.json。
- 边界：仅计划/文档核算，无新PPL/GPU/Slurm/TLM/RTL/EDA/DRAMSys；2/4MiB非最优结论，完整物理PPA保持null。
- 待同步：当前连接器未提供Projects操作；唯一备忘录维护源的入口追加由其维护流程处理，拟文见HANDOFF，不覆盖其他工作树增量。
- 下一步：PR审阅；后续从资源账本、条件下界和恢复/供数流水开始执行。本任务未接管95/96/104/107/110。

以下保留此前状态的历史快照；Issue98/PR100及Issue95/PR97已进入本任务集成基线，不将旧“待审”文字作为当前状态。

更新时间：2026-10-22；本会话 GitHub 连接器实际账号 rayggxia。

## Issue98：benchmark / LLM质量 / PPA统一调研

- 分支：task/98-benchmark-protocol；PR base：pbit-tlm-attention-details-20261016@83e15289434af50fc09c35e699d8b39965389d98。
- 工作目录：C:/Users/86134/Documents/a_P_BIT/tmp/benchmark-protocol-issue98-20261022，最小稀疏 worktree。
- 阶段：研究文档、16篇结构化对照与协议已上传；PR100开放待审未合并，源提交618b85ac59e4823497dc8ae7083aefc75247b7f4，9份来源文件已远端读回一致。最终发布状态见work/rayggxia/98/PUBLICATION.json；不关闭Issue。
- 验证：work/rayggxia/98/verify.py，33项文档/数据一致性、来源制品hash、Git内链接及例子复算通过；不是33项模型或PPA测试。
- 成果：architecture_tlm/benchmark_protocol_20261022/README_ZH.md、PAPERS.json/.csv、PROTOCOL_PROPOSAL.json。
- 未运行：模型、训练、GPU、Slurm、TLM、EDA；协议/质量门槛是提议，未知物理成本仍null。
- 待同步：Projects权限/写入未核实；长期备忘录唯一维护目录已有其他任务未提交增量，不覆盖。待合并/维护时追加本研究入口，拟追加文字在HANDOFF。
- 下一步：PR100评审验收；质量预算与协议评审后再决定新实验。接口实现仍由Issue95/96负责。

## 并行既有任务保留

Issue95随机源模型/RTL已由本账号发布PR97，开放待审未合并；其工作目录、进度及实际验证以 task/95-rng-service-rtl 的 work/rayggxia/95/HANDOFF.md / PUBLICATION.json为准。本分支没有修改其源码、默认配置、冻结结果或工作目录，也未接管Issue96等成员任务。

## 2026-10-22 Issue95 架构图续作

PR97已合并（上文旧状态为历史）；当前新增离线架构核对图，源码/数值模型/RTL未改。task/95-rng-architecture-view基于eb317e4f，目标pbit-tlm-attention-details-20261016。12场景372沿由原模型导出；11模块交互及1440/768/390宽度浏览器检查通过，无JS错误。文件architecture_tlm/random_service/architecture-view.html；恢复work/rayggxia/95/VISUALIZATION_HANDOFF.md。已注明PR103小接口与38322118后续布局前PPA边界。待文档PR评审与用户核对，不代表整机已全部换源；Projects同步未核实。本节不改变Issue98记录。

可视化交付PR：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/113，开放待审、未合并；源提交bc8561813c110b62829287661c1303c65a2d14b0。远端HTML已读回与本地逐字符一致。

2026-10-23 Issue95发布回执：网络已恢复，分层质量实现/结果已上传PR134（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/134），开放待审未合并；科学交付1f8e1d468792b5af17d337db885b482c189c00f9。完整远端tree与本地c8162a04b3c32bd0d5615108d8dc7b93bdf0b1ee相同，报告读回逐字符一致。旧网络阻塞文字仅为先前时点，无需重复实验。

## 2026-10-23 Issue95：旧比较器采样间隔纠正

用户指出当前应较慢采样，复核确认质量主链硬编码0.5us，不能把旧比较器rho约0.72～0.74泛化为慢速采种质量。复用9条已签SHA波形，72项间隔重分析/216 Pearson交叉核验/9数组SHA通过；10us固定时间lag的两款旧比较器三seed范围0.027～0.052，20us约0.018～0.047。单相位长间隔样本少，不能宣布IID或长间隔更差；P1偏置不会随间隔自动消失。VN原负相关仅属0.5us场景。

RandomNetwork未规定同一物理源采样间隔；SeedWords.interval是调理32bit字间隔，1亿拍换种在100MHz约1s，但不决定包内原始bit间隔。下一轮需显式物理时间戳/同源间隔及调理时序，再贯穿各层。入口architecture_tlm/random_service/quality/results/sampling_review_20261023/REPORT_ZH.txt；用户副本远端上传/rng_sampling_review_20261023.txt。沿用Issue95/PR134/task/95-rng-quality与现有工作目录，不改原189案例、旧报告或正式模型默认，不新增EDA/RTL/PPL/数字实验。台账原run补充后处理索引，不虚增实验数量。补充远端交付状态以work/rayggxia/95/quality/SAMPLING_PUBLICATION.json为准；Projects未同步，PR不自动合并。

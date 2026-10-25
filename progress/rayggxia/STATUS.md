# Issue184 常规比较器已实际运行 / 2026-10-25

2026-10-25新Issue184由本轮已核实rayggxia负责，独立task/184-normal-readout@d6d33995，tmp/normal-readout-issue184-20261025，不接管152/jieruiz旧任务。已把38380128三seed各20000次1us理想/旧比较器逐位CSV及单列TXT导出到analog_pbit_20261016/ideal_and_old_20000_v1，11文件SHA通过；旧MID分别1089/1145/1115，全部保留。真实源原本接旧比较器，理想判决不是完全裸核心或实际数字读出，500Hz短记录不证明IID/慢漂移。新normal_readout_v1复用未实测10MOS无输出限流拓扑，1.2V、SVT/LVT输入、10/20uA，输入反型及饱和裕量实测门禁；源01d63b66aa5653dffb4d116e1b1d5f9c951b1571，manifest743bbec6b48ee440773623698c5de423d21756ad721edc4ee1411b7082d8ec82；24文件逐个SFTP上传，无新源码压缩包，8本地/8远端测试、17Python3.6 AST、Bash和27PDK哈希通过。实际Slurm38387635已RUNNING，m3ca1003，03:54:35Z观察；8CPU16GB、APS1最多8案例、6h+15m，snapshot normal-JMJc0ox0/source不可改。4候选中SVT20u尾管VDS-VDSAT=-12.6162mV拒绝，另3正常；确定性策略选LVT20u，输入overdrive189.9/193.3mV、gm/Id11.98/11.86；1mV连接核心阶跃最坏3.5ns、10mV1.5ns，采样分辨0.5ns；不等于独立随机位率。短精度、独立cal62003/9/17冻结及新val64007/13/33每条22ms总/20ms有效/1us/2万位仍待执行结果，numeric63003/17/29与cal/val分离，fmin500Hz，本轮不自动1s/10Hz长任务或精确能耗。结果根/public3/home/t6s011227/analog_pbit_20261016/normal_readout_v1/results/38387635，结束自动normal_readout_38387635.tar.gz/.sha256。台账新增派生索引（cases空、不算新实验）与真实新run，拒绝项保留。PR实际发布以work/rayggxia/184/PUBLICATION.json为准，不虚报合并。

# Issue184 常规比较器与2万次导出 / 2026-10-25

负责人rayggxia，task/184-normal-readout，基线d6d33995，独立tmp/normal-readout-issue184-20261025。3seed各20000次1us理想/旧比较器CSV/TXT已导出，11文件SHA通过。新24文件常规偏置10MOS脚本完成，8测试/17模块3.6AST/Bash/27PDK哈希通过，实际Spectre待提交。formal architecture_tlm/physical_rng_normal_readout，交接work/rayggxia/184/HANDOFF.md；不改Issue152旧快照/负责人/STATUS。本条为本地准备，PR及实际作业以后续回执为准。

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

2026-10-25发布回执：Issue184/PR185已实际发布为draft/open，未合并；科学提交97ec6f12df651fc11cfa497521fe0b465cf7823a，完整tree9600d63c40808cc2236dd1a06def8fc3686ffc10与本地f7e6110bfae671b09e75d6dca7d020fbff3d85bb一致，5份关键源文件远端逐字符读回一致。实际执行源仍01d63b66，提交后快照未改。04:06:57Z观察38387635仍RUNNING，29案例已结束；首条precision_fine_seed63003为3ms总/2ms有效，实际1us采样2000次，密集输出P1=0.5109、MID=0.0068，耗时877.6s；尚无新比较器独立校准冻结或每seed2万次最终验收，不能把该短记录当正式结果。旧3seed各2万次逐位文件已在ideal_and_old_20000_v1。Projects工具未暴露，待维护者同步。Issue152接口已留言，原负责人/分支/STATUS未改。

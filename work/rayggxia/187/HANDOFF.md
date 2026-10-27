# Issue187交接

## 2026-10-27 保守调度审计追加

用户要求将当前保守调度整理为文件并核查论文惯例。沿用本Issue/PR189，不修改Issue186的实现。只读PR192@556462dc5db37582310302ed8b916d717b4d6ceb与其12项500MHz条件结果；报告CONSERVATIVE_SCHEDULING_AUDIT_ZH.md已推送源提交2a7352b767fb6966b800a04522d0650bae3864eb，6文件逐字回读/tree通过，本地同一SHA。PR仍待审未合并；回执CONSERVATIVE_PUBLICATION.json，Issue评论6435467483。

执行：python -B work/rayggxia/187/check_conservative.py --source-root C:/Users/86134/Documents/a_P_BIT/tmp/ffn-local-pipeline-issue186-20261025。产物CONSERVATIVE_CHECK.json记录8源码SHA、12结果/派生配置SHA、两任务预约微例与报告SHA。微例是软件Scheduler验证，不是新数字/PPA run；无全模型重跑。原33条证据及旧HLS验证不改。

结论：FIFO预约、宏DMA排空、SRAM整描述符占用、数字预填充关闭和SC跨窗口限制值得隔离验证；数字/SC优化不对称；保守PPA与乐观假设并存，不能称整体上界。不概括“大部分模拟器不保守”。下一步实现仍由Issue186接续，保持容量/依赖/响应/计费守恒。

负责人rayggxia；日期2026-10-25。任务为只读文献调研及正式研究文档发布，无新硬件/模型实验。

## HLS专题追加（2026-10-25）

已推送源提交884b9717852fa17cd2893413ea14cc614dbbc64f，9个文件读回一致，Git tree21989edb4813b87959f7508d074c241422418c44与本地index相同；精确commit已导入。PR189待审未合并，后续元数据head以PR为准。长期备忘录同字节同步并保留既有字节；其维护提交归Issue28。
用户询问功能＋工艺库如何确定周期、论文是否需要HLS。沿用本Issue/PR189，新增architecture_tlm/simulator_survey_20261025/HLS_LATENCY_ZH.md与HLS_SOURCES.json；不扩大至实现。核对5篇论文及工具官方资料，明确HLS、Chisel/SpinalHDL、手写RTL三路线，Latency/II/时钟与反压区别。只读PR190@ee21c0ce的ffn_latest/config及MATURE_SCHEDULING，引用其最新结果替代旧“186实施中”的时点，不改其他任务文件。

建议优先做桶归约/系数恢复/宽位累加的ASIC HLS小试点，同时闭合数值语义与数字基线。Catapult/Stratus许可和服务器环境未核实；本机PATH未找到命令不能推断服务器没有。本轮无HLS/RTL/EDA、TLM运行、模型质量实验；仅文档/引用/当前源码SHA及参数复算检查。实际发布回执见HLS_PUBLICATION.json，维护备忘录见HLS_MEMORY_SYNC.json。下一步等用户的实施指令与PR审核，不能据建议自动提交昂贵EDA作业。

## 基线和成果

- 仓库rayggxia-workspace/pbit-llm-qwen-baselines；分支task/187-simulator-survey；main基线5273e5d9fdae811a714f1a278fee6e776c5675af，tree bdf5aca1429971b4e2db0f4625769e11c2f37580。
- 独立稀疏worktree：C:/Users/86134/Documents/a_P_BIT/tmp/simulator-survey-issue187-20261025。
- 正式成果：architecture_tlm/simulator_survey_20261025/六个文件；源数据EVIDENCE.json，表/CSV由build_and_check.py生成。
- 本地来源PDF未上传。source_checks/保留三个渲染页供核表，已.gitignore；原PDF路径/大小/SHA见SOURCES.json。没有模型/工艺库/长轨迹。
- 引用PR183固定head0341b4acde1e0afd7decf4a48b037e6b376343d8，核查时open未合并。Issue186负责调度实现，本任务仅提供验证需求。

## 实际检查与未运行

执行：bundled Python -X utf8 work/rayggxia/187/build_and_check.py；33记录/67URL文档一致性通过。结果和文件SHA见VALIDATION.json。最终git diff --cached --check应再次执行。

三路原文证据经父任务转录、原研究分支复核；修正Kelle表定位、PIM-GPT普通DRAM/PIM时序区分、X-Former ADC来源、LLMCompass锁频、Timeloop验证集、Accelergy占比误差、SANTA v2版本及TPOT定义。

没有论文artifact运行、模型权重/语料实验、GPU/服务器、TLM执行、RTL/EDA/PPA。模型/数据SHA不适用于本轮文献任务，不能将文档检查数当性能验证。

## 发布与下一步

PR189已发布、开放待审未合并；源提交725a8e69f4f02d331f33b67e3ff1810b22f07585；11个源文件逐字远端读回，tree 1a7095817a1df079838b8b778f8104af69c95755与本地一致。回执见PUBLICATION.json。只提交本任务显式文件。远端Git网络CLI不可用（getaddrinfo线程错误），采用已核验rayggxia连接器创建Git对象/分支/PR；未改变历史origin。通过SOURCE_COMMIT.json恢复精确commit字节，经Git SHA验证后导入本地，未生成不同历史。

PR待审不关闭Issue，不自动合并。下一步按审阅意见补来源或需求；若要实现建议，接续Issue186或另立独立可验收任务，不在本文档PR混入代码。Projects权限/写入未核实，待同步。

长期备忘录唯一维护目录已有未提交更新，已在确认根镜像字节一致后只追加本任务入口并同步；旧字节保留，前后SHA见MEMORY_SYNC.json，其维护提交仍归Issue28。交付后保留此最小待审worktree，不创建额外全量副本。3个ignored核表PNG总量很小，原用户PDF仍在原路径，清理本工作副本时可重新渲染。

# Issue187交接

负责人rayggxia；日期2026-10-25。任务为只读文献调研及正式研究文档发布，无新硬件/模型实验。

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

发布回执写PUBLICATION.json。只提交本任务的正式目录、本人STATUS和work/rayggxia/187显式文件。远端Git网络CLI不可用（getaddrinfo线程错误），采用已核验rayggxia GitHub连接器创建Git对象/任务分支/PR；不改变历史origin，不尝试其他身份。

PR待审不关闭Issue，不自动合并。下一步按审阅意见补来源或需求；若要实现建议，接续Issue186或另立独立可验收任务，不在本文档PR混入代码。Projects权限/写入未核实，待同步。

长期备忘录唯一维护目录已有未提交更新，禁止覆盖。本任务只在确认根镜像字节一致后追加简短入口并同步；其维护提交仍归Issue28。交付后保留此最小待审worktree，不创建额外全量副本。

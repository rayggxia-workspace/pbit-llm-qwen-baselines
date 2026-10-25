# rayggxia 当前研究任务

更新时间：2026-10-25。GitHub连接器身份rayggxia已核验；正式仓库rayggxia-workspace/pbit-llm-qwen-baselines。

## Issue187：LLM架构模拟器与PPA证据综述

- HLS专题已推送PR189，源提交884b9717852fa17cd2893413ea14cc614dbbc64f；9个源文件远端逐字读回一致，tree与本地index一致，精确Git对象已导入本地。原33条矩阵保持不变；新增12条专题来源、3个当前项目文件版本核验。回执HLS_PUBLICATION.json；仍待审未合并。
- 2026-10-25追加：用户询问功能与工艺库如何确定周期，以及是否引入HLS。新增HLS_LATENCY_ZH.md，核查HSA/FSGen/SpAtten/Anda/HLSTransform和官方工具资料；只读PR190@ee21c0ce9a14662aad98abbda8277f8af37365b8。建议局部ASIC HLS试点桶恢复/宽位累加；不是已经运行或确定采用HLS。发布状态见work/rayggxia/187/HLS_PUBLICATION.json（生成后）；无新模型、RTL或EDA实验。
- 分支：task/187-simulator-survey；PR base：main@5273e5d9fdae811a714f1a278fee6e776c5675af。
- 工作目录：C:/Users/86134/Documents/a_P_BIT/tmp/simulator-survey-issue187-20261025，最小稀疏worktree。
- 当前阶段：[PR189](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/189)已发布、开放待审未合并；源提交725a8e69f4f02d331f33b67e3ff1810b22f07585，11个源文件远端读回一致，远端tree与本地index一致；发布回执见work/rayggxia/187/PUBLICATION.json。
- 成果：architecture_tlm/simulator_survey_20261025/README_ZH.md、REQUIREMENTS_ZH.md、EVIDENCE.md/.json/.csv、SOURCES.json；33条论文/工具证据、67个去重来源URL。
- 实际验证：build_and_check.py检查结构、JSON/CSV一致、相对链接/锚点、关键范围约束、UTF-8/LF、4份用户PDF SHA、SANTA batch公式复算；三条研究线独立复核转录，综合建议复核通过。
- 未运行：模型/PPL/训练、GPU/Slurm、TLM、RTL/EDA/PPA、论文artifact重跑。不是新的硬件实验，不新增数字run台账。
- 关系：接续Issue98的benchmark研究；只读PR183@0341b4ac与Issue186，保留unified_v6、不接管调度实现。
- 待办：PR审核验收；Projects权限/同步未验证。长期备忘录唯一维护副本已追加本任务入口并同步根镜像，保留其现有未提交改动；核验见MEMORY_SYNC.json，维护提交仍属Issue28。

## 历史任务入口

旧Issue98及95等状态以其原分支STATUS/HANDOFF及最新远端Issue/PR为准。本分支main基线没有rayggxia STATUS，故新增当前任务入口；未覆盖其他成员STATUS，也未修改已有实验。

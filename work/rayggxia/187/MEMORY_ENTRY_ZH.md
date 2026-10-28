## 2026-10-25 Issue187：LLM模拟器/PPA证据调研，PR189待审

- 用户要求全面调查论文的模拟器、自建模型、ASIC/XPU对象、工艺/频率、结果与可信度，明确p-bit LLM投稿所需系统仿真。33个代表性论文/工具条目、67个来源URL已形成结构化矩阵；不是会议全量普查。
- 正式成果：分支task/187-simulator-survey的architecture_tlm/simulator_survey_20261025/{README_ZH.md,EVIDENCE.md,EVIDENCE.json,EVIDENCE.csv,REQUIREMENTS_ZH.md,SOURCES.json}；PR189：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/189，开放待审未合并。源提交725a8e69f4f02d331f33b67e3ff1810b22f07585；base main5273e5d9。
- 本地最小目录：C:/Users/86134/Documents/a_P_BIT/tmp/simulator-survey-issue187-20261025；本人进度progress/rayggxia/STATUS.md、交接work/rayggxia/187/HANDOFF.md。来源指纹和发布回执在该任务目录；用户PDF没有上传。
- 推荐保留unified_v6+既有ZigZag+DRAMSys/DRAMPower，补模块RTL/PVT成本、有限随机流/读出/转换/CDC、独立时序核验与真实Instruct质量闭环。PyTorchSim用于未来编译/ISA需要；ONNXim用于匹配探针，不将局部0.23%误差当LLM整系统保证。
- 只读引用PR183@0341b4ac、Issue186；未重写调度，不接管其他任务。PR183时间是给定配置的单步decode；全机PPA仍未知，DRAM负ACT分项不能当整体误差界限。文献建议不是会议统一规则或已批准质量阈值。
- 已做文档/来源/JSON-CSV/链接/UTF-8-LF/SHA与公式检查，三路线转录和综合建议复核；11个源文件远端读回一致，remote tree与本地index一致。无新模型/PPL/TLM/RTL/EDA实验，未重跑论文artifact；Projects权限/同步未核实。待PR审核验收，未自动关闭Issue或合并。

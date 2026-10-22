# Issue95 随机源模型与核心RTL交接

2026-10-22。负责人/已核验连接器账号rayggxia；正式repo rayggxia-workspace/pbit-llm-qwen-baselines。
分支task/95-rng-service-rtl，base pbit-tlm-attention-details-20261016@83e15289434af50fc09c35e699d8b39965389d98。
独立稀疏目录C:/Users/86134/Documents/a_P_BIT/tmp/rng-service-issue95-20261022；不使用/覆盖其他成员未提交状态。

实现入口architecture_tlm/random_service/，原parallel_sampler_v5.py仅增加可选timed-source钩子；默认理想源保持。基础LFSR、现有GF64共享、Bivium；直接新种子分配、启动禁止固定种子输出、慢速重播种、回压、保存/重放、操作统计和可综合RTL。

验证：本工作目录VALIDATION.json/python_tests.log；rtl_final/RESULTS.json与每例日志，9例8100沿逐一匹配，另FFN250沿；最终发布摘要复制到RTL_VALIDATION.json。此前第一轮Icarus语法失败保留rtl_validation，修复后rtl_validation_v2与最终目录分开。旧v4测试一次因Windows默认临时目录权限失败，最终validate.py显式设置任务内temp目录而不修改旧测试。

OS种子demo和三固定seed统计诊断都保留原始输出；不宣称物理熵、完整PPL或PPA。待用户自行做DC/PT等工艺仿真，POWER_SIM_ZH.md与模板说明边界。DESIGN_QUESTIONS_ZH.md是本轮疑点/决策清单。

发布状态以PUBLICATION.json及远端PR为准；本文件创建时本地实现完成，尚未推送。任务未合并前不关闭Issue。Projects未验证权限，待同步，不宣称已更新。后续确认本分支新head与源码hash，再续同一任务，不重复创建副本。

大波形/编译产物只保留本地和交付包，不入Git。交付前按SHA归档旧验证目录；本PR待审保留最小源码工作树。没有GPU/Slurm/模型推理/许可EDA操作。


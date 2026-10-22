已交付[PR109](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/109)，ready/open待审、未合并。科学head7b12fea03bd2596cc206f3f0c32571196688e665，9关键blob远端原字节回读一致；后续只补回执。

52封存情景完整/阶段核等效周期、物理访存和假设已整理：100MHz核、80MHz SRAM，Link有限窗口。当前时序是条件模型，MAC/向量/非线性/权重驻留/局部状态/源/CDC仍需落实，不能只认为PPA未知。完整报告和代码在architecture_tlm/digital_ppa_v1。

源码23e8d65：66功能组、12870输出逐位、63活动预检通过，29源blob与Git原字节一致；单独ZIP解压的编码/恢复96输出也通过。没有新模型/PPL/GPU/Slurm/DC/PT/STA/实际DRAMSys。功能一拍不证明10ns；非线性/融合候选须另验质量。随机源、p-bit和随机矩阵阵列未写。

113124B本机源码包digital_ppa_v1_20261022.zip，SHA d8004f0fdf586dc020e99c3d6e6ed3b29050a652a55af037220af898c03aafb2；Git供正式源码/说明。原1061份临时原件526321920B逐SHA归档成75976225B，核验后回收本任务目录，原始数据仍可恢复。STA/PT下一步的位宽、PVT、时钟、模式、有效项/帧、面积/能量/II字段及操作模板在PPA_TASK_ZH.md。STATUS/HANDOFF/同字节长期记忆同步，Issue保持open等评审，PR105/103不动。Projects实际查询记录在PROJECTS_CHECK。

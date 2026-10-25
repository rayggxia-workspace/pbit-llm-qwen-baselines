# Issue186 本地权重流水续作
- 负责人 jieruiz；分支 task/186-local-pipeline；main 基线 d83eeb1fc6b89a3dff51b5b62bf79acf665c7166。
- 独立目录 tmp/ffn-local-pipeline-issue186-20261025，正式新目录 architecture_tlm/ffn_local_pipeline_20261025。
- 范围：有限双本地bank，单SC阵列/计数器/归约；可选DMA响应绕过共享SRAM的本地搬运。保留主线默认与原数据。
- 当前：代码小形状检查通过，独立审阅/合同测试进行中；尚未发布PR。下一步冻结代码，CPU Slurm运行3个全36层对照与10个单层诊断。
- 实验为合成事务时序，无真实模型权重/语料/PPL，无新RTL/STA/PT；HBM原库电流未标定，不能声称整机能耗。
- 保留每波权重/系数、64次GU及64次NL/Wd采样、K64恢复顺序；128单列。新增本地bank成本未知，按容量显式列出。
- 项目看板缺read:project权限，待同步；不自动合并。

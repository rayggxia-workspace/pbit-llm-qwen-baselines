# Issue245 跨模型原生pilot交接

2026-11-08更新：24/24 pilot均已COMPLETED且WORK_GATE PASS，全部封存文件SHA复核；数组已自然结束。完整原始JSON归档project_archives/cross245_20261108/SEALED_PILOTS.tar.gz（SHA6e0198f2460989ef40ba24ca9a6969b4581d6b6b36dd1b9bd3c918e19a0f86e2），小索引VERIFIED_PILOTS.json。新增component_budget.py/COMPONENT_BUDGET.json只计算静态权重下界和标定核增量，不是总能量或整机时延。TT250三版目前仍无完整验收价格；见ffn_tt250_repair_20261107最新交接。下方首次完成/运行中为旧快照，勿重跑。

负责人rayggxia；task/245-cross-model-estimate，PR247 base main。用户授权执行硬件评估，不测准确率、不下载大权重。开始时远端25e950b5cb95e0fa62122f38f6cc17ab284f1820；本地历史be39450a保持。最新README/AGENTS、Issue245及其评论、244/247/248/249已核对。项目看板无可用写接口，待维护者同步。

本次正式入口`architecture_tlm/model_scaling_20261106/{execution.py,prepare_execution.py,run_case.py,test_execution.py,EXECUTION_STATUS_ZH.md}`。执行器为独立试接，不修改100/250默认和198/204源。私有源只在local_runtime/和远端；禁止把整个work目录加进Git。

实际提交38625522数组0-23%2，1CPU/10GiB/2h每项，0GPU；原生LPDDR派生8533，现有动态库复用。准确地址和SHA见SUBMISSION.json。首次检查00_Qwen100SC完成且字节/队列门禁通过，其他运行/排队。STATUS.json只是检查时快照；只有RESULT status=completed、WORK_GATE=PASS且SEAL内各文件SHA相等的任务才收结果。

本地四项Gates通过：24物理bank/尺度表布局、12全形状FFN分包计数、3seed所有参考地址键覆盖、合法等面积配额。先前未封存的本地全层原型曾因参考键把g/query索引颠倒而KeyError；已在提交前修正，未把失败当完成。两个完整尺寸FFN本地回放完成，不是整机结果。新代码和测试SHA见SOURCE_MANIFEST.json。

主线未完成项必须先读EXECUTION_STATUS_ZH.md末节：本试接偏串行、250 r32未对齐主线r16、四Q槽填充、norm/RoPE/残差实际读写/计价、250合格PPA。没有提交全层任务，没有最终PPA/精度主张。当前pilot用于守恒和跨模型适配，不将较串行时间当原硬件性能或直接乘层数。不要重跑健康任务/覆盖快照；后续修正另建执行快照和SHA，先Qwen回归再全模型。

恢复：在本checkout用Codex附带Python执行ops.py status；它调用已有local_tools/paracloud_client，不输出凭据。若需要收集，先逐封存JSON和SHA检查，再小型汇总；大原件留EDA或project_archives约定目录。当前目录留最小必要文件，不新建全量checkout。

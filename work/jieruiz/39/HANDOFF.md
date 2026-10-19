# Issue39交接

2026-10-19，负责人jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines，PR base pbit-tlm-attention-details-20261016@c1555ae。独立分支task/39-ffn-clipping，目录tmp/qwen-ffn-clipping-issue39-20261019。

新任务：裁剪PPL、静态train分组尺度与二次幂实现成本，依赖已合并范围修正Issue32，避免修改Attention成员任务。已读最新README/AGENTS/STATUS/TLM索引，核实账号jieruiz有push/admin；开始时本人Slurm队列为空。

当前本地编码中：experiments/qwen_ffn_clipping_20261019/，未提交/未上传/未运行。并行kernel工作树tmp/qwen-ffn-clipping-kernel-agent39，仅负责clip_core和单测；主工作树负责runner、部署、汇总。

验收步骤：核对control严格重现、端点p1、分组scale恢复、PoT舍入；先提交源代码再打tar部署不可变快照；Slurm prepare跑原BF16完整基线/hash/train校准，成功后53case数组（含无采样control、3固定seed、512及预选2048诊断）。记载实际job/hash；收回所有完成输出，逐SHA核验，通过PR交付，更新memo。无新PT/TLM数据；Projects曾缺read:project，需要再核实但不阻止代码和Issue同步。

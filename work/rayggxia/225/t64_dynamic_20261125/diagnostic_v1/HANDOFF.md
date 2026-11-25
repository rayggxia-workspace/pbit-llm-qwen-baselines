2026-11-25：g/u机理诊断完成。6320唯一采集并通过观察器末logits逐位一致；median统计失败，6321 cuBLAS环境失败，6322复用同一6.23MB激活完成5层×16位置解析后级诊断，无重跑模型/PPL。极端幅度组只占少数；纯共享造成低事件概率更关键。简单截断伤害首/末层；共享基准＋1bit修正后局部NMSE接近原四档，尚无该新方案PPL/PPA。优先候选为组64基准＋1bit，而非再缩组或全层统一裁剪；这是建议，未修改默认。报告experiments/t64_dynamic_scale_20261125/diagnostic_results/REPORT_ZH.md，raw/source/失败记录均归档并校验。

# g/u共享尺度机理诊断

Issue225 / PR266，2026-11-25，rayggxia。用户询问组16低采样退化是否由离群值过多导致；现有均值/零码统计不能回答组内尾部分布，因此执行一个单窗口诊断，不运行新PPL或训练。

Slurm6320，原GPU、zhj/t64-dynamic-scale-issue225-20261125/diagnostic_v1。冻结T64 W8及原non_ffn，准确Attention，GU16/Wd32、动态组16；只捕获第0/9/18/27/35层各16个位置的g/u。相同输入和种子下，对比普通和仅增加观察器的最后token logits逐位相等后才分析。权重和原已完成执行快照均不修改。

对同一批固定g/u比较lane4、max64/32/16、第二大值PoT、max-PoT减一指数、组16＋逐元素一位S/4修正。解析计算后级32与128分层的期望、方差和零计数概率；Wd列范数与实际线性映射用于区分噪声与确定性编码偏差。浮点SiLU只作局部误差参考，不是候选硬件算子，不将该结果称为PPL或物理能耗。

解析moment与逐格枚举的CPU断言已在模型加载前通过；模型/观察器验证尚在执行。暂不能宣称哪个新尺度方案提高了模型质量。源manifest说明git_commit9789339555f8059dc02cf42d152db02d43a3cf81只绑定未改的父数值模块；新增diagnose.py按提交时SHA绑定，随后发布相同字节，不修改已提交manifest追写新Git SHA。资源包装器增加可选entrypoint，旧冻结远端副本保持。

精确命令/来源见SUBMISSION.json、EXECUTION_MANIFEST.json。下一步先看EXECUTION和outputs/RESULT的封存SHA；报告组内max/median、头部能量、低期望计数和噪声/偏差，不凭全局均值断言真实尾部。ACTIVATIONS.pt留授权结果存储，Git只保存位置与SHA。原学院62220健康任务不动，无新完整WT2/PPA/TLM默认修改。

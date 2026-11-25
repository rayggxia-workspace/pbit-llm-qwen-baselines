2026-11-25：g/u机理诊断完成。6320唯一采集并通过观察器末logits逐位一致；median统计失败，6321 cuBLAS环境失败，6322复用同一6.23MB激活完成5层×16位置解析后级诊断，无重跑模型/PPL。极端幅度组只占少数；纯共享造成低事件概率更关键。简单截断伤害首/末层；共享基准＋1bit修正后局部NMSE接近原四档，尚无该新方案PPL/PPA。优先候选为组64基准＋1bit，而非再缩组或全层统一裁剪；这是建议，未修改默认。报告experiments/t64_dynamic_scale_20261125/diagnostic_results/REPORT_ZH.md，raw/source/失败记录均归档并校验。


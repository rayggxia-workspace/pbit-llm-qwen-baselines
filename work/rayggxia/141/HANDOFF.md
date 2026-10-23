# Issue141 Qwen新采样器联合PPL（2026-10-23）

负责人rayggxia，任务分支task/141-qwen-sampler-ppl，PR143 draft/open未合并；base6966739，独立tmp/qwen-sampler-ppl-issue141-20261023，不修改Issue138训练目录，不恢复116/123。执行7a286ec140de6846006c96456275377fd22b4943已推送；正式结果qwen/results/parallel_sampler_ppl_20261023。

2802仅缺历史两校准资产而失败；新快照按原SHA补齐，2803已完成SHA门禁、原BF16完整299077目标11.652735047455899、12组GPU轨迹/分布＋仲裁/cap检查、6项8目标pilot。10个sidecar与identity本机回读通过。2804_[0-15]%2后缀4096目标运行；2805_[0-15]%2完整299077目标依赖afterok:2804，已提交未完成。每协议16配置，随机配置3seed；精确参数看正式README/PLAN。理想软件随机，不把结果继承给物理RNG或q256。

服务器/home/Hongjie_Zeng/projects/pbit-qwen-sampler-ppl-20261023-issue141；快照snapshots/7a286ec140de6846006c96456275377fd22b4943，输出outputs/同SHA；源码不改。回执work/rayggxia/141/remote/workers-submission.json。下一步只读squeue/sacct及已完成JSON，核对sidecar和每层覆盖，分别汇总后缀/完整。不要重交健康作业；不因pilot排序，不把pending写成完成。失败作业修复另冻执行源，保留旧原件。看板权限本轮未核，待同步；PR附加UI因侧会话thread not found失败，GitHub PR已实际创建。

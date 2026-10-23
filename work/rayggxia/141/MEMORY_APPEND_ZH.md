
## 2026-10-23 Issue141：新采样器联合Qwen PPL已提交

负责人rayggxia（侧会话），独立task/141-qwen-sampler-ppl / tmp/qwen-sampler-ppl-issue141-20261023，PR143 draft/open未合并；不改Issue138训练模块，不恢复116/123。冻结7a286ec140de6846006c96456275377fd22b4943，服务器/home/Hongjie_Zeng/projects/pbit-qwen-sampler-ppl-20261023-issue141。2802缺外部旧校准资产在verify失败；2803新快照按原SHA补齐后，模型/语料/旧源校验、12组GPU轨迹/分布及仲裁/cap守卫、6项8目标pilot通过；原BF16完整WT2精确11.652735047455899/299077目标。

固定FFN W8/B4/T32/K32/shared64、max4 fixed8×64/旧校准；BF16单seed，FFN-only/筛选准确PV/旧CTMC128/校正拒绝128接受/赢家1024更新各3seed，每协议16项。赢家argmax/burn0/spacing1/c=max；拒绝m0..24/cap128*S；理想FP32独立软件随机，未接物理RNG/q256，不继承新随机服务质量。后缀4096目标数组2804_[0-15]%2运行；完整299077目标数组2805_[0-15]%2已提交afterok:2804依赖，未收齐。只查看本任务HANDOFF与回执，不重交健康作业、不改冻结源码。正式qwen/results/parallel_sampler_ppl_20261023，恢复work/rayggxia/141/HANDOFF.md，具体发布以PR143实时head为准。pilot不作质量结论，完整结果仍待收集。未设置定时（临时侧会话不支持）。
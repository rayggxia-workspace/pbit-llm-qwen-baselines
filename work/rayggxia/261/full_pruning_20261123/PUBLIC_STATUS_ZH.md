# 完整硬阈值验证：13项已完成

2026-11-23最新：4项完整WT2、9项完整下游全部completed并核验；原6141/6146队列
已空，没有失败补跑或改动冻结源码。完整结果见
experiments/ffn_pruning_full_eval_20261123/REPORT_ZH.md及results/。

训练T64 PPL9.270730；纯输入20%9.304866（+0.3682%）；范数PoT20%9.298672
（+0.3014%）。唯一GU行需求相对减少17.84%。未剪枝→剪枝，PIQA acc
73.2862%→73.2318%、acc_norm 73.7214%→73.2862%；ARC-C acc
47.0990%→47.5256%、acc_norm 50.2560%→50.9386%；WinoGrande acc
65.6669%→64.7987%。PIQA有97题变差、96题变好，净少1题不是只改1题。

seed101、FFN64/64、准确Attention、36层、完整WT2及全部任务提示/答案位置范围
不变。44成员原件SHA、13完成、相同权重/输入/校准、目标/题数/36层及配对批次
通过；本地独立复算SHA/NLL/指标/正误转移通过。COMPLETED_RAW.tar.gz为4698022B，
SHA85396a156a8f58a1da1cca49c12a4ed54fbe3d3b196219d875b23a12e39642fb，
原服务器readback_completed_v1和本地原work目录保留。逐题文本不公开，私人命令
及绝对路径仍仅本地HANDOFF维护。结果收集器collect_completed.py是只读后处理。

30%/40%硬阈值和边界带概率剪枝只是下一步建议，未启动；不把它们称已验证。
PR继续开放待审未合并、默认不变，公开回执见PUBLICATION_FINAL.json。完整历史
STATUS/HANDOFF没有上传，Projects及正式备忘录由维护者接续。

---

以下是初始提交时的历史快照，不代表当前运行状态：

2026-11-23；rayggxia；Issue261 / PR262；task/261-ffn-address-coverage，base main。
继续原独立工作目录；本文件为提交后快照，恢复必须重新读取Slurm/封存JSON。

用户要求单seed完整测试及少量代表任务。主候选为已有纯输入幅度20%固定阈值，
训练校准不变；原T64配对、BF16父参考，范数PoT20%只加PPL对照。
T_x64/T_AND64、后级P8/LUT/AND/Wd和准确SDPA保持，不训练或扩大剪枝率。

- PPL：Slurm6141数组四组，seed101，完整292窗/299077目标。执行源码
  f3e89e2bfc02132f9cfa0e2b1d6376687947686e，manifest SHA
  43a99961e9e077e95505e259358d8720da265d53cc9fb5b43110c490c041c0f4。
- BF16完整PPL已封存11.5371603731、RESULT SHA
  f34ff64c97ab7e5784ed3c67a9112bcc555ed2b35a1dc36247d255a3b8d3df26。
  其它三组在运行；每组首窗须与此前同seed封存筛选NLL一致，不把8窗当完整结果。
- 任务：PIQA validation1838、ARC-C test1172、WinoGrande validation1267，
  完整划分、lm-eval0.4.8官方0-shot原文似然；PIQA/ARC同时报acc/acc_norm，
  WinoGrande报acc。前缀及答案全部经过当前FFN，不采用精确FFN前缀。
- Slurm6145门禁已completed，247.03s，官方HFLM包装前后似然逐位一致，三项
  各2题仅为功能门禁，未剪枝/剪枝的全部36层覆盖通过。Gate SHA
  776dd1652b3a6126d81b4678e35c542834bb2deb02bf63d0cf32c3a249871b85。
- Slurm6146数组9项：三模型配置×三任务，依赖6145成功后已开始/待资源。
  执行5df53bac765c069eacb33da276150cdd0a52cf8b，manifest SHA
  807238c8e2d1e995aba9f75eb949899aa63b5178189d9f774ae788560a507d1f。

源码包/manifest在本目录；私有准确launcher和Slurm命令留本机local_tools，不公开
服务器运维信息。STATUS_INITIAL.json是初始只读快照，不代表之后的最新状态。
没有完整任务准确率结果，不把门禁小样本分数当作正式成绩。

新实现入口experiments/ffn_pruning_full_eval_20261123/。inspect_results.py按completed
JSON/SHA、真实292窗或完整题数、模型身份、36层与配对输入批次SHA检查，只有
4份PPL和9份任务全部核验后才记13项完成。不要重交健康运行项或改冻结源码。
若明确失败，在新快照修复并只补缺项；旧失败/日志保留。

历史三任务选择来自已有Qwen3质量表（旧联合低采样设置分别下降5.44/8.11/6.95
个百分点）；只作为选任务依据，不能把不同权重/Attention的历史结果当本轮对照。
完整历史STATUS/HANDOFF本地维护，公开用本精简文件和Issue/PR同步；PR待审未合并，
Projects待有接口的维护者同步。当前不创建自动回查，不承诺聊天结束后后台监控。

## 2026-10-31 Issue220：用户最终确认11概率组＋2数字控制

用户否决缩减矩阵，要求保留原十组：无筛选及SparQ各赢家S64/128/256、校正拒绝S128、原稠密逐节点Gibbs S128。所有SparQ概率组与C_SPARQ候选统一256，r32/最近32不变；仅新增筛选族赢家S32（K_WH32），无N_WH32。共11概率＋2数字控制＝13独立训练组，不以部署扫描替代正式S32训练、不删除S256。

Qwen3-4B后训练、QKV/O-only、固定BF16教师、CE+0.5KL、每组100M上限及seed/数制/采样规则保持原方案；总名义上限1.3B，只增加一组100M，不推GPU小时。S32无筛选开关配对，原五对完整保留。K128历史PPL不能标为K256，旧P8拒绝限制未解除；未启动训练/Slurm/模型/RTL/PPA。

复用Issue220/PR221/task/220-attention-ten-case-plan，正式目录qwen3/training/attention_ten_case_20261031（名字保留）；当前CASES v2/REMOTE_AGENT_PLAN/REVISION_V2、validate_plan及SHA索引已按用户范围修订。实际验证/发布见VALIDATION_V2、PUBLICATION_V2；PR待审未合并、Projects待维护者同步。此前6概率组精简建议和S32替换S256建议仅为历史，未采用。

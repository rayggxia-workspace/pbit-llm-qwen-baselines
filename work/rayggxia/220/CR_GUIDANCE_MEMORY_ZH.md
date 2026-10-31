## 2026-10-31 Issue220：CR有界执行说明与可转发检验

用户要求明确修改CR并附检验给训练方。当前采用严格纯CR执行策略，不改概率律/P8/m/S或13组矩阵：每query/head总提议S×64，当前S128为8192；最后一轮恰好收齐算成功，否则归档并退出当前CR case、协调全部worker，其他case独立继续。不返回部分结果、不丢训练行、不隐式回退。上限保证成功或失败返回，不保证所有输入成功；不声称分布偏差已修复。

CASES仅增加执行/门禁状态字段，原11组、2控制、model/common/screening及采样数学参数逐对象保持。真实Qwen检验110592事件MC0超限/约214–222轮、P8归零约7%/2.95%、CR期望TV约10.4%/4.9%随报告附在CR_AGENT_REPLY_ZH.md。仅完成率/行级诊断，实际两更新及原10M阶段后再看训练质量。作为备选不阻塞赢家/数字对照。未新增GPU/训练/EDA或PPL，不重跑已完成3571/3572/3573。

正式入口qwen3/training/attention_ten_case_20261031/CR_AGENT_REPLY_ZH.md；同目录主方案/数值/复核/清单和校验器同步，父远端da2bbd276aeebe826d64deb59219c9bcae703ffb，复用Issue220/PR221/task/220-attention-ten-case-plan及本人原工作树。实际验证/发布见work/rayggxia/220/CR_GUIDANCE_VALIDATION.json和CR_GUIDANCE_PUBLICATION.json，PR待审未合并，Projects待维护者同步。

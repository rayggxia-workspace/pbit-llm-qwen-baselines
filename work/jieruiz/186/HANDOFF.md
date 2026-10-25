# Issue186 交接

更新时间 2026-10-25T05:33:14.297869+00:00。负责人jieruiz；工作树 `tmp/mature-scheduling-issue186-20261025`。任务分支`task/186-mature-scheduling`；基线0341b4ac/PR183，PR目标base `task/182-memory-hierarchy`；当前未合并。

## 已完成

共同 tile 有界队列与slot generation / retire、显式数字operand存储、真实DRAMSys SG；103旧回归通过。SG gate2938封存于results/scheduling_20261025/sg_gate。实际联调2942十项完成，VERIFIED.json保留远端原文件hash和小汇总。2941失败因小fixture2块装不下mandatory blocks，已修正为4，生产默认8未改。

## 运行中和不可变执行

31项数组2943，max20 CPU workers，未请求GPU。执行源码commit `bab9721d629df643e4096f5111a0a4ac5722ed3e`，57file闭包见SOURCE_bab9721d.json，包SHA `39873a2cd859d3ee8d16aef51f780703ae1ea4f212125c08d40ef37dd1d06c1d`。
远端 `/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/full_bab9721d/`，source/不可改；results/case_N为各唯一输出；logs/为Slurm日志。SSH使用既有lab-server-ai配置，不提交凭据。只从MANIFEST.status=completed以及RESULT_SUMMARY/EXECUTION/rawRESULT的SHA确认完成。

## 待办

1. 独立审计共同pipeline，完成新tests及原生ONNXim最小probe；需要升级/远程操作由root执行，子agent此前升级阻塞，未完成的构建不能写成已运行。
2. 收集31项完成数据、失败单列；`analyze_schedule.py`检查封存summary/config/version/rawSHA。原始大JSON/trace留个人远端项目，Git只小汇总/manifest。
3. 对比共同资源BF16/W8/SC、筛选PV/拒绝、2K/8K和有限tile/SG/阵列扫描，区分单seed资源试探与3seed主要概率结果。旧PR183结果明确其旧schedule版本。
4. 完成SCHEDULER_RESEARCH_ZH/MATURE_SCHEDULING_ZH，发布同一任务分支/PR，更新Issue/STATUS/memo。不要自动合并。看板缺read:project，待同步。

## 范围

合成事务和架构时延；无PPL/质量、GPU速度、新RTL/PT或完整芯片PPA。SC固定点GU restore仍有数值宏待验；价格为空不等于0。DRAMPower负ACT已知限制原值保留。#187广泛论文矩阵由rayggxia负责，本任务不改其目录。

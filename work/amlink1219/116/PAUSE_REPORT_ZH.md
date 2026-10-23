# Issue116 暂停总结与成果交接

**状态：paused。** 用户于2026-10-22 19:42 UTC要求提前暂停；目标已通过状态工具置为paused，未标记complete，不自动恢复。本轮此后只核验状态、整理既有证据和上传交接，没有继续实现或启动实验。原A–G方案尚未完成。

## 原方案A–G

| 阶段 | 暂停时状态 | 已有内容与验证证据 | 已知问题 / 未完成内容 |
|---|---|---|---|
| A 冻结参考 | **已完成本轮基线冻结** | base `46804fb3`；源码/配置/输入/SHA与运行源快照；43项旧回归通过，旧v6/random_service/历史正式结果在主分支差异中未改 | 这是本轮可复核基线，不代表并行PR已合并 |
| B 框架试验 | **部分完成** | ONNXim固定版本实际构建，2官方例+4自定义Operation场景通过；PyTorchSim固定版本 | PyTorchSim未构建；框架试验未接入本p-bit图的完整DRAM/NoC |
| C 最小周期核 | **部分完成；tile/query/GQA原型已验证** | 整数ps时钟、latency/II、old-state、有限资源/存储/回压、真实字节、动态native随机反馈；FFN W8主参考B4/T32/K32与对照；68真实裁剪例+8合成例；81实现/71独审测试；真实context64、7query/1KV组的5运行配置和6独审配置通过，42个head/2,688值逐bit一致 | 统一强格式schema、实际阵列供给/物理端口、全局地址容量/随机共享、真实DRAM/互连未闭合；不是已验收的周期精确芯片 |
| D RTL对照 | **部分完成** | 9协议RTL场景/252握手逐ps对应；PR122固定版本12场景/1,536恢复兼容复验 | 本任务未完成全算术链逐拍RTL/STA/PPA；并行PR的45组RTL/11,667输出是其已有证据，不重计为本轮新跑 |
| E 单层闭环 | **部分完成** | 缩小单头同Kernel层：7成功+2容量拒绝；真实算子片段和GQA组 | 真实全维完整层、在线摘要/筛选、多KV组、持续多token未完成。PR125完整FFN接合已公开，但其全维作业2783为CANCELLED/0:15，不能记通过 |
| F 全模型 | **未开始完整新后端运行** | 已写接口缺口与接续顺序；旧模型/PPL仅历史背景 | 未完成新后端Qwen/Llama全层首尾、2K/8K、多seed及PPL。新增2K合成候选在用户暂停时中止，仅建图完成，无执行/数学/轨迹通过结论 |
| G 校准优化 | **部分完成** | 8组FFN条件资源敏感性、动作/台账边界；公开ActiveMemory候选的64/128/256合成规模探针与独审兼容 | 仅模拟器CPU成本改善，不是硬件加速；物理PPA为null，同质量/同资源排名、完整资源因果关键链和旧新差异归因尚未完成 |

总体实现证据见[实施报告](../../../architecture_tlm/cycle_v1/IMPLEMENTATION_ZH.md)，逐条must及下一验收见[原方案覆盖表](PLAN_COVERAGE_ZH.md)，专门独审见[REVIEW](../../../architecture_tlm/cycle_v1/audit/REVIEW_ZH.md)。

## 主要已知问题与已修问题

- 首轮真实矩阵2775的6个有限预取死锁已修，失败原件保留；2776最终68+8通过。GQA的免费host union与无界operand响应两项P1已修，当前固定原型无独审遗留P0/P1。
- 32KiB权重信用是逻辑所有权，未证明额外阵列保持和宽供数的物理实现。默认host_order与rtl_fused0_order在次正规反例存在已记录的0x2/0x3差异。
- 原核pending/历史内存扫描超线性。公开PR125 `d944081a` 的ActiveMemory候选在N64/128/256分别约0.995/3.668/14.692秒，仍近二次；独审47个GQA场景×4路径=188次及动态hazard另4次全payload/state相等，另在候选上通过20个core测试。它依赖私有接口，**只作候选验证，没有替换默认Kernel**。
- 各mode数值/随机轨迹边界不同；native轨迹通过不证明IID/PPL，不从不同边界耗时推出speedup/PPA。

## 分支、提交及未提交范围

正式仓库 `rayggxia-workspace/pbit-llm-qwen-baselines`；认证 `amlink1219`（75301230）。

- 主目录：`E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/workspace_projects/cycle23`。
- 正式分支：`task/116-cycle-execution`；基线 `46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d`，PR base为`pbit-tlm-attention-details-20261016`。
- 暂停前已推送提交：`3347bd8a0a46ad2533298d680d8a6800ad9fa8d4`。基础科学发布`ddd2e340`、真实GQA固定生产源`f94c9db`/独审源`9f1122e`、候选source`d944081a`分别保留，不能用后续文档提交替换实验来源。
- [PR126](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/126)已推送、开放待审、未合并；本轮没有任何自动合并。收尾提交及远端逐对象/原始blob核验以`PUBLICATION.json`为准，通知链接见`PAUSE_NOTIFICATION.json`。
- PR119/120/122/125亦为待审，最终核验快照见`PAUSE_GITHUB_STATE.json`；其中PR125的最终head为`09dc2f90`，base为本任务分支。候选兼容验证仍只绑定此前公开的`d944081a`，不自动继承新提交；不能把公开代码或取消作业视作完整形状验收。
- 主目录没有未提交的生产代码修改。此前四组未跟踪诊断目录仍保留，其现有153项跨工作树诊断/初步回执已封存上传，未删除或重置。2K新脚本与暂停回执另已封存；原工作树仍保留草稿和合成输入。
- `cycle23-audit`有13项RTL文档/日志换行差异，`cycle23-ops`有1项旧REVIEW换行差异；逐字节比较确认全部仅CRLF/LF差异，未回写主树、未清理。各工作树的HEAD、分支、逐文件大小/SHA/未提交清单见`PAUSE_WORKTREE_INVENTORY.json`。重复源码提取目录、第三方构建包及私有fixture留在本地/个人服务器。

## 子智能体、进程和作业

| 对象 | 暂停核验状态 | 是否需要另行停止 |
|---|---|---|
| cycle_core | 已停止；需求覆盖报告已整合；未创建2K台账记录，无运行进程 | 否 |
| cycle_independent_audit | 已停止；兼容审查已提交；2K仅只读审运行器，无2K通过结论 | 否 |
| cycle_ops | 已停止；2K worker 290792、monitor 251584、launcher 274768已终止，root再次确认PID不存在 | 否 |
| 本任务服务器2759/2764/2772/2775/2776/2781/2782 | 均已终态；旧失败和最终成功分开留存；暂停时队列中无本任务作业 | 否 |
| 并行Issue123作业2783 | scontrol核实CANCELLED，ExitCode0:15，运行24分20秒；本任务没有取消它 | 否；不自动重交 |

暂停时`squeue -u Weican_Chen`为空（命令成功），证据在`PAUSE_QUEUE.json`、`PAUSE_PEER_JOB_2783.json`和`PAUSE_LOCAL_PROCESSES.json`。服务器未启用sacct，不能把查询失败当终态；旧任务依据运行时保存的scontrol终态和日志。5090可用，本轮未使用4090。

2K于19:41:44 UTC启动，用户暂停后约19:42:46 UTC停净。仅BUILT记录：1.349秒/32,818个初始操作；没有EXECUTED、ARCHIVED或SUMMARY成功门。终止码4294967295是本次用户中止，不是算术失败，也不是通过。`active_gqa_2k_paused/USER_PAUSE.json`明确automatic_resume=false。

## 成果位置与上传边界

- 正式代码/契约/报告/图：`architecture_tlm/cycle_v1/`；真实矩阵、GQA公开回执、缩小层、敏感性和独审均在其results/audit目录。
- 本次补充上传`pause_archives/`：完整v5矩阵归档、首轮v4失败归档、v1/v2/v3/v5源快照、153项历史本地诊断、暂停2K的确定性合成输入；每个压缩包及成员有SHA清单。初步/失败材料不计为额外最终通过。
- 2K草稿运行器、START/BUILT/停止回执、进程观察：`active_gqa_2k_paused/`。运行器为原路径依赖的档案副本，不能直接当恢复命令运行。
- 真实Qwen权重、原始私有GQA输入/输出和完整真实GQA轨迹继续留本人服务器`/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/`；Git有位置、配置和SHA。先前自动审批拒绝新私有激活下载，因此已在服务器完成验证，仅回传白名单结果；本次没有绕过该限制。
- Projects看板因缺read:project权限尚未同步，未更改权限。Issue/PR/HANDOFF/个人STATUS均记录paused；已授权通知仓库成员`@jieruiz`（169070146），不是无本仓库协作身份的同名`@Jierui`。

下一次恢复必须由用户明确发起。入口、优先次序及必要命令见[HANDOFF](HANDOFF.md)；本轮不会再启动实验或自动继续目标。

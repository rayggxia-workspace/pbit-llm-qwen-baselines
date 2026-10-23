# 接手 agent 的执行规则

这是 Issue151 的20层 P-DNN **推理评测**交接，不训练、不改采样或模型拓扑。先读同目录 `START_HERE_ZH.md`、`SERVER_RUN_ZH.md`、`RETURN_CHECKLIST_ZH.md`，再读包内根 `AGENTS.md`、`PROJECT_MEMORY_ZH.md` 相关章节、实验 README、checkpoint 清单、评分器和便携 runner。远端最新 Issue151、PR155、依赖 Issue145/PR149、成员 STATUS/HANDOFF 优先于旧快照。

- 使用接手者自己的、已核实的服务器及 GitHub 身份。根规则中 `amlink1219` 与 `/home/Weican_Chen` 是移交人的身份/历史路径，不要求也不授权你冒用。不得索取或使用移交人的凭据。先核实账号、canonical home、目标属主、symlink 和 Slurm；仅在接手者个人 home/已明确个人分配的存储内工作。本入口目前限定 canonical home，其他个人挂载需先单独适配并验证。
- 接续 Issue151，不新建重复 Issue；在原 Issue 记录“接手服务器执行”及自己的分工，不擅自改负责人或别人的 STATUS。独立 `task/151-<本人用户名>-server-eval` 分支/工作目录；个人进度和交接用 `progress/<本人GitHub用户名>/STATUS.md`、`work/<本人GitHub用户名>/151/`。如使用 GitHub CLI/API，首次只读核验实际账号、仓库权限和完整 push URL。
- 正式仓库仅 `rayggxia-workspace/pbit-llm-qwen-baselines`。PR155 尚未合并；包内版本以 BUNDLE_MANIFEST 为准，不把默认 main 当最新评测源码。源码解包目录是冻结快照，不在运行中修改；必要改动形成新提交和新快照/新 run。
- 所有安装、模型/数据准备、权重加载、机制测试及模型推理经 Slurm；CPU-only 明确 `CUDA_VISIBLE_DEVICES=''`。登录节点只做轻量检查、编辑、传输、提交、监控。不得直接用 ssh 后的可见 GPU 开算。环境仅装进自己的隔离环境，不改共享/系统环境。
- 先查 Issue151/145 和已记录 job ID，确认任务没有被另一 agent 接手运行；检查当前可用的配置服务器相关队列。本项目最多一个 pending/running GPU，接手账号已有 GPU 作业也先协调。队列查询失败不等于空队列。不得取消/改动别人的作业。
- 20份 checkpoint 必须通过固定大小/SHA、payload 类型/层号/训练步数/配置及严格 state_dict 检查；不改 expected SHA、不重保存文件冒充原版。若不匹配，记录实际清单，停在 CPU 门禁并联系移交人确认版本。
- 便携入口 `portable_runner.py` **重跑本机 BF16 三任务**，无需读取移交人 Issue145 私有路径；原 `runner.py`/`prepare.sbatch`/`evaluate.sbatch` 只作为历史入口，不能直接照抄到你的账号。保持 N4、seed0/1/2、任务数据/提示/选项/计分不变；不用 vLLM/lm_eval 普通批处理替换本随机评分流程。
- CPU strict preflight 全过后才允许 GPU；GPU 先 smoke 后完整12case。partial 不覆盖，不从任意题中途续算；完整 case 只有通过原件/SHA验证才跳过。失败保留原件，换新 run 或按文档恢复已完整 case，不能自动重提任务。
- `sbatch` 前记录 submission intent、目标 run 和命令；成功立即记录 job ID，遇超时先查 scheduler/job name/保存记录，不能重放提交。第一次看到终态立即保存 State、ExitCode、NodeList、AllocTRES 与日志。监控断线不等于作业终止。
- 执行中产生的结果manifest只散列已关闭的结果原件；Slurm stdout/stderr会继续写入，须在作业终态后另存最终大小/SHA，不能把汇总时的活动日志SHA宣称为最终SHA。
- 结果回传包含完整 per-doc 证据、汇总、代码/配置/模型/tokenizer/数据/harness SHA、环境、job终态和验证记录。权重、数据及大原件不入 Git，按项目约定存储并交付索引/SHA；通过自己的任务分支/PR，更新原 Issue 和自己 STATUS，有权限才改看板，不自动合并/关闭 Issue。
- 准备通过、真实 smoke 通过、部分 case、完整模型结果、已上传、待审、已合并分别记录；本任务不提供训练或硬件 PPA 结论。

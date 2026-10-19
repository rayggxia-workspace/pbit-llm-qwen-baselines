# Issue59：39项代表任务准确率已在Slurm运行

2026-10-19；负责人jieruiz；正式目标rayggxia-workspace/pbit-llm-qwen-baselines。

- 分支task/59-qwen-task-accuracy；PR62草稿、未合并，base task/50-joint-ffn-attention，依赖PR52；独立目录C:/Users/86134/Documents/a_P_BIT/tmp/qwen-task-accuracy-issue59-20261019。正式成果qwen/results/task_accuracy_20261019/，实现experiments/qwen_task_accuracy_20261019/。
- 选择PIQA1838、ARC-E2376全量，HellaSwag预先Random(20261019)抽1000题。官方lm_eval0.4.8零样本模板/边界及acc/字符长度acc_norm。B4T32 FFN固定，Ising64/128/512每档3seed，另BF16与FFN-only3seed，共39项。
- 当前3/39完成：新matched cached BF16 PIQA acc70.5114%/acc_norm69.9674%；ARC-E64.3939%/58.3333%；Hella子集41.9%/52.4%。36替换结果未齐，不能给采样准确率结论。不是历史native-vectorized分数搬用，子集不是完整Hella。
- 真0.5B GPU2476已重现完整WT2 BF1611.652735047455899；12最长prompt题独立naive cached参考逐候选总分最大差0.0、greedy一致；9项pilot完成，不当作正式任务。15CPU评分/计划检查、15汇总负面测试通过；评分CPU使用微型24层Qwen2夹具，不是全0.5B测试。
- 执行源码冻结075574ec94307202f3187845d6d7417f1e98ba48，不再修改；collector-only快照0d4be877714ace3f1b360c4d74b62e563850e9bc。原件/配置/数据/75项执行源Git blob或私有校准manifest已核验，公开索引/门禁在正式结果evidence/。
- Slurm2477三基线已全done；2478 ARC-E12项、2479 PIQA12项运行/排队；2480 Hella12项等资源；2481 afterany四数组自动CPU汇总。所有ID/命令见SLURM_WORKERS.json。sacct存储关闭，以squeue及completed封印原件确认，不用空sacct当结束。
- 服务器个人项目/home/Hongjie_Zeng/projects/pbit-qwen-task-accuracy-20261019-issue59；正式outputs/075574.../full含逐题jsonl，自动analysis/075574..._0d4be...。大原件留已授权服务器，Git只存摘要、SHA和索引。
- 旧2471包启动失败，2472依赖取消；348c828/2474因向量化和cache BF16形状差触发旧阈值，原件保留，新075574用独立cache参考严格验证后才启动正式任务。三任务均短于512，筛选保留allK，不能当长上下文筛选质量证明。首答案token及后续均真走24层decode替换；前缀Attention准确、FFN替换。
- 用户授权只取消本人未运行2430_19/20/21 B4T16冗余全量PPL，保留最佳B4T32。回执已提交。未训练/新PPA/修改Attention或FFN数值核。
- 下一步：先核实Issue59/PR62/最新本目录及本人队列；只读收集已封存full JSON+对应documents原件，按SHA核验。用collector --input下载目录 --execution-commit075574... --output SUMMARY.json --report RESULTS_ZH.md（命令参数之间需空格）；不得拼接进度冒充完整，至少三seed齐再下联合结论。继续更新PR62、Issue59及备忘录。
- 长期记忆本次补充在Issue28/PR64待审、未合并；根PROJECT_MEMORY同字节阅读副本已更新。Projects此前缺read:project，看板待同步，Issue/PR写入可用。

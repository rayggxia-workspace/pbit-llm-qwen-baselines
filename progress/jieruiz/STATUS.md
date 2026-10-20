# Issue50：25项完整WT2确认已回收核验，接续原PR52发布

2026-10-20；jieruiz；用户要求重审补全结果，Issue55审阅中只读接续Issue50现有原件。原2430保留19项、2461六项全部封存completed，2430_19/20/21三项B4T16联合按用户既有授权取消；未新跑模型或改快照。新独立报告qwen/results/joint_full_wt2_20261020/，含25原始结果、完整输入/源/取消与调度证据。

299077目标各一次/7300段NLL/25配置/24层审计与原件SHA通过；执行53dd/c0fd数值核一致，65核心CPU+4计划测试通过。B4T32联合S128/256/512完整PPL 12.423820/12.274153/12.207062，匹配cached BF16 11.652118；S256/512缺原FFN完整控制，交互不计算。原FFN仅S128三seed完整确认可供PR49有限引用。完整结果与旧4096后缀不混用，不使用自定质量阈值，不声称PPA。

当前阶段：原PR52仍draft，正追加本包与最新集成冲突解决，未把准备发布写成已合并。PR62的39任务已合入本任务base992c693；后续合并需独立原生回执。旧调度记录scontrol已过期、sacct实测storage disabled，完成依据为封存原件/逐目标审计，未伪造Slurm会计终态。Projects历史缺read:project仍待同步。恢复先核远端PR52/Issue50及Issue55第三轮回执，不重跑已收齐矩阵；本轮本地唯一稀疏审阅目录tmp/pr55-review-20261020，辅助资料归档后回收。

## 以下保留原任务交接及运行阶段快照，运行描述不作实时队列

# Issue59：39项Qwen任务评测已全部完成，完整报告已上传，PR待审

更新时间：2026-10-20；负责人：jieruiz；目标：rayggxia-workspace/pbit-llm-qwen-baselines。

- Issue59；分支task/59-qwen-task-accuracy；PR62，base task/50-joint-ffn-attention；依赖PR52。工作目录C:/Users/86134/Documents/a_P_BIT/tmp/qwen-task-accuracy-issue59-20261019。
- 服务器39/39均已封存、0待完成；当前没有本人的Slurm运行任务。Slurm2477/2478/2479/2480完成，2481自动汇总成功。PIQA1838、ARC-E2376、HellaSwag固定1000题；每任务BF16＋FFN-only三seed＋联合S64/128/512各三seed。
- 2026-10-20严格复核39项及逐题SHA，重建SUMMARY/RESULTS与服务器归档逐字节一致；原执行075574ec94307202f3187845d6d7417f1e98ba48及collector0d4be877714ace3f1b360c4d74b62e563850e9bc保持不变。没有新GPU推断、训练或PPA。
- 正式成果qwen/results/task_accuracy_20261019/：完整表、三seed波动、逐seed配对变化及原件SHA索引；大的逐题原件留原授权服务器。两份报告SHA：SUMMARY be47dd60a87dfb1467add4e22c6795e02df2a80867d0085d8f1a3b70cb1e61ac；RESULTS 7fc169344d0166f938580f32fb0ce03f0f5d34465bea5a74830ccdef4d0edbde。
- 局限：Hella不是完整10042题；短题K保留100%，前缀Attention准确，不能宣称长上下文筛选或完整prefill Attention已验证；Ising观测数不是ESS/电路拍。
- 当前发布阶段：完整报告已推送cebba22dadb78440b210b3ec237b5e2d16c77030；GitHub API核验16份结果/evidence字节与manifest相符，PR62说明及Issue59清单/进度已更新。PR仍draft、未合并，Issue保持open，不使用旧3/39或11/39代表当前状态。
- 长期记忆已同步并通过PR72提交待审（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/72）；下一步审查/合并PR52、PR62及PR72。看板查询实测返回INSUFFICIENT_SCOPES（缺read:project），Projects待有权限者同步；仓库报告上传不受影响。实际发布回执见work/jieruiz/59/FINAL_REMOTE_RECEIPT_20261020.json。

---

以下保留历史状态与交接，不作为当前状态：

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

## 2026-10-19 17:51北京时间实时更新

已完成11/39、28项运行/排队，无worker traceback。首次联合结果ARC-E S64 seed0完整2376题：acc63.4680%、acc_norm58.4175%，参考64.3939%/58.3333%，仅一seed不作三seed质量结论。耗时1084.16s；FFN-only ARC-E三个seed已齐，原件按SHA与严格collector验证。

按真实decode前向工作量和当前每task两个并行槽估时：ARC-E S64三seed约18:05～18:15；PIQA/Hella首个联合seed约18:20～18:40；三个任务S64各三seed约19:00～19:20；全部S64/128/512各三seed约21:00～22:00。均为2026-10-19北京时间的动态估计，不是Slurm保证。按ctx长度分组、候选最长长度决定batch步数，不能用题数百分比简单外推。未调整作业/并行数/随机源，输入与快照不变。RUNTIME/DECODE_WORK为本次原始状态快照。

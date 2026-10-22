# Issue98 交接：统一LLM benchmark与PPA调研

2026-10-22；实际连接器账号rayggxia；正式仓库rayggxia-workspace/pbit-llm-qwen-baselines。
分支task/98-benchmark-protocol，基线/PR base pbit-tlm-attention-details-20261016@83e15289434af50fc09c35e699d8b39965389d98。
工作目录C:/Users/86134/Documents/a_P_BIT/tmp/benchmark-protocol-issue98-20261022；使用--no-checkout后最小sparse-checkout，未复制模型/结果轨迹或安装环境。

已完成：16篇代表文献与官方评测代码重新核查；中文综合报告、JSON/CSV文献矩阵、不可直接运行的协议提议。报告将原文事实、既有项目结果和本项目建议区分。5%等质量档位未获用户正式接受；无新质量/PPA数字。未披露不等于未建模。

验证命令：
```powershell
& 'C:\Users\86134\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' work/rayggxia/98/verify.py
```

33项检查通过：JSON/CSV、16/11计数、字段与null语义、内部相对链接在冻结Git树中存在、SANTA与PPL例子复算、Qwen39/Llama26最终证据入口、用户MBA PDF/历史GPU报告/旧14篇样本SHA、UTF-8/LF。详细值及四份正式文档hash见VALIDATION.json。不是模型复现/EDA或外部URL全面探活测试。
小型校验脚本对本机历史来源做只读hash，异机复验需取得该来源原件；不得用重新下载的不同版本静默替换。

实验清单不适用：本轮未运行模型、训练、服务器、Slurm、GPU、TLM或EDA；新运行模型/数据revision、种子、精度、运行环境/完整推理命令均不适用。提议JSON中待冻结字段保留null。旧实验仅按已验证manifest索引，不重复推理。

发布：以PUBLICATION.json和远端PR为准；本交接创建时本地完成待发布。Issue保持open直至PR审核验收；不把创建PR写为合并。Projects权限/看板同步未核实，待同步。没有给其他任务发送消息。

并发边界：Issue37/78/95/96仅只读；95的PR97已开放。本研究不改系统实现、活动默认、随机源或实验输入。个人STATUS只写rayggxia。后续若97先合并导致STATUS冲突，保留两项任务状态按最新远端刷新，不覆盖95成果。

长期备忘录：根阅读副本与唯一维护目录tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md当前同SHA256=020c97a7108134e645d46eb2cb6881edb28d48bf09007cf82823f6bcca588b52；维护目录为task/28-project-memory@a71e4bc且已有未提交修改。遵守不覆盖其他任务未提交状态，本轮没有另建完整备忘录编辑版本。待唯一维护任务/集成验收追加：
> 2026-10-22 Issue98：统一benchmark/LLM质量/PPA研究入口architecture_tlm/benchmark_protocol_20261022/README_ZH.md；16项代表工作、官方lm-eval0.4.8与MLPerf5.1定义核查、结构化比较和提议协议。SANTA的全batch ms/token与请求TPOT分开；acc_norm默认字符长度；质量/PPA每点同配置；未知成本null。没有新模型/Slurm/TLM/EDA；1/3/5%预算为提议，非会议规则或用户批准。发布/验收以PR和PUBLICATION为准，Issue95/96实现不接管。

成果文件只提交本任务路径及个人STATUS；不上传用户PDF、GPU原始测量包、私有工艺库、权重/语料或凭据。
原始用户PDF维持原字节，来源hash在PAPERS.json/VALIDATION.json。远端读回将逐文件SHA比较。

恢复/回收：同任务复用当前小工作树；PR待审仅保留这些文档与校验记录。没有额外helper、波形、大型下载或本轮实验日志需要搬移。合并后按规则核对refs/未跟踪状态再回收；不要按日期清理其他目录。

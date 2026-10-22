# 安装与验证失败及恢复记录

2026-10-22，Issue90。两台环境的CPU19项和GPU6项均已验证；下表保留各次失败及其独立恢复结果，PR审阅与服务器完成分别记录。服务器使用“备用一/备用二”代号；连接身份、网络地址和本机资料不在发布范围。

| 作业 | 已观察事实 | 原因及处理边界 | 独立恢复验证与边界 |
|---|---|---|---|
| 备用一9038、备用二14099 | CPU安装在官方Python发布文件下载阶段失败 | GitHub发布文件访问超时。改用独立核对官方SHA的同一文件传入个人目录，保留安装源码 | 目标Python文件SHA已核，后续14101/9041及GPU分别通过 |
| 备用一9039 | 本任务CPU安装持续慢下载，取消后`CANCELLED / 0:15` | 只取消已核对的本任务安装作业，随后复用备用二个人pip缓存导出的LLM层wheel；不干预其他任务 | 14105导出与传输SHA已核，9041闭包及固定Torch元数据通过 |
| 备用二14100 | 包安装、pip check通过，原CPU检查在sklearn导入处失败，作业`FAILED / 1:0` | 旧glibc的static TLS加载问题。原导入顺序不改，追加个人环境的进程预载wrapper | 同样CPU检查在每台实际进程入口中通过，不据pip check推断import可用 |
| 备用二14101 | `COMPLETED / 0:0`，原CPU检查19项通过，wrapper/预载库SHA和线程池已记录 | `llm-python`预载本环境sklearn wheel的唯一libgomp，线程来自Slurm分配；系统/共享环境未改 | 备用一9041独立通过，9042/14104再分别验GPU，不从CPU结果推断 |
| 备用二14102 | `FAILED / 1:0`；单卡CUDA/BF16与因果SDPA通过，tiny模型重载logits对比失败 | 原模型FP32创建后转BF16，重载重新生成FP32非持久RoPE buffer，测试两边初始化路径不一致；原阈值未满足 | 14104/9042采用v2同BF16初始化与严格state门禁，原阈值及FFN checks均通过 |
| 备用二14103 | CPU导出器拒绝安装报告中来自额外官方PyTorch域名的包，作业失败 | 初版允许来源只列PyPI域名，安全拒绝了`download.pytorch.org`供应的colorama；原失败保留，另建v2列明两个官方HTTPS域名 | 14105的v2分发、导出/传输SHA已核；来源域名和hash限制保留 |
| 备用二14104 | `COMPLETED / 0:0`，v2 synthetic GPU smoke的6项通过 | 原阈值不变，先核27参数/3buffer逐位一致；logits最大误差0.0；FFN K32/K4小输入均通过 | 随后备用一9041/9042独立通过且freeze一致；此结果不建立真实模型质量或跨GPU数值等价 |
| 备用二14105 | `COMPLETED / 0:0`，v2源端导出70wheel，归档164065280 bytes | 仅两个明确官方HTTPS域名，记录源包SHA和纯Python构建wheelSHA；归档SHA为`1c999138495f92b9e7c5fd2e69a79a6cfcb09b0103f6e025a8f7c110aa27b9aa` | 接收端9041分别核传输、固定Torch、offline闭包和CPU，9042再核GPU |
| 备用一9040 | `FAILED / 1:0`，最前置路径检查报`Path.is_relative_to`不存在，没有安装结果JSON | sbatch误选共享旧Python，Python源尚未开始安装。保留旧launcher和失败，新v2仅改为调用已验证的个人Python3.12 | 用同一已验证解释器做预检和实际执行；本地另一Python版本的语法检查不证明共享旧runtime能力，由9041/9042分别完成CPU/GPU复验 |
| 备用一9041 | `COMPLETED / 0:0`，offline闭包/70wheel、pip check、原CPU19项和进程compat均通过 | v2用个人Python3.12执行不变的安装源；Torch元数据前后相同、无CUDA初始化 | 随后9042的6项GPU独立通过、exact freeze已收齐；CPU/GPU环境通过不等于完整质量/性能验证 |

14102的因果SDPA `relative_rmse=0.0017545506125316024`、`max_abs_error=0.005356907844543457`，在该项既定阈值内。后续tiny模型对比为539/2048项超出 `rtol=atol=0.001`，最大绝对差0.00390625。这里只描述各项发生位置，不把部分通过等同于完整GPU环境可用。

v2是单独的测试修正阶段，原gpu_smoke.py、原14102日志/报告和新源码各自hash均保留。相同权重不足以证明两边计算相同，尤其非持久buffer不随state_dict保存；先核对实际实例的参数、buffer dtype/值与设备，再比较输出，不能通过放宽输出阈值掩盖初始化差异。14104中两侧3个RoPE buffer均为FP32，27参数和3buffer逐位匹配后logits差为0.0；这是测试初始化路径修正后的实测，没有给原失败改判。该已证实教训已加入本任务根 `AGENTS.md` 的reproducibility规则，未修改全局规则或记忆。

离线恢复的wheelhouse仅包含原LLM安装阶段，不包括Torch、CUDA、Triton底座。官方PyPI wheel按pip报告来源SHA核验；rouge-score/sqlitedict/word2number从匹配原source archive SHA和origin metadata的纯Python构建wheel取出，构建hash单独标注。接收端须已有匹配Torch底座，并先以`pip install --dry-run --no-index --find-links ...`证明所需闭包；此后实际安装也不访问索引。

9040没有生成应用报告，缺少该JSON是实际执行尚未进入安装阶段的结果，不能替造报告或据缺少结果推断没有作业。调度终态与原stderr共同保留。v2只更正Slurm launcher的解释器路径，实际安装Python源hash不变；不修改共享Python或用运行时升级系统的方式修复。此处仅记录已确认原因，不另加全局或第二条项目规则。

脱敏公开摘要与原始采集快照是不同对象；最终exact报告核验见RESULT_MANIFEST.json。[EXECUTION_HISTORY.json](../../work/amlink1219/90/EXECUTION_HISTORY.json) 只提取必要检查、状态和误差字段，并记录未发布的原始本地采集快照SHA。那些快照包含调度器输出及解析后的应用报告，并非服务器子报告原字节；最终交付已独立核验13份exact报告/日志/冻结原件，见RESULT_MANIFEST.json；传输manifest及接收端offline9041亦完成核验。不得将派生摘要hash当作服务器报告hash。

最终备用一9042为COMPLETED/0:0，6项GPU通过，27参数/3buffer逐位相同且logits重载误差0.0。两台94包freeze完全同字节，完整版本和13份私有原件hash经独立收集核验；exact freeze和脱敏派生报告已进入本交付。所有原失败保留，原执行源未覆盖。

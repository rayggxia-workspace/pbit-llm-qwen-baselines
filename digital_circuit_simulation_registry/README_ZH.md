# 数字电路仿真统一台账

从 [00_总览.md](00_总览.md) 查看哪些模块已仿真，从 [01_结果地址索引.md](01_结果地址索引.md) 打开具体结果文件；[02_覆盖与待补.md](02_覆盖与待补.md) 说明哪些成本仍不能直接用于当前架构。

本目录集中登记LLM的随机矩阵、随机源服务、SRAM、转换、非线性和控制等数字模块，也交叉索引共用的数字p-bit芯片。**只收索引、必要数值和SHA-256，不重复保存波形、网表、工艺库或模型。** Issue110初建时为已有结果整理；后续新增仿真按独立记录登记，不能沿用“没有新仿真”的历史范围。

Issue116新增 `cycle-116-protocol-rtl`（9组有限流水/FIFO/跨域握手对照、252个事件逐ps相等，仅RTL功能）和 `cycle-116-conditional-model`（68真实片段、8smoke、8条件敏感性案例，仅明示假设下的周期模型）；没有综合/STA/PPA。与PR119、PR120、PR122、PR125的并行登记互不替代，集成时应合并各自独立record后重建总览，避免用任一分支的catalog覆盖其他新增记录。

Issue116的GQA增量单独登记为 [`cycle-116-gqa-conditional-model`](records/cycle-116-gqa-conditional-model.json)：真实Qwen第12层、context64、7查询头共享1个KV头，5个S32配置案例；6个S16独审配置及42个配置/查询头对照仅列为验证证据，不增加案例计数。原有84例条件模型记录保持不变。周期来自明示参数的模型，面积/功率/能量均未知，不是完整模型或实测硬件结果。

| 先找哪一类 | 当前证据 |
|---|---|
| 随机矩阵、OR、缓存、CSA | 3个完整历史批次、72组配置/活动结果；保留负结果和旧失败批 |
| 随机源架构 | 最新4核心×3频率；216门级用例、252个PT窗口；100MHz已报告时序通过，高频部分失败 |
| SRAM权重存储 | SS下DFF/SRAM主模块对照与S0–S5状态标定已有PT；时序/X审查限制保留 |
| SRAM不同尺寸 | 14组SS/TT库提取、42个负载代表点；与PT和CACTI预测分开 |
| SwiGLU后处理 | TT/SS各18场景，功耗/面积已有；Q10单通道 |
| 转换、短流、新非随机算术/控制 | 已有功能验证，目标工艺PPA仍待测 |

阶段用语：`pass`功能通过，`completed`综合完成，`reported_nonnegative`已报告slack非负，`violations`有时序违例，`calculated`已算出功耗，`partial`只完成部分，`not_run`未执行。它们分别记录，不能互相替代。

正式版本为 workspace 仓库中的同名目录，当前任务 Issue110；本机固定阅读入口是 `C:/Users/86134/Documents/a_P_BIT/digital_circuit_simulation_registry/`。本机入口是同字节阅读副本，不是第二套独立编辑版本。任务分支/PR状态见 `work/jieruiz/110/HANDOFF.md`；PR合并后从集成分支维护。

| 文件 | 用途 |
|---|---|
| `00_总览.md` / `runs.csv` | 一眼看出功能、综合、STA、功耗分别完成到哪一步 |
| `01_结果地址索引.md` / `artifact_locations.csv` | 每项对应的绝对路径、归档成员、原字节SHA-256 |
| `records/*.json` | 每批/每模块的版本、条件、边界、限制及逐case数值；是登记内容的主数据 |
| `archive_inventory.csv` | 原始数字结果归档的发现清单；`discovered_not_audited`不能当作已通过 |
| `02_覆盖与待补.md` | 新旧模块对应、失败历史、成本缺口和禁止混用 |
| `templates/record.template.json` | 新增仿真的登记模板 |
| `registry.py` | 无第三方依赖的录入、汇总、原件/归档成员SHA检查 |

每次新增仿真，执行以下登记流程：

1. 先查台账、最新Issue、原负责人交接，避免重跑已有健康任务。提交前也可建立新run记录，阶段写`not_run`，数值留空。
2. 在正式任务checkout内复制模板，填写唯一run ID、模块/参数、**执行**源码SHA或源manifest、工艺/PVT/频率/负载/激励/seed/窗口、结果原件和SHA、各阶段状态。没有Git提交的旧实验用manifest绑定；不编造SHA。
3. 收到结果后读实际日志/报表，分别核对功能、综合、STA、PT与后布局。功耗算出但有时序违例，必须同时保留；新run不能覆盖旧失败run。同一次仿真的多个副本/重汇总不算新实验。
4. 运行录入与检查，更新总表、Issue/STATUS/HANDOFF，并通过该任务PR交付。新增原始压缩包也追加`archive_inventory.csv`的路径、字节和SHA；维护分支尚未合并时引用它，不能另建分散台账。

```sh
python digital_circuit_simulation_registry/registry.py add /path/to/new-run.json
python digital_circuit_simulation_registry/registry.py check
python digital_circuit_simulation_registry/registry.py check --local --members
python digital_circuit_simulation_registry/registry.py render
```

`check`在其他电脑也能校验格式、阶段门槛和索引一致性；`--local`核对当前可访问原件的大小/SHA；`--members`还核对已登记tar成员。找不到本机路径时输出`unavailable_here`，不伪称完成原件校验。出现哈希变化会失败，不能用改登记SHA掩盖历史结果被覆盖。Markdown/CSV由记录生成，修改记录后必须重新render。

原件在临时工作目录时，应先按项目存储规则归档，再登记新位置/归档成员和SHA；保留原位置历史。清理checkout前更新台账，不能留下唯一指向已删除目录的地址。本轮没有搬移或删除任何原始结果。

功耗面积单位及边界：标准单元面积、SRAM宏面积、物理核心面积分开；总功耗已含时钟引脚内部功耗时不重复加clock分组；每帧/每结果/每生成字/每消费帧分别计量。`not_run`/`null`表示未知，不表示零。库提取、功能验证、PT、TLM估计和芯片实测不可互相替代。

Issue95分层随机质量189案例已通过PR134发布（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/134，待审未合并），run `rng-quality-95-20261023` 为DESIGN_PROOF，不能当作新RTL/PPA或熵认证；其他并行记录保持。

Issue152长记录准备脚本见[PR156](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/156)，physical-rng-long-152-prepared仅记录脚本准备，实际Spectre未运行。第九轮合并回执与50条记录核验见work/jieruiz/55/round9/REVIEW_ZH.md及Issue55。

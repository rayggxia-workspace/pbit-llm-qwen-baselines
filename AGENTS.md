# Project memory and resuming work

- Before starting or resuming any LLM task, read the repository-root `PROJECT_MEMORY_ZH.md`, especially sections 0, 1, 12 and the section for the current subsystem; then check the latest remote Issue/PR, `progress/<verified-GitHub-login>/STATUS.md` and task HANDOFF. The memo is a navigation and decision record, not a replacement for current evidence or repository rules.
- Preserve user decisions, negative results, evaluation protocols and unresolved limitations. Update the memo when a major result, design decision, handoff, publication or merge changes the project state. Distinguish physical IID randomness, PRNG/stratified sequences, approximate numerical references, RTL/PT and macro TLM estimates.
- Keep a same-byte reading copy at the local `a_P_BIT/PROJECT_MEMORY_ZH.md` when working in that workspace. Do not rely on chat history or claim inaccessible future conversations automatically remember the project. If the file cannot be read, report the missing project context before repeating expensive experiments.
- This section implements the user's 2026-10-18 request for durable cross-session project memory, Issue #28. All existing reproducibility and collaboration rules below remain in force.

# Experiment reproducibility

- Before comparing a new coding or architecture against recorded results, verify model revision and train/test text SHA-256, then rerun the unchanged BF16 reference in the experiment environment.
- Salesforce/WikiText parquet represents whitespace-only raw lines as empty strings. To reproduce this repository's `wiki.train.raw` and `wiki.test.raw`, restore each empty row as `" \n"` (one space followed by LF), concatenate rows without an additional separator, and require the recorded corpus hashes. Do not assume ordinary newline joining recreates the raw corpus.
- Keep `bipolar` as the default for older full-path checkpoints without a `coding` field. Both encodings must keep every matrix input binary on sampled paths and average only after the final readout. Run `experiments/pdnn_ffn/test_full_path_coding.py` after changing these boundaries.

- Generate new text manifests with explicit UTF-8 and LF before hashing or transfer. Once a server manifest records a checksum, preserve those exact artifact bytes in Git; use `-text` attributes for archived originals when necessary rather than silently normalizing recorded CRLF. Verify committed blob bytes against the manifest before publishing.

- Server-side tests must create temporary checkpoints under the verified personal project directory (pass an explicit `dir` to `TemporaryDirectory`); do not rely on the shared host's default temporary directory. Keep execution snapshots immutable after submitting a job and record later test-only fixes separately.

- For model save/reload validation, initialize both instances with matching parameter and nonpersistent-buffer precision before comparing outputs. Keep Qwen RoPE buffers explicitly FP32; do not compare a blanket `model.to(dtype=...)` instance with `from_pretrained(torch_dtype=...)` without checking those buffers. Require matching parameter/buffer keys, shapes, dtypes, devices and values before the logits comparison, and preserve the original logits tolerance rather than relaxing it to hide initialization differences.

## Workspace collaboration rules（2026-10-16）

本规则适用于本仓库及其 LLM 实验、RTL、TLM、文档和发布任务。执行用户明确授权的任务时，持续完成修改、适当验证、任务分支上传、PR 和进度同步；遇到权限、环境、数据阻塞，应完成不受影响的部分并如实记录待办，不把本地完成写成远端已完成。

### 1. 核实项目和身份

- 正式目标仓库为 `rayggxia-workspace/pbit-llm-qwen-baselines`。`jieruiz/pbit-llm-qwen-baselines` 为历史个人仓库，不能因为 remote 名为 `origin` 就默认向其推送。
- 每次开始或恢复工作，先确认实际 Git 根目录、分支、工作树改动、远端 URL、远端最新提交与实际 GitHub 登录用户名。`git config user.name` 只是提交作者配置，不能代替登录身份核实。
- 核实项目资料：远端最新 `README.md`、`AGENTS.md`、任务所处分支的协作说明和状态索引。默认分支未必包含最新实验；阅读相关任务分支及有时间标记的交接记录，不把旧首页当成完整状态。
- 保留既有项目规则及子目录规则；更新规则时说明来源和适用范围，不覆盖历史实验的复现约束。

### 2. 一项任务对应一个 Issue

- 开工前检索最新 Issue、关联 PR、`progress/*/STATUS.md` 和交接记录，确认其他成员负责人、正在修改的范围和已完成内容，避免重复开工。中断恢复或准备发布时再次检查远端变化。
- 已有同范围 Issue 时接续原 Issue，不重复创建；新任务先建立 Issue，明确负责人（GitHub 用户名/assignee）、范围、非目标、依赖和可检查的验收标准。不可独立验收的步骤作为同一任务清单。
- 发现范围重叠时先在 Issue 记录分工与接口，不覆盖他人文件或擅自接管任务。其他成员的旧结果和评审作为有版本的证据保留。

### 3. 独立分支和工作目录

- 每项任务使用独立分支，例如 `collab/issue-1-governance` 或 `task/<Issue编号>-<简短名称>`；在 Issue 中记录基线提交和目标 PR base。
- 并行 Codex/成员必须使用独立 checkout 或 Git worktree，并记录路径和分支；不得在同一工作目录切分支、共用未提交状态或覆盖他人的改动。
- 不重置、清理、强制推送、删除或搬移其他成员的工作树/分支。依赖任务尚未合入时明确依赖分支和提交，不为方便把无关实验混入本任务 PR。

### 4. 文件位置和个人进度

- 个人进度统一维护在 `progress/<本人GitHub用户名>/STATUS.md`，用户名使用核验后的登录名，不用组织名或代操人的账号代替。其他成员的 STATUS 只读，除非获得明确授权。
- STATUS 至少记录：更新时间、负责人、Issue、分支/PR/base、工作目录、当前阶段、实际验证、成果位置、阻塞/待同步以及下一步可执行动作。区分“本地已完成”“已推送”“PR待审”“已合并”“远端任务已完成”。
- 任务辅助资料放在 `work/<本人GitHub用户名>/<Issue编号>/`，例如核实记录、命令日志、manifest、验证和交接；正式代码、文档和结果仍遵循 `baselines/`、`experiments/`、`architecture_tlm/`、`results/` 及任务已有正式目录，不把正式实现藏进个人工作目录。

### 5. 验证和 PR 交付

- 上传前再次核对 GitHub 身份、目标仓库、任务分支、PR base、提交差异和文件清单。只按明确文件范围提交，不在混合实验/工艺资料工作区执行无范围的 `git add .`。
- 通过任务分支和 PR 交付，关联 Issue，说明问题、最终改动、实际验证命令及结果、未运行项和限制；不把历史测试、参数估计、合成输入当成本次真实模型或芯片验证。不得将“PR已创建”写成“已合并”。
- 在已有用户授权内完成修改、验证、上传和状态同步，无需重复询问已授权的常规步骤；超出授权、缺少权限或不能验证时清楚标记阻塞。
- 更新 Issue 的阶段、验收清单、PR 和结果链接，并同步有权限操作的项目看板。看板无访问/写权限时在 Issue、STATUS 和交接里写明待同步项，不虚报成功，不以权限不足替代其余可完成工作。
- PR 合并/验收后再标记任务完成；暂停、PR待审或换人不自动关闭 Issue。遵守仓库已有保护、审查和合并规则。

### 6. 数据、实验结果和大文件

- 实验记录必须包含代码仓库与准确提交 SHA（以及未提交补丁，如有）、配置及其 SHA-256、模型/分词器/数据版本与 SHA-256、种子、精度/编码、采样数、环境、完整命令、计分协议、成果位置及文件 SHA-256。文档任务中不适用的字段写明原因。
- 区分完整 WT2 滑窗 PPL、固定文本后缀 PPL、合成事务输入、TLM 参数估计、RTL 功能验证、DC/PT/工艺数据和硬件实测；不同版本或评估协议不能直接混称。比较新结构时遵守上方原有 BF16 和文本哈希规则。
- 大权重、数据集、长事务轨迹及大型原始仿真产物使用项目已约定的共享存储，Git 只提交索引/manifest、必要的小型可复现配置和汇总；索引说明版本、位置、访问要求、大小及 SHA-256。未约定位置时先保留现有授权存储并记录待确定，不擅自公开上传。
- 不上传凭据、SSH配置、token、工艺库本体或受限制资料。散列原始归档字节，不为了美化或换行重写已签校验和的结果。

### 7. 暂停和换人交接

- 在 `work/<本人GitHub用户名>/<Issue编号>/HANDOFF.md` 和个人 STATUS 留下：已完成/未完成、远端与本地状态、精确分支/提交、变更文件、执行命令、配置/数据/成果及哈希、验证结果、运行中任务ID/环境、阻塞和下一步操作。
- 交接必须能让接手者按步骤继续执行；明确哪些文件尚未提交/上传、哪些结果只存在远端、哪些权限需补齐。恢复时先重读最新 Issue/PR 和交接，不能仅依赖旧聊天记录。

### 8. 规则来源与实验入口

- 上方原有英文复现规则完整保留自 workspace 分支 `codex/ten-layer-calibration` 的 `AGENTS.md`（本次读取版本 `595c3ab44be27799878353395d30645df0441983`）。本节来自用户 2026-10-16 的 workspace 协作要求。
- 继续遵守 README 的同模型、分词器、语料、精度、window/stride、种子对照要求；随机方案记录采样数并至少报告三个独立种子。
- 既有 P-DNN 层原理及后续变更继续维护 `experiments/pdnn_ffn/P_DNN_FFN_DESIGN_ZH.md`，不是被个人 STATUS 替代。
- 当前 TLM 已发布入口位于分支 `pbit-tlm-attention-details-20261016` 的 `architecture_tlm/WORKSPACE_LATEST_ZH.md`；该分支未自动合入 main。阅读版本与限制后再接续，不将宏级模型结果宣称为实测芯片性能。

## Server snapshot preflight

- When staging a minimal server snapshot, include test fixtures and imported data/configuration files in its source manifest. Run tests from the extracted snapshot rather than only from a full checkout, and pass a CPU Slurm preflight before allocating a GPU; preserve failed snapshots and job identities.

## amlink1219 hardware-design workspace（2026-10-18）

- 本节补充用户在本机的硬件架构设计协作要求，上方原复现及协作规则完整保留。只约束本用户的操作身份，不改变其他成员的身份或任务所有权。
- 本人的 GitHub 登录名为 `amlink1219`，ID `75301230`；首次使用认证渠道及切换凭据后核实 `/user`，发布前核对目标权限和所有解析后的 push URL。目标仅为 `rayggxia-workspace/pbit-llm-qwen-baselines`；不使用身份不符的连接器，不回退旧上游。
- 个人进度为 `progress/amlink1219/STATUS.md`，辅助资料及可执行交接为 `work/amlink1219/<Issue编号>/`。2026-10-18的本机规范落地是既有 Issue #1 的子项，负责人 `amlink1219`；Issue #1 原负责人仍为 `jieruiz`，未接管其 PR #2。实际硬件实现的新范围另建或接续对应 Issue。
- 继续执行一任务一 Issue/分支、独立并行目录、开工/恢复/发布前检查 Issue/PR/成员 STATUS/HANDOFF、明确验收、限定文件范围、实际验证、任务 PR 交付和有权限的看板同步。缺少权限仍完成可执行部分，并记录尚未上传或同步的内容。
- 恢复硬件设计前，先读根 `PROJECT_MEMORY_ZH.md` 第 0、1、12 节及对应子系统。若 PR #29 尚未合并，用 `git fetch origin` 后 `git show origin/task/28-project-memory:PROJECT_MEMORY_ZH.md` 读取待审版本并注明来源，不把它当成已集成代码。随后重新核对 Issue #19、#22、#30 等实际状态。
- 当前主要集成分支为 `pbit-tlm-attention-details-20261016`，不是默认 main；此为截至 2026-10-18 的导航，恢复时重新确认。其他成员拥有的 Issue #19/22/30 及既有评审分支只读，不重复启动或覆盖其运行快照。
- 硬件目标围绕质量、能量、面积和延迟一起决策；同一数制和质量目标下比较确定性低位/位串行与随机计算。输入侧/双侧随机、自然 IID/PRNG/分层/枚举、原生 p-bit/数字随机字、数值参考/RTL/PT/TLM 分开记录。SRAM、权重/KV、随机源/分发、计数累加、非线性、格式转换和接口均计费。
- `work/amlink1219/1/REMOTE_SNAPSHOT.json`保存的是2026-10-18身份和权限时点快照，不代表当前权限。开始、恢复和发布前重新核实；权限不足时如实记录未上传或待同步项，不换账号或擅自修改权限。

## Attention 架构验收口径（用户 2026-10-19 指定）

- 概率 Attention 的主目标是降低面积、能量与延迟；允许有限质量损失。以同模型、同语料协议下完整模型 PPL 增量约束比较完整数字 Attention 与概率方案的 PPA；尚未约定具体 PPL 预算时报告质量与成本曲线，不擅自写成用户已接受某个阈值。局部 TV/NMSE、采样独立性用于诊断，不能代替完整模型验收或单独决定架构优劣。
- 数字对照须有可追溯实现依据，包含分块在线/融合 Softmax、GQA 的 K/V 复用，并区分 QK/Softmax/PV 核心与含 QKV、RoPE、KV 追加、Wo 的完整 Attention。注明归一化、残差、FFN、lm_head 的边界；不强制数字方案物化完整概率矩阵。
- 面积/能量/延迟比较必须使用明确数制、资源共享、驻留容量和数据流；把假设的资源速率下界、宏表局部成本、同工艺综合、功率分析与芯片实测分开。FP32 概率乘 V 不得按纯 BF16 MAC 免费计费；SRAM fabric 若为读写合计，DMA 写入和计算读出须各计一次。缺失项保持未完成，不用旧占位系数补成完整 PPA。
- 比较已保存的 Attention 汇总前，核对 decode token 数、首 token/均值、摘要 cold-build/prefill-prebuilt/增量更新和完整模块边界；旧 v3 两 token 均值与 v4 单个冷 token 不能直接作为同协议加速/节能比。候选保留率、GQA 并集、物理突发字节、DMA 请求数与 SRAM 峰值分别记录，不按逐头保留率缩放访存或按较低平均功率判定省能。

## Decode Attention quality execution

- A decode-only Attention patch must not be evaluated by an unchanged multi-token window call and reported as candidate PPL: audit that every scored target executes every replaced layer through the single-token path. Preserve matched cached SDPA controls, exact target coverage, prefill scope, candidate-valid masks, original FFN/weights, and separate suffix/full-corpus protocols.

- Integration-equivalence gates must use matching operators, dtypes and layouts. For Attention, compare the wrapper with the original BF16 SDPA core before using an explicit FP32 reference as a separate quality control; record its numerical difference instead of imposing or silently relaxing an identity threshold. All pilot comparison cases must use the same scored token set.

- In sample-count sweeps, a shared seed or single-call prefix test does not establish shared sampler draws across a whole model run. State which RNG streams are independent, whether draw consumption changes with S, and the exact logits/RNG/batch conditions under which pairing holds; candidate masks may change with downstream hidden states.

## Historical Attention quality evidence

- Before declaring model-level Attention PPL evidence absent, inspect the historical algorithm branches and the executable dispatch, rather than only the current TLM integration tree or a mode name. Record all-layer coverage, prefill/decode coverage, suffix versus full-corpus scoring, FFN state, and whether sampling is accurate-Softmax IID, ideal CTMC, or a finite physical/network model. A separate screening result and Ising result do not establish their joint PPL. Before claiming that an energy sampler removes an existing digital Softmax, trace the active behavioral dispatch separately from the TLM address oracle; distinguish exact-score categorical Gibbs, learned energy, and independent or coupled multi-on masks.

## amlink1219 后续FFN仿真参考（用户2026-10-19指定）

- 后续本人的FFN行为/数值仿真主参考采用PR47已合并的固定W8＋多档幅度＋随机门限分层：B4/T32/K32，显式传policy=pot4、mode=sampled、cycles=32、strata=32，不沿用原类的128/1默认。采用版本、SHA、工厂和方法边界见architecture_tlm/ffn_stratified_reference/。B2/T32/K32、B4/T16/K16、B4/T64/K64作为简化、短流、低误差对照。
- B是幅度尺度档数、K是0..255门限区间数、T是每投影阶段总采样数；保持共享64路及跨档共享门限、gate/up共享x抽样、z独立重编码、固定W8、符号/满幅旁路和FP32 SiLU/归约，不能替成各通道独立Binomial、自然IID或双侧随机。
- Attention-only继续保留原FFN控制；联合仿真显式声明分层FFN在prefill/decode均替换，复用准确版本的双路径Guard/计分审计。FFN的T/K与Ising的burn/spacing/S分别记录，不把分层门限直接当Ising去相关方法。
- 本次采用是行为参考，不是已验收的RTL/PPA默认。T32包含x与z各一帧，整FFN周期由调度和其余模块决定。新增硬件实现需计入缩放/区间控制/随机分发/累加/非线性/格式转换/存储，并比较直接随机舍入＋低位确定性矩阵。旧PPL/旧TLM结果不因规则更新而重命名或继承。
- Issue50/PR52的完整联合确认由原负责人继续；恢复先查最新Issue/PR/交接，不重复提交记录中的运行任务。完整WT2与4096目标后缀分别标注，不把单独FFN全量结论或待审PR写成联合全量已完成。

## FFN candidate recommendations and existing negative results

- Before labeling an FFN direction done, failed or new, match the exact forward equation, sampled branches, retained amplitude paths and executed dispatch/PPL evidence. In particular, both-branch gated/AND models do not establish an activation-only result with continuous up. Then inspect matched multi-layer PPL, high-sample and continuous-input controls, including dual-rail gated and three-projection multi-threshold AND-bank results. Do not rename these as untried alternatives; state a concrete new condition and controls before proposing a rerun. Single-layer feasibility does not override a failed multi-layer result. Historical two-projection students already used floating-point weights; W8 is a deployment constraint, not an established remedy for their quality loss.
- Separate input bit width, hidden representation and sample count. Four-bit input results with a single-bit hidden layer do not establish four-bit-hidden or twenty-layer success. Repeating identical sigmoid p-bits reduces sampling variance without changing the mean encoding; a multi-stochastic-layer mean-field surrogate is not automatically the exact infinite-sample network or a PPL lower bound.

## 本地工作副本生命周期与磁盘预算（用户2026-10-19要求）

- 用户要求清除已完成任务的工作副本，今后不长期保留大量checkout。本节接续Issue68/PR69，不撤销并行任务必须隔离目录、保留原始实验证据和禁止覆盖他人改动的规则。
- 同一任务恢复时优先复用已有分支和工作目录。顺序完成后回收该任务工作副本，再为下一项任务建立独立分支/目录；仅在实际并发时保留必要的独立worktree，不为每次只读审阅、统计或恢复重复建立全量副本。
- 文档/审阅任务优先用git show读取对象，或使用git sparse-checkout只检出当前需要的目录；新worktree优先add --no-checkout后按需检出。不要默认在每个helper重复检出历史大事务轨迹、原始结果包、模型、数据集或复制安装环境。验证依赖的配置/fixture/原件必须显式补齐，不能因精简检出而略过必需验证。
- 每项任务交付时检查自己的临时review/resolve/helper目录：提交与SHA留在Git；未跟踪、ignored和未提交资料先分类、逐SHA归档至项目约定存储或已有授权本地归档，再移除完成使命的副本。PR待审保留最小必要工作目录；任务合并后及时回收。长驻目录限于主checkout、长期备忘录入口和仍在进行的任务。
- 回收前核对Issue/PR、负责人、绝对路径、Git refs、未提交/ignored文件和恢复索引；不得按日期/文件夹名批量删目录，不重置或清理其他成员、运行中任务及唯一数据。恢复索引需要说明原分支/HEAD、归档位置和SHA；不得将删除工作副本写成删除实验历史。
- 为节省空间不得给可修改源码建立跨任务硬链接，也不删除共享Git对象库。模型和大结果使用既定共享存储，Git保留版本/配置/摘要/校验索引。
- 本机2026-10-19已回收目录与恢复方法入口：Issue68/PR69的maintenance/storage_cleanup_20261019/REPORT_ZH.md及ROUND2_REPORT_ZH.md；第二轮未提交资料和增量bundle保留在本地project_archives/cleanup_20261019_round2/。旧备忘录中的已归档工作路径可按恢复索引重建，不重复昂贵实验。

- When training a replacement QK selector, preserve the reference selector’s valid/forced masks, free-block normalization, standard-deviation floor and temperature before matching budgets. Fit only on training data, report actual holdout budget/capacity drift, and do not call lower omission at a larger budget a matched-cost gain. If a temperature optimum is at a sweep boundary, extend the control or include a TRAIN-fitted scalar threshold before attributing the gain to a learned selector.

## 数字电路仿真统一台账（用户2026-10-22要求，Issue110）

- 所有LLM相关数字模块及共用随机源新增仿真，必须在同一任务PR内新增或补全 `digital_circuit_simulation_registry/records/` 的run记录，并运行registry.py的check/render，更新总览。维护入口是该目录README_ZH.md；本机固定阅读副本为 `C:/Users/86134/Documents/a_P_BIT/digital_circuit_simulation_registry/`。不再另建互不相通的功耗台账。
- 登记准确执行源码/manifest与配置SHA、原始结果路径或归档成员、原字节SHA-256、工艺/PVT/频率/位宽/激励/seed/窗口、模块边界和未计成本；功能、综合、STA、PT、后布局分别写实际状态。待跑、失败、仅功能、库提取、TLM估计不能写成已测PPA；功耗算出但时序违例/告警须保留。
- 台账只存小型索引/必要数值，不复制大波形/网表/工艺库；同一实验多副本或重汇总不算新实验。新run保留旧失败/负结果。清理结果所在临时目录前，先把台账补为可恢复归档路径/成员和SHA。没有本机或共享存储权限时明确待补，不宣称远端可访问。
- 工作区正式版本为仓库同名目录；本机根目录仅同字节阅读镜像。更改后同步镜像、本人STATUS/HANDOFF与长期备忘录；未合并维护分支先引用最新PR，避免并发覆盖。

## architecture_tlm 原始制品入库

- 本仓库对 architecture_tlm 有宽范围文本换行规则。新增 PNG 等二进制、保留原字节的生成图或日志前，先用局部 .gitattributes 显式保护其字节（例如 PNG 用 binary、原始 SVG/日志用 -text），再暂存；若此前已经暂存，属性修正后对这些明确路径执行 git add --renormalize，让索引重新读取原件。不能为通过空白检查而重写已签 SHA 的制品。提交后逐项比较 Git blob 与原文件的长度和 SHA-256，避免 CRLF 归一化损坏图片或破坏原回执。

- Before staging an overlay Python environment, record the actual imported dependency paths, not only the base venv path. A .pth entry that points at another site-packages directory does not recursively process that directory's .pth files. Verify the full Torch/Transformers/task-harness import chain in a CPU-only allocation before downloading models or requesting a GPU; keep existing personal environments read-only.

- When a CPU validation step runs inside a GPU Slurm job, hide devices inside the launched task (`srun env CUDA_VISIBLE_DEVICES="" python ...`), since Slurm can overwrite the parent export when creating a step. Require the validator to assert the actual child variable and CUDA initialization state before imports/inference.

- Persist numerical-gate comparison records before rejecting an optimization, including per-case score deltas, prediction changes, source and execution identity. Keep the predeclared gate unchanged and preserve the validated reference path when a batching or precision candidate fails.

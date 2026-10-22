# Issue92 计算成本补充交接（2026-10-22，当前）

负责人amlink1219，接续Issue92/task/92-pbit-gate-pilot/PR94。新增部署运算账本qwen/results/pbit_gate_cost_20261022/README_ZH.md、COST.json及compute_cost.py。每自由块32连续乘法/40加法/8bit门控/9概率事件、两阶段；原三位置混合F21，层0/12/23候选QK省378/−165/379 MAC，小网第一层新增672乘法，不能称整体节能。含公共特征/动态归一化、GQA并集与固定S的PV边界。9模型形状、2304隐藏态门控等价、6项均值回算及独立只读审阅通过；没有新训练/Slurm/完整PPL/RTL/PPA，原质量结果保持。发布随PR94，待审未合并；上传核验以work/amlink1219/92/compute_cost/PUBLICATION.json实际回执为准。Projects沿同日已验证read:project不足待同步，不自动合并/关闭Issue。

---

# Issue92 第二轮优化交接（2026-10-22，当前）

负责人amlink1219；同一task/92-pbit-gate-pilot、PR94，base集成83e15289。本轮没有接管他人Issue或作业，第一轮负结果及发布回执保留在下方/历史Git。

## 实际完成

直接最小化期望遗漏mass＋准确TRAIN平均8块约束，隐式梯度；max4 warmup、query-relative输入及global控制。192/48/48新文章排除旧48篇，7776组，先54候选搜索、再9 pbit长训、加入27项max4温度/硬阈值控制；90配置先冻结后一次盲评。CPU2749通过45项，GPU2744/2746/2748/2751均COMPLETED/0:0，CPU2750冻结、2752校验打包完成；没有本任务运行中作业。

盲集三seed平均遗漏：pbit 1.978%/2.021%/24.845%，原T1 4.253%/3.550%/31.365%；验证预选强max4 2.069%/2.163%/24.723%。层0平均候选更少且误差更低；层12遗漏更低但候选多0.5%；层23遗漏略高、候选更少且PV误差低。不能称所有层全面胜出、隐藏随机性独有收益或完整PPL/PPA优势。

正式结果qwen/results/pbit_gate_optimization_20261022/README_ZH.md，含全部90紧凑评估、90小模型原件、15预声明逐文档记录、来源和SHA。执行来源：搜索cfa19622、长训cfad3902、强对照6241ab7f、冻结/盲评f66b65ac、包装727ed629。训练/评估optimize.py的差异仅新增hard-threshold dispatch，network.py/train.py一致；旧kind回归和新hard smoke通过。

## 服务器恢复位置

本人Weican_Chen@10.129.164.156:21570，home /home/Weican_Chen，项目/home/Weican_Chen/projects/pbit-gate-pilot-issue92。全部计算走Slurm，单5090，没有用4090 fallback。

- outputs/gpu_optimize-cfa1962202e3：新教师与54候选；training_dataset.npz SHA d80319da15c29b6b105157d2abce7ce3f11de510f8ffe25c20c18e2ceb24642e。
- outputs/gpu_refine-cfad390297d9：9个direct6000 pbit，TRAIN/VAL相同，blind未参与。
- outputs/gpu_baseline_ext-6241ab7f682c：更低温度＋TRAIN标量硬阈值，非query top-k；CURVE_SUMMARY为前两阶段日志派生。
- freezes/direct-quality-v2-20261022/FREEZE.json：90配置完整冻结，SHA 6ca6e2ce829909a7dd993b8d1a507c55701a135dcc724b02144c737b80a67090。原32MB留服务器，Git放compact+完整manifest。
- outputs/gpu_blind-f66b65ac76d4：90/90盲评原件，EVAL_STARTED先于blind读取。blind NPZ SHA 9ee16da484f00fcfa9a29c30251e376112b7ad4c98d2f3d5caa0249ccf01aec7。
- outputs/cpu_package-727ed629a9f6：135文件小档；downloads/cpu_package-727ed629a9f6.tar.gz（1785053字节），SHA 09eb7c7e102e0e76b0b74d4e3d5d7fe1a172397070e9c40922a0c48e25c2ce16。本机回传与Git暂存blob逐SHA核验。

## 下一步与限制

先读最新Issue92/PR94、成员STATUS、AGENTS/PROJECT_MEMORY，再接续。当前盲集已经使用，不能继续调参后仍称独立测试。下一轮先冻结新的数据/容量/工作点协议；若扩到24层并验证PPL，需要明确新增范围和算力计划，不重跑已完成作业。

约33%/39%/39%的mask超过512 tokens；正式512宏尚不能直接使用。权重仍是浮点软件参考，未做W8/物理响应/真实随机源相关性、整模型PPL或PPA。确定性49参只300epoch与pbit6000不匹配，不宣称随机隐藏优势。质量／候选量／新增门控成本分开比较。

本轮科学成果64848a345c7926881f0c4b1ff543954fcc851eea已推送，PR94已更新并开放待审、未合并。263项远端Git对象和8项关键原始SHA256已核；Issue92里程碑及结果评论6335181212已同步。实际回执见本目录optimization_v2/PUBLICATION.json；后续提交仅补发布元数据。PR不自动合并，Issue保持开放；实时GraphQL确认缺read:project，看板待同步，未作看板写入。以下是第一轮交接历史，当前恢复以本节为准。

---

# Issue92 小型p-bit筛选网交接

2026-10-22；负责人amlink1219（75301230）；目标rayggxia-workspace/pbit-llm-qwen-baselines（1420564659）。

## 当前状态

实际服务器训练已完成，Slurm2741 COMPLETED/ExitCode0:0，没有本任务运行中作业。论文级优势尚未成立：49参数4→8→1网在层0/12/23的holdout遗漏质量为6.173%/4.493%/37.082%，原max4为4.552%/3.319%/32.298%；网的预算略高仍更差。BCE下降只能说明训练流程能优化首轮代理目标。完整学生PPL/Ising联合/PPA没有执行，正式Attention默认未改。

任务分支task/92-pbit-gate-pilot，独立目录workspace_projects/gt92；PR base为pbit-tlm-attention-details-20261016，初始83e15289434af50fc09c35e699d8b39965389d98。代码和报告已推送，payload提交074172c93b00b30eef30923223fe8a408b1ccd13；PR94开放待审、未合并，Issue92验收和评论已更新。82项远端Git对象、8项关键原始文件SHA256已核。准确回执见PUBLICATION.json；本次后续提交仅补发布元数据。Projects缺read:project，因此看板待同步，未改权限/凭证。

## 执行与成果

- 冻结执行源码53c24f28eb24d25f0edffc4e45354dab6cd86154。最终CPU2740的16项测试通过；先前CPU2738环境/SHA门禁通过、CPU2739为增加分母诊断前快照的16项检查。
- 主服务器Weican_Chen@10.129.164.156:21570，规范home /home/Weican_Chen；RTX5090分区gpu5090、job-name cwc、单GPU+4CPU、12G主机内存请求。无备用GPU作业；备用155的可选完整探测超时后，轻量squeue恢复成功，终态/提交前检查分别保留，不把超时当空队列。
- 不可变快照/home/Weican_Chen/projects/pbit-gate-pilot-issue92/snapshots/53c24f28eb24d25f0edffc4e45354dab6cd86154。
- 远端成果/home/Weican_Chen/projects/pbit-gate-pilot-issue92/outputs/gpu_pilot-53c24f28eb24。
- NPZ 8557506字节，SHA256 5a531bed5bfbfc688db272384857ee369985ef9761d58023fec4b0fbb3f7f249，位于该成果根capture/dataset.npz。模型/原始语料/NPZ未上传Git，仍在本人已授权服务器。
- 正式代码experiments/pbit_gate_pilot_20261022；小型报告/逐epoch日志/JSON小网参数/原字节调度记录qwen/results/pbit_gate_pilot_20261022。54个小文件传回并逐SHA验证，ARTIFACT_INDEX和MANIFEST保留完整源位置、输入版本与散列。
- 配置32/8/8文章、0/12/23层、head0/6/13、3query位置、3训练seed、3评估seed×16draw、100epoch。验证选checkpoint，holdout从未调参；总45.90秒、训练评估30.05秒。

## 恢复和下一步

1. 先读取远端最新README/AGENTS/PROJECT_MEMORY、Issue92和关联PR、所有成员STATUS，核对本人的认证身份和权限；别重交已完成2741。
2. 从结果README/RESULTS.json检查负结果、真实预算、PV与容量。当前可变mask约35%–40%超过512 token，不能直接塞进512宏，也不能按预算均值代替缓冲上限。
3. 若用户继续，另行冻结直接质量/PV目标、相同规模确定性控制及新的独立留出协议；本次holdout已经看过，后续调参不能继续把它当独立测试。先做新的局部训练对照，再决定完整PPL接入，不直接改现有正式默认。
4. 复用已核个人venv /home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/.venv/bin/python，不安装到共享/系统环境。所有算力操作经Slurm，先核队列与allocation。完整环境及原命令在RUN/ENVIRONMENT，README给出sbatch环境接口。
5. PR待审时不合并、不关闭Issue。看板若read:project不足，保留待同步，并以PUBLICATION.json实际响应为准。

没有待恢复训练，没有另行下载数据或在登录节点运行训练。辅助脚本和完整本机传回档位于DAC资料根outputs/gate_pilot_20261022；正式成果不依赖这些本机临时脚本即可解释和复现。

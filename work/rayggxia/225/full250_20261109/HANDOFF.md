## 2026-11-10 完整概率任务与数字接口清单已发布

PR249源80bdfaa9f7a785b4f66469082a269e28cd62968e，20文件远端完整回读一致，Issue225评论6746072666。EDA门禁38644763已通过，完整数组38644764的_0/_1运行、_2等待并行限制，尚未完成。全量36层/151936词表/三seed、原生LPDDR、28nm250新价保持；旧46ms仍为外推，不重标签。数字优先两级量化MAC/CIM，FFN与Attention确认问题已写文件，未发消息/提交数字任务。源包/环境/回执SHA齐，恢复本work/ops.py status；PR待审未合并，Projects待维护者同步。

---

## 2026-11-10 完整概率版已启动

门禁38644763已通过（EXIT0/SEAL/Slurm COMPLETED）；数组38644764_0/1已RUNNING，实际job38644798/38644799；_2依并行限制等待。全量仍未完成。精确观测见OBSERVATION_20261110.json，后续只查状态、不重复提交。数字接口待确认清单已写，未发消息或提交数字任务。

---

# 完整概率版提交与数字对照交接

## 2026-11-10 28nm250完整概率版已提交：本地回执待发布

Issue225/PR249，rayggxia；沿task/225-tlm-unified250-20261107。北京时间00:46提交EDA门禁38644763与完整三seed数组38644764，afterok依赖、最多2并行；请求1CPU/12GiB，实际Slurm可能分配3CPU，无GPU。36层/151936词表、GU16/Wd32/K128/S64/S12、3核/832KiB保持；原生LPDDR derived8533后端。不是仅跑2层或缩小head的全量任务；门禁本身仍一层/384head。

服务器根/public3/home/t6s011227/pbit_chimera_pipeline_20260920/tlm28p250_full225_3c811d6efe58；源码包SHA9e0125325e3aaae6151786ef16645159f4a82d20c58aa175dd9f9dad12f8bf87，MFf69df7db841445d52d9572732824709130d5cdedacaff99981dbdd957490fd8b。各case独立work防止DRAM统计互相覆盖。现已提交，不把门禁运行/全量依赖等待写成完成；最新状态见本work/STATUS。冻结源码不修改，binary64等值兼容补丁与六检查另存。55/500不变，无新EDA电路/GPU/PPL。

数字新决定：两级量化整数MAC/CIM优先，z25位尾数/指数到共享P8、Wd复用/状态位宽及计费边界需FFN确认；Attention只确认完整PV概率数制/转换和可选R8实际数量归一化。现有参考价格已够，不能再用旧浮点Wd的7.9x/21x称最强数字优势。详细转发文件process_28nm/250MHz/DIGITAL_BASELINE_COORDINATION_20261110_ZH.md；未向其他对话发消息。等面积/数字执行/内存排布由TLM端负责，确认不阻塞概率作业。

恢复本work/ops.py status，完成只认EXIT=0与SEAL/原件SHA；需要修复则独立新快照，不重复提交健康任务。本地提交回执已齐，GitHub同步看本work/PUBLICATION；PR未合并，Projects待维护者同步。

---

# Qwen3-4B：28nm250完整概率版Slurm任务

实际提交：2026-11-10T00:46:36.606205+08:00（北京时间）。Issue225 / PR249，rayggxia。已提交，完成状态以每项SEAL＋EXIT＋实际Slurm状态为准，不将依赖队列写成已完成。

|任务|Slurm ID|范围|
|---|---|---|
|CPU门禁|38644763|原生外存、一层＋384词条head，seed17|
|完整数组|38644764，下标0/1/2|36层＋完整151936词表，seed17/503/1009|

完整数组依赖门禁afterok，通过后自动启动，最多2项并行。每项请求1CPU/12GiB，pilot4h、full12h，无GPU；集群可能按节点粒度实际分配3CPU，实际分配以sacct为准，不能把请求数当实测分配。各项有独立工作目录及原生DRAM统计文件，不会并发覆盖统计输出。

## 冻结的配置

Qwen/Qwen3-4B revision1cfa9a7208912126459214e8b04321603b3df60c的执行形状；B1/2K；28nm TT0.9V25°C、250MHz；3随机FFN公共核、GU16/Wd32；SparQ K128、Ising/PV S64、A/S12优先分数前端；256共享BF16 FMA、PV每头2ADD；832KiB/178真实宏。沿最新6.480303mm²条件成本账本，宏/hold/参考宽度边界保留。

本次用**原生Ramulator桥＋既有derived8533配置**，保留LPDDR命令/队列/回压，8533为衍生时序而非独立JEDEC8533签核。外存能量仍采用独立4/6.6/8pJ/bit情景，不能把原生时序模型说成新DRAM芯片实测功耗。完整输出提供含head、扣head阶段时间/能量、各模块面积与动作能量；共享硬件面积不随36层重复。

这是完整硬件事务执行，不加载真实模型权重、不生成文本、不计算PPL；筛选/采样使用已冻结代表性输入及地址轨迹。精度实验是另一条证据，不能因这次硬件运行宣称新精度通过。

## 结果与恢复

服务器根：`/public3/home/t6s011227/pbit_chimera_pipeline_20260920/tlm28p250_full225_3c811d6efe58`。

- `outputs/pilot/`；`outputs/seed17/`、`seed503/`、`seed1009/`：RESULT/BUDGET/VALIDATION/SEAL。
- `work/<case>/INVOCATION.json`、`EXIT.json`、`run.log`：实际命令、源清单、Slurm ID及返回码。
- `logs/`：Slurm日志；根SUBMISSION记录依赖和作业ID。
- 本地入口：`work/rayggxia/225/full250_20261109/ops.py status`；使用已有EDA登录助手，不在代码/聊天中放凭据。

包SHA-256：`9e0125325e3aaae6151786ef16645159f4a82d20c58aa175dd9f9dad12f8bf87`；执行清单SHA-256：`f69df7db841445d52d9572732824709130d5cdedacaff99981dbdd957490fd8b`，大小44006B。manifest逐文件核验源码/配置，并验证已有runtime/dependencies/host三个冻结清单。原始源码包和结果按项目共享/本地索引保存，不修改已提交源。

源基于e6dc60c及一项等值兼容补丁：binary64 epsilon由math.ulp(1.0)改为2**-52，价格与调度不变，六项既有检查通过；补丁前后SHA见PORTABILITY_PATCH。Slurm显式使用已有Python3.9.6/GCC11.2环境与已验证原生库，避免登录节点默认Python3.6造成版本混淆。

本机已检查既有队列，无同配置TLM重复任务；未取消其他健康作业。若门禁失败，完整数组不执行；保持失败源与回执后另做修复，不能原地改冻结包。

数字对照仍未提交；需要的模块确认见[DIGITAL_BASELINE_COORDINATION](DIGITAL_BASELINE_COORDINATION_20261110_ZH.md)。数字主线优先两级量化整数MAC/CIM，旧浮点Wd只作参考；接入、等面积和存储调度由TLM侧完成。

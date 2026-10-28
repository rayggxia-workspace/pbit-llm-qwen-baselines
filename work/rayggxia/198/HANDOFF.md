## 2026-10-28 SparQ＋Ising完整WT2三seed完成（Issue198 / PR199）

负责人rayggxia；task/198-attention-compare，原独立checkout继续复用，PR待审未合并。GPU Slurm3270_[0-2]完整结果均已收齐，独立SHA/回执、299077目标恰好各一次、36层计分覆盖及每头160更新/128保留采样审计通过。执行源a7108f8cba2c72ad319114af34557f4cec2b793d；短流源d9b64717641ae8f7efeaa2e9375a1b01a30361d0。模型Qwen/Qwen3-4B后训练revision1cfa9a7208912126459214e8b04321603b3df60c，权重/tokenizer/原始train-test/token SHA在provenance中核验。原BF16 FFN/投影/归一化不改，dense prefill、全36层单query Attention替换；无chat模板、无BOS，window2048/stride1024、batch32。

完整PPL：BF16 11.538153；纯SparQ 10.797926；SparQ＋winner S128 11.177429±0.006594（三seed样本标准差），相对BF16 -3.126%，相对纯SparQ +3.515%。固定r32/k128/local32、burn32/spacing1，赢家地址直接V读出；理想FP32 sigmoid/Philox行为参考，不是器件或q/256实测。完整结果不同于1024目标初筛，短流S32退化/S512≈IID128的负结果保留。

完整平均每KV组唯一V 54.594行。理想标量读取、候选K维度复用、4Q完整去重下，K+V逻辑元素需求为dense的17.41%、纯SparQ的87.91%；不是实测DRAM字节或速度。SparQ第一阶段全N近似softmax和top-k仍存在，只替换候选上的第二阶段softmax/PV。当前说明质量可行但未证明同质量完整硬件PPA胜出；完整缓存、布局、仲裁、累加及有限相关采样成本待补，不继承旧控制RTL为整机PPA。无新数字电路台账run。

正式源码及报告：experiments/sparq_ising_20261028/results/REPORT_ZH.md、SUMMARY.json。准确SOURCE/SUBMISSION/COLLECTION见work/rayggxia/198/QUALITY_*；原始结果保留本人GPU目录/home/Hongjie_Zeng/projects/attention-sparq-ising-issue198-20261028和本地project_archives/attention_compare_issue198_20261027/quality。report_quality.py可按封存原件重建。下一步以纯SparQ为硬件主要对手，在匹配质量下接有限KV读出和控制费用；未自动启动额外全量扫参、未合并PR或关闭Issue，Projects权限待维护者同步。发布以QUALITY_PUBLICATION.json和远端实际head为准。

## 2026-10-28 SparQ + Ising Attention-only：短流已完成，完整WT2运行

负责人rayggxia，继续Issue198/草稿PR199，不接管PR163。用户明确授权GPU实验。Qwen/Qwen3-4B后训练revision1cfa9a7，原BF16 FFN/QKV/Wo/norms不改。论文GQA概率求和r32/k128/local32；赢家保持argmax初始化、burn32、spacing1、理想FP32 sigmoid/Philox，不是q/256器件实测；实际赢家地址直接V读出，没有第二次PV抽样。

短流科学源d9b64717641ae8f7efeaa2e9375a1b01a30361d0，CPU3263/GPU门禁3264/三seed3265已完成。8窗context2048，每窗128目标，共1024；所有计分目标全36层单query，非完整WT2。BF16原生/包装logits逐字节相同，5CPU测试、960帧GPU逐帧oracle和稳态TV门禁通过。三seedPPL：BF16 13.562400；纯SparQ12.822322；winner S32 14.741226±0.637781；S128 13.342155±0.145833；S512 13.006869±0.027843；IID128 13.002485±0.031817。相对纯SparQ仍有有限采样损失，S512接近IID128提示相关性成本；不能称无损或PPA胜出。S128四Q共享KV组平均唯一V55.11行，仅理想逻辑去重，不是实际DRAM流量。

完整WT2源a7108f8cba2c72ad319114af34557f4cec2b793d；CPU3268、GPU3269门禁通过，batch32显存<28GiB。Slurm3270_[0-2]正在运行，固定S128三seed，每32窗配对BF16/纯SparQ/winner，计划299077目标；不得将已完成分片当完整PPL，不重复提交或取消健康任务。每片随机键含起点，避免随机流重置复用。GPU数值运行耗时不作ASIC周期。

源码experiments/sparq_ising_20261028；阶段报告results/REPORT_ZH.md、SUMMARY.json。准确SOURCE/SUBMISSION/COLLECTION均在work/rayggxia/198/QUALITY_*；原字节本地project_archives/attention_compare_issue198_20261027/quality及本人GPU独立目录/home/Hongjie_Zeng/projects/attention-sparq-ising-issue198-20261028。collect_quality.py按源前缀下载校验，report_quality.py核三seed完整回执/目标/层/采样计数；完整结束后再次收a7108f8cba2c并生成完整表。未训练、无新RTL/EDA/数字台账run；PR待审不自动合并，Projects待既有权限同步。

发布确认（2026-10-28）：KV读取与数字Attention基线调研源1f3ce3ee63653e1a88fb0b73f65eba5cd59ac2d0已推送草稿PR199；13文件完整tree/本地同SHA、7关键文件逐字读回通过。Issue198评论6461917653；100地址核验/18旧单头案例布局推导、功耗面积09三文件同字节，不是新GQA模型/时序/PPA。真实4头QKV与同质量完整链仍待补；82run不改，无运行作业。回执work/rayggxia/198/KV_BASELINE_PUBLICATION.json。

2026-10-28 KV读取与经典数字Attention基线调研：正式KV_DIGITAL_BASELINE_ZH_20261028.md/SOURCES。锁定FlashInfer和vLLM布局文档；主TLM已做GQA并集/在线融合，不另造整机。本次100地址几何核验、18旧2K/d128/S128单头案例原ZIP/成员SHA复核并做布局换算；无新抽样/模型/DRAMSys/RTL/EDA。P0旧轨迹V连续行32KiB→指定通道交错页示例456KiB，不是GPU实测/同质量GQA；真实4头QKV/同质量S/有限SG与bank访问仍待确认。Qwen3-4B形状2K全KV每层8MiB、36层288MiB；下界不等于时延。功耗面积目录09与两份数据已同字节同步，旧文件和82run不改。仅只读Issue186/PR192@91f68416，未改统一入口/默认资源。发布见KV_BASELINE_PUBLICATION.json及Issue198最新评论，草稿PR199待审；无运行作业，Projects待维护者同步。

发布确认（2026-10-28）：Softmax文献参考已放入统一功耗面积目录08文件及CSV/JSON，共14点；源310c0381978957df95a391af48779bacd795cc45已推送草稿PR199，5关键文件逐字读回、完整tree/本地同SHA通过。根阅读镜像3文件同字节；82run/105旧文件未改。Issue198评论6461568004，PR待审未合并。回执work/rayggxia/198/SOFTMAX_REFERENCE_PUBLICATION.json。

2026-10-28用户要求调研也进入功耗面积文件夹：已在统一台账新增08_Softmax文献功耗面积周期参考.md及references/softmax_20261028的CSV/JSON，共14个文献点，含原工艺、整行拍数、时钟ns、面积和已有功耗/功耗频率；未知整行周期明确保留null。只列文献，不新增本机run、不跨工艺×0.81；根固定阅读副本3文件同字节，既有文件/records保持原SHA。复现build_softmax_reference.py；发布见SOFTMAX_REFERENCE_PUBLICATION.json及Issue198最新评论。PR199待审；无运行作业，Projects待维护者同步。

发布确认（2026-10-28）：普通数字Softmax调研已推送草稿PR199，源e73e50abc414c7b5ebd442a5c0f515880260236e，完整tree与本地同SHA、4关键文件逐字读回通过。Issue198评论6461443490，未合并；PDF私有归档SHA和5行周期换算已核。无新RTL/EDA/模型/台账run。准确回执work/rayggxia/198/SOFTMAX_PUBLICATION.json。

2026-10-28 普通数字Softmax调研完成：512输入公开FP16/DW/P8为199拍/45nm 0.283300mm²；fixed32/LUT/P1/2/4为1542/775/392拍、0.059/0.085/0.138mm²（NOREG，外部存储另计）。65nm小定点核与FP精度/边界不同；不据跨工艺文献宣称Ising胜出。正式SURVEY/SOURCES记录PDF SHA、页面/代码pin、失败与算术；私有原件已逐SHA归档。无新RTL/EDA/模型或registry run、无运行作业；上传状态见SOFTMAX_PUBLICATION.json。下一步同SHARK库实现明确精度/缓冲的数字及CDF采样对手，本轮未启动。Projects待维护者同步，PR199待审未合并。

发布确认（2026-10-28）：Attention服务器DC/VCS/PT已推送草稿PR199，源2c4e4bafb74d41779bbaff78e346d0800172bcc8，39文件完整tree及7关键文件逐字读回、本地同SHA通过。Issue198评论6460241999，未合并；8DC/116回放/66PT，hold违例与PWR-981保留。81联合台账，1662报告/72诊断成员SHA已核，原始大包仅服务器，本任务无运行作业。回执work/rayggxia/198/EDA_PUBLICATION.json。

2026-10-28服务器评估已完成：8DC/116VCS回放230400拍/66PT窗口及8top时序审计，所有hold违例，PWR-981保留；无签核/模型结论。主候选G16融合折算0.035969mm²、全1控制17.17pJ/输出。准确结果RESULTS_ZH.md，源/作业/原件EDA_*；原始私有大包仅服务器。本地报告包逐成员SHA与72诊断成员已核；上传见EDA_PUBLICATION.json，PR199待审。下一步IO/reset合同/hold/标注，无需重跑健康原任务。

## 2026-10-28 EDA服务器测试进行中

用户明确授权本任务EDA实测；延续PR199/task198，不接管pbit整片任务。已通过现有客户端验证登录、库SHA与本地一致；私有连接/库/模型位置仅在.eda_private。DC预检38437604因拒绝RTL先引用后声明coin_mask失败；仅调整声明顺序，新20项/90000拍独立oracle通过，旧快照保留。修正预检38437625完成，G16p2 setup约+0.44ns、hold约−0.02ns，不能称时序通过。其余DC矩阵38437668（7项，%2）及VCS/PT预检38437709/矩阵38437736已提交。SS1.08V125C/100MHz、输入slew0.1ns/输出0.02pF、setup uncertainty2ns/hold0.1ns；无SPEF/CTS/SDF。原始面积×0.81另报55nm折算，功耗时序不缩放。长任务均Slurm，已冻结v1/v2/v3且逐SHA校验；真实状态以后续收集回执为准。不得重复提交健康任务。

发布确认（2026-10-27）：完整Attention反馈/仲裁v2已推送草稿PR199，源7fe360390c01de5195e504094f36ee62735b02be；56文件完整tree与本地同SHA、7关键文件逐字读回通过。Issue198评论6445525003；待审未合并，STA/PT及后训练/全V链仍待后续，无运行中任务。准确回执work/rayggxia/198/CONTROL_PUBLICATION.json。

2026-10-27 控制v2本地完成，上传状态见CONTROL_PUBLICATION.json（尚未生成即未确认发布）。完整赢家/拒绝反馈仲裁RTL、8固定PPA top、独立oracle/数学检查、DC/PT脚本在control_v2。124RTL项422800拍及3个cap64零延迟门级1920拍通过，8个55nm SS映射0.018058–0.056112mm²；STA/功耗未跑，不把TB100MHz当时序通过。源码/原字节/公开包/台账/记忆同步见CONTROL_*。保留G16融合/两级及G32候选待STA；源供给/完整V链/后训练QKV/GQA/D1仍待补。无运行中GPU/Slurm/许可EDA作业；PR199草稿、未合并。

已发布：草稿PR199（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/199），科学提交5fad0fc32f5284560c38c03f4fe28657f936f553；7关键文件远端逐字回读、完整Git tree和本地相同SHA导入通过。Issue198评论6443236705；待审未合并，广泛验收仍开放。PUBLICATION.json为准确回执。

# Issue198交接

2026-10-27，rayggxia。用户指定两份Attention资料后，本轮完成第一阶段可运行代码与功能仿真。任务更广泛的验收保持open；准确发布状态见PUBLICATION.json，不能用本文件的本地完成冒充已合并。

仓库rayggxia-workspace/pbit-llm-qwen-baselines；task/198-attention-compare；main base d83eeb1fc6b89a3dff51b5b62bf79acf665c7166；独立最小worktree C:/Users/86134/Documents/a_P_BIT/tmp/attention-compare-issue198-20261027。原GitHub CLI网络getaddrinfo失败，使用认证rayggxia连接器发布；未改变历史origin/他人分支。

正式代码architecture_tlm/attention_compare_20261027：core.py、schedule.py、run.py、quality.py、test_core.py；rtl/attention_rejection_control.sv、nr_singleton_tree.sv、tb_rejection.sv及validate_rtl.py。P3/P4复用main已合PR88三个模块，未复制改写随机算法；源SHA在INPUTS和执行SOURCE。数字参考输入BF16存储、算术FP64数学oracle，未冒称逐位BF16 MAC。

已验证6机制测试、108合成案例、72项预算探索；RTL9例22500拍通过，N16/64/512，seed17/503/1009，配置/输出/公平位等待、reset、cap、m24上限均覆盖。Icarus10.1在Windows沙箱内启动WinError623，沙箱外自动审批后短验证成功。rtl_v2打印格式失败、旧快照和负结果均归档；最终RTL为rtl_v4，未跑综合/STA/PT。cap失败会在输出若干地址后报告failed，下游必须丢弃整query部分和，不得用部分输出充成功。

原始输入为固定normal QKV，未加载真实模型/文本/tokenizer；不适用模型SHA/BF16 PPL复现门禁，不能引用旧Base证据作新模型。L512/2048/8192、d64/128，S=L/16，筛选8块。单一输入/三seed均值过解析IID128 MSE阈值仅探索；P3/P4须S512，117264/22181条件拍，对D033586；没有能量/面积胜出结论。

重跑命令见正式README，必须新输出目录。正式Python为C:/Users/86134/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe（3.12.14，NumPy2.3.5）；Icarus位于C:/Users/86134/Documents/a_P_BIT/sc_weight_storage_or4_20261014/tools/iverilog/bin，ivl-lib为同级../lib/ivl。CLI命令与环境见CONFIG/VALIDATION。

RAW_ARCHIVE.json是5.31MB原始ZIP及399成员逐SHA，包含逐case事件/地址/结果、全部bit轨迹与编译日志、历史失败；.vvp可重建不归档。Git保留小型FINAL汇总/配置/SOURCE/manifest与QUALITY/RTL VALIDATION。读取manifest中的某个case原件时，从ZIP的results/sweep_final/对应成员取出并核对SHA。输入与外部资料保持原位置，不上传用户PDF/工艺库/模型。

统一台账同PR仅新增attention-rejection-198-20261027；main缺全套工具，work/rayggxia/198/registry_check用根现有78记录增量合成79并check/render；READING_SYNC记录根镜像原记录未改的核验。本人Issue28记忆维护副本和根镜像原有历史差异，分别追加同段，旧字节保留，preimage在归档。尚未执行远端Projects同步。

下一步按优先级：

1. 将新RTL真实捕获→树→校正/反馈→配置完成→输出的边沿时序接到PR88或可替换适配器；源配置/稳定等待外供，不能删sink检查绕过PR192未实现映射。
2. 用后训练真实QKV建立同输入数学/逐位参考与质量曲线；若新增模型比较，核对model revision、权重/tokenizer、train/test SHA并同轮重跑未变BF16。旧78 Base仅诊断引用。
3. 实现赢家完整count/无偏按秩仲裁RTL；补共享V有限表/缓存/返回/累加；D1固定ITA commit/许可后移植或建立明确INT8合同。
4. 沿统一unified_v6接口补GQA集合复用和真实memory后端，报告固定资源与质量/吞吐匹配；Link宏条件模型不是新整机版本。
5. 若用户要PPA，先N512代表控制与公共算术STA/PT，不重测已有源本体；按相同PVT/负载/活动绑定计价。未知完整成本留null。

无本任务运行中GPU/Slurm/许可EDA或自动化。保留最小待审目录；恢复优先复用，不新建全量副本，不清理其他成员。PR待审不关闭Issue。

控制v2原始目录已逐SHA归档后回收，释放629349369字节；保留最终小汇总与PPA源bundle。重现report.py需从CONTROL_RAW_ARCHIVE.json所指ZIP恢复对应results成员；逐成员SHA必须一致。CONTROL_CLEANUP.json记录范围，未删除其他任务/共享库。

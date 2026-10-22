# 2026-10-22 评估补充交接

负责人amlink1219；Issue37；task/37-ising-update-20261022；base集成5b26c80c28ab22383f12ab31046dd723ca985abb；独立最小稀疏工作目录workspace_projects/iu37。正式报告architecture_tlm/attention_comparison/ISING_UPDATE_20261022_ZH.md，原README新增索引；项目记忆和本人STATUS已补充，原科学结果及他人文件不改。

已做：固定已合并PR79/80、待审PR82/86/88 head；核查新算法、128目标后缀PPL、90配置真实QKV、驱动量化、v5单模块/单层连通与旧数字表边界。19个来源逐SHA核验，固定预算与TLM中位数/单位/null成本等46项离线检查通过，见ISING_UPDATE_VALIDATION_20261022.json；来源见ISING_UPDATE_SOURCES_20261022.json。报告已作行为与TLM独立审阅。没有新模型、GPU/Slurm、训练、PT或上游采样器测试运行；当前没有本任务远端作业。

另通过21项文档链接/历史保留/边界与Git检查，见ISING_UPDATE_DOC_CHECKS_20261022.json；7项稳定文件SHA见ISING_UPDATE_DELIVERY_20261022.json。2026-10-22实际只读GraphQL返回INSUFFICIENT_SCOPES，缺read:project，看板待同步；不影响仓库分支/PR。

发布已完成：结果提交18bd5f299cba76ff0c33dbf0d02d8133eac165d7已推送，[PR89](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/89)开放待审、未合并；ref/PR head和7项稳定文件的GitHub原字节SHA读回一致。最新PR82/86/88 head与报告固定版本相同且仍未合并。回执见ISING_UPDATE_PUBLICATION_20261022.json；本次发布仅含评估补充、来源验证和本人状态/交接/项目记忆，不包含PR82/86/88源码。最终完整模型PPL与物理PPA继续待原负责人/后续任务；不能因本报告而关闭37/78/87。

恢复：先读最新Issue37、78、87与PR82/86/88/89，复核远端集成和head是否变化，再读本报告、来源及验证；需要验证旧数据时只读冻结提交，不重放Slurm提交。不把旧README/HANDOFF中的权限时点当当前状态。当前继续PR89评审，无需重建PR或重推已确认结果；不要自动合并。

以下全部为历史时点记录，按其原日期理解：

# 本轮补传状态（2026-10-19）

分支已推送，[PR #45](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/45)待审、未合并；Issue保持open。amlink1219当前Admin/push权限已核实。看板GraphQL仍缺read:project，待同步。最新个人汇总见progress/amlink1219/STATUS.md；PUBLICATION.json记录原交付提交，DELIVERY_MANIFEST.json记录补传后文件SHA。

以下交接保留原执行时点，其中无push权限/未发布描述属于历史状态；原manifest按原提交验证。

# Issue37 交接

负责人amlink1219；2026-10-19；正式目标rayggxia-workspace/pbit-llm-qwen-baselines。[Issue37](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/37)。

本地独立工作树 `E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/workspace_projects/ac37`，分支`task/37-attention-comparison`。目标PR base `pbit-tlm-attention-details-20261016` @3553996bf014a29dee7fdb2250a3965e8fd881a4，依赖Issue36本地d3c6514b34dcb106ed4053a2d4d93a871d0a011c。实际执行源**7f1cc0d5c3e967f4983727c726b7e1d6e36e7873**；其后报告/后处理提交不是实际事务执行源。实现工作树ac37run独立保留，95450bc已cherry-pick，勿重置它。

## 实际完成

- 核实amlink1219/id75301230、目标仓库id1420564659、最新README/AGENTS/Issue/PR、集成branch及PR29最新项目备忘录；没有接管FFN或其他成员任务。项目AGENTS保留原规则并增加旧汇总token/cold-warm/范围的比较要求。
- 旧v3/v4结果只读提取、源SHA核对，保留两token均值对单冷token等差异。旧结果未覆盖。
- 新完整模块条件TLM包含共同投影84MiB stream、RoPE/KV追加、digital dense或screen/Ising/V、Wo；统一100MHz/512MAC、16GB/s、64B、有限pending32，SRAM按E/SS word收费和实际峰值分配。输出physical_PPA/PPL均null，所有非SRAM成本系数为proxy。
- 本地9/9小测试；Slurm**2164 CPU1、COMPLETED/0:0**，冻结快照23源SHA核验，9/9测试、32/32全24层场景。GPU未请求且CUDA_VISIBLE_DEVICES为空。第一终态和分配立即保存于SLURM_TERMINAL.txt。当前无本任务运行作业。
- 完成归档及40结果文件SHA独立回收验证、32项阶段/容量/权重/能量闭合和周期地址相同性验证；独立审阅三seed均值/ratio、tau盈亏点及SRAM范围。正式postprocessor重算三份派生报告逐字节一致。

## 成果和版本

正式代码/报告`architecture_tlm/attention_comparison/`；历史索引/新结果`architecture_tlm/results/attention_comparison_20261019/`。raw包含全部32个小型case JSON、summary、来源和已关闭日志，未保留大候选/样本数组；每行candidate信息和样本顺序SHA可由代码/seed重建。模型权重/语料没有参与本轮仿真，因此模型数据SHA不适用；模型配置、筛选校准、合成fixture/seed来源在源清单中。

个人服务器规范root `/home/Weican_Chen/projects/attention-compare-issue37`；不可变执行目录`snapshots/7f1cc0d5c3e967f4983727c726b7e1d6e36e7873`，结果`outputs/7f1cc0d5c3e9`，日志`logs/compare-2164.out/.err`；archive与源码清单见本目录receipt。所有文件仅在本人home，不访问他人目录。Python沿用本人旧项目`.venv/bin/python`的词法路径，纯标准库，不安装系统依赖。

历史Issue36 manifest应在其交付提交d3c6514复核；本任务已按规则更新同一个个人STATUS，不能拿当前HEAD的STATUS去要求匹配旧任务记录的字节。Issue37 manifest覆盖本次交付文件，不重写既有历史manifest。

## 结论与限制

2K主表：D0 29.480ms/条件10.057mJ，P/S32 27.963/8.961，S128 33.038/9.495，S512 49.921/11.080（三seed、warm、100ns、512候选）。S128宏期需约<=17.27ns才在该固定映射延迟胜过D0；S512仅加快宏不足。D0 SRAM64KiB/.53162mm²，P2K256KiB/2.12648，P8K448KiB/3.72134；小Ising宏面积不能替代全模块。

这些不是等PPL验收、器件/RTL或真实功率预测。8K固定512候选仅6.25%，不能从其成本优势推质量。screen_exact为variable候选，不能用其差值独立归因Ising。理想IID只用于地址；真正Ising量化/相关性/有效采样率/随机源成本、同候选数字systematic对照、分阶段流式64KiB和同工艺表征仍待完成。

## 远端与下一步

当前amlink1219对正式目标push=false，未推分支、未创建PR；本人Issue37同步实际摘要并回读，保持open。Projects此前明确缺read:project，待权限同步。不是代码已上传/PR已交付。发布前复核最新Issue/PR/base/身份和全部push URL；权限可用后只推该任务分支、用PR_BODY.md建PR，不自动合并、不换账号/旧库。若Issue36仍未上传，本分支明确携带其数字参考依赖，不能当纯独立补丁漏报。

已有结果复核可运行README的postprocessor到新目录；不要重放Slurm提交。若确有新代码或新配置要运行，创建新commit/新snapshot/新输出，先测试；重型任务只走分配。后续首选S32/128与固定候选的行为级PPL验证，宏输出周期目标和SRAM/V-gather重排可并行设计。

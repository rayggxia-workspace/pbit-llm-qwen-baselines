## 2026-10-28 Issue201最终发布确认：PR202已ready

最终结果已实际推送，科学成果提交4134a3629bf2d08610a303ed6e13057f562fd441；PR202 ready/open、待审未合并（依赖PR174）。40份主计分/37唯一、108原始JSON与sidecar的Git字节SHA全部一致，八个关键远端blob回读一致。FINAL_PUBLICATION.json含准确提交、回读SHA和Issue201评论链接；不是此前草稿/运行中状态。Issue验收项已更新，保持open待审，不合并；Projects缺read:project待同步。

核心结果：联合256拍PPL15.8951±0.1856，固定W同T15.2405±0.2481（+4.30%）；原BF1613.566049（+17.17%）。仅1024目标后缀、非完整WT2；未训练，无新PPA，GU恢复仍FP32oracle。当前用户要求的扫描和报告已交付，无需再收3200或重交。后续可审阅该PR，若扩充完整WT2/共享W源/Ka×Kw扫描须显式作为后续研究；不建立新自动回查。

## 2026-10-28 Issue201：Wg/Wu双随机40项已完成核验

2026-10-28T09:51:41+08:00；负责人jieruiz，task/201-dual-gu-short，PR202依赖未合PR174，目录tmp/dual-gu-issue201-20261027。Slurm3200四片各10份完成，40物理/37唯一主计分、三seed齐全；pilot4份独立。58源blob、模型/数据/token/目标/TRAIN表、documents/sidecar SHA与36层各8次/17400词覆盖核验通过，18项CPU/CUDA通过。此前运行中/单seed数字仅历史；未重跑。

后训练Qwen3-4B、1024目标后缀（非完整WT2），BF16四次13.566049。T32/64/128/256固定W均值15.6137/15.3647/15.6853/15.2405，W-IID76.2007/25.5600/18.8150/16.8902，A/W联合29.9061/18.3942/16.5566/15.8951。联合256 std0.1856，相对同T固定W+4.30%、BF16+17.17%；不能称无损。仅Wg/Wu权重取随机，Wd固定W8、原随机NL128、准确SDPA不变；联合分配同时换A/W层数，W独立未共享。GU恢复FP32oracle，非全链路bittrue，无训练/RTL/PPA。256是GU长度非整token周期。

成果qwen3/dual_gu、qwen3/results/dual_gu_20261027/REPORT_ZH.md、FINAL_SUMMARY/RAW_INDEX；work/jieruiz/201/ARTIFACT_AUDIT与HANDOFF。科学源2cd6d360不变，b0仅诊断/测试补丁。当前本地最终汇总完成，待更新同一PR202；正式发布以FINAL_PUBLICATION回执为准，不合并、不关闭Issue。旧控制器3200记录已失效，完成依据封存文件，未虚报Slurm历史退出码。无新定时；Projects缺read:project待同步。

## 2026-10-28 Issue201发布回执：PR202草稿，扫描继续

2026-10-28T00:48:34+08:00，身份jieruiz。源码与阶段报告已实际推送到workspace的task/201-dual-gu-short，PR202（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/202）为draft/open、未合并；base为尚未合入的PR174分支。首次发布head98530eaa，九个关键远端blob原字节回读一致，PUBLICATION/REMOTE_VERIFICATION保存回执。Issue201验收项只勾选已通过部分，主扫描及最终三seed对比仍未完成，Projects缺read:project待同步。

Slurm3200_[0-3]保留，不重复提交。18项验证、pilot封存完成；主协议未封存观测及剩余流程见同目录HANDOFF和REPORT。当前不是256拍质量验收、完整WT2、训练或硬件PPA结果。后续收齐四片后运行audit_artifacts.py --write-final，更新同一PR，不另建任务或重跑健康作业。

# Issue201恢复交接

## 2026-10-28 Issue201：仅Wg/Wu双随机短流扫描运行中

负责人jieruiz；task/201-dual-gu-short，目录tmp/dual-gu-issue201-20261027，依赖PR174@b41ee008（未合并）。科学执行2cd6d360不可变；18项CPU/CUDA验证通过（3205仅验证），pilot3199完成。正式Slurm3200_[0-3]健康运行，T32/64/128/256，各固定W、W-IID、联合2D分层三seed。后训练Qwen/Qwen3-4B；Wd固定W8、NL固定四档/联合32 T128、准确SDPA不改，全36层及前缀覆盖。不是训练或PPA。

主协议8×128=1024目标后缀，不是完整WT2。未封存主观察：BF16四片同为13.566049；固定W T64三seed逐值复现PR174。W-IID seed0 T32/64/128/256为77.9953/25.4284/18.1963/16.6126，其他seed/联合待齐，不能宣称256已足够。权重P=abs(W8)/128，无额外量化，独立W源；联合Ka×Kw=8×4/8×8/16×8/16×16，条件二项CDF压缩有数值精度边界，无Gaussian。GU仍FP32恢复oracle，未验收完整bittrue。2cd旧diagnostics front_T/K写死64，顶层gu_samples等为准；b0a仅报告/验证修复，不重跑。

成果qwen3/dual_gu、qwen3/results/dual_gu_20261027；交接work/jieruiz/201/HANDOFF.md，SOURCE/SUBMISSION/COLLECTION及RECOVERY可恢复。旧3197类型fixture失败、3198依赖未运行已取消，健康3199/3200未取消。不重复提交；恢复先收complete.json/documents SHA，再核40物理/37唯一及三seed差异。当前阶段PR待创建，未推送/未合并；实际发布以PUBLICATION.json及Issue201为准。Projects缺read:project待同步，无新定时。更新时间2026-10-28T00:43:16+08:00。


## 不可重复的执行

- 服务器个人项目：/home/Hongjie_Zeng/projects/pbit-qwen3-dual-gu-20261027-issue201
- source-2cd6d360b264；pilot3199、主数组3200_[0-3]。source-b0a87c866640对应3205，仅18项验证。SOURCE/SUBMISSION原件不改，VALIDATION_RESULT解释旧通用回执字段。
- 远程读取用既有lab-server-ai配置（不上传凭据），Slurm命令使用bash登录shell。执行runtime沿SUBMISSION中的sbatch及源包，无临时checkpoint。现场GPU为RTX5090 32GB，每片1卡。
- 初始source574f仅fixture失败，3197；3198依赖永不满足从未运行后取消。FAILURE记录保留，不能将其写成模型失败。

## 接手后具体动作

1. 重读最新Issue201/依赖PR174/本人STATUS，确认没有他人已收完；Git根是本目录，不是a_P_BIT混合资料根。
2. 在本机使用bundled Python运行 `work/jieruiz/201/collect_dual.py`。脚本只读取、保存封存pilot/已complete主分片和日志；未封存观察放COLLECTION。不要再运行submit_dual.py：这会重复提交。
3. 本地收集后运行 `python work/jieruiz/201/audit_artifacts.py`；四片齐全才加 `--write-final`。它不会启动远端任务。若尚未complete，查本人3200的squeue与日志，保留健康任务。完成标准是每片complete.json，status=completed，10case，documents和sidecar原字节SHA全部一致。四片40份/37唯一；36概率配置各三seed，四次BF16只算一唯一。
4. 检查模型revision/权重和tokenizer manifest、TRAIN校准SHA、test/token/target位置SHA、每配置1024目标、all_layer_calls=8与全部36层输入token一致；code2cd，配置SHA246f41e7...。不能仅数JSON个数。
5. 最终按T/方法报告三seed均值/样本标准差、同T固定W的ΔNLL/ΔPPL及相对原BF16；联合方法同时换Ka/Kw需标注，不挑seed。pilot独立、不把GPU模拟时间当电路周期。
6. 原2cd diagnostics front_T/K固定64属显示错误，用顶层字段核实；公开代码b0已修且18项通过，无forward/kernel差异。保留原件，最终汇总显式映射有效配置。
7. 更新同一PR/Issue201、本人STATUS/HANDOFF、长期备忘录和小型索引。当前不合并、不关闭Issue、不建立未请求的自动回查。看板缺read:project待同步。

## 当前证据和限制

18项CPU/CUDA通过，validation.log及SHA见VALIDATION_RESULT。封存pilot32目标完整；主表目前仅未封存观察。当前三seed固定T64完全复现旧PR174，BF16四片一致。W侧独立随机，未测试W共享；GU恢复FP32 oracle，非完整电路bittrue。无RTL/PT/新PPA，无训练。详细报告和输入索引在qwen3/results/dual_gu_20261027。

source三包单份归档project_archives/dual_gu_issue201_20261027，具体绝对路径/大小/SHA见RECOVERY.json；Git保留代码与SOURCE清单，不包含模型、完整数据或大型波形。已提交源码SHA不随报告提交改变。

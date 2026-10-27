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

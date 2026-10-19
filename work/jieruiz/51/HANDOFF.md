# Issue51 新器件LLM质量指标交接

日期2026-10-19；实际GitHub登录jieruiz。目标rayggxia-workspace/pbit-llm-qwen-baselines。

- Issue：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/51。
- 独立目录：C:/Users/86134/Documents/a_P_BIT/tmp/emerging-quality-issue51-20261019；分支task/51-emerging-quality。
- base：pbit-tlm-attention-details-20261016 @c1555ae6594c863011a70845d88c950a68de732b。
- 已完成报告：architecture_tlm/EMERGING_LLM_QUALITY_METRICS_ZH_20261019.md；用户master_report目录有同字节副本。EVIDENCE JSON含14项原文表值及算术复算，非新模型实验。
- 主要结论：5%仅可作为自定PPL工程预算；Kelle有大于5%的PPL操作点，DS-CIM用准确率、UniCAIM用F1、CQ-CiM用检索、SCARLET用token accuracy。指标/基线和应用范围不同，不作跨指标换算。
- VQT-CiM、HEIRS、DBC本次全文质量表未取得，报告明确列出DOI和需核查事项；未引用二手精度数字。
- 无新模型、训练、PPL、TLM、DRAM、RTL/PT/PPA或服务器任务；未动Issue46/48/50的实现或作业。所有数值均为论文转录/复算。
- 实际验证：UTF-8/LF、14项算术复算、2个既有本地链接、正文/用户副本一致；来源PDF五份的SHA仅记录、不上传全文。发布前再核Git blob。
- 准备/核验脚本位于tmp/emerging-quality-preflight-20261019/prepare_delivery.py；来源与正式成果SHA见MANIFEST。
- Projects实际GraphQL返回INSUFFICIENT_SCOPES、缺read:project，未同步看板。
- 下一步：核文档范围后推任务分支PR至TLM base；长期备忘录在独立更新分支向task/28-project-memory提交小补丁，保持唯一主维护文件和根阅读副本不被并行覆盖。实际远端动作发生后补回执。

## 已发生的发布动作

- 主报告两个本地提交16c3459/a07d695已通过GitHub Git Data API逐blob和tree原样上传；远端head为a07d695ce703129635c14fe5bbaec249c3170c1d，与本地一致。Git网络连接失败，改用认证API，不涉及自动审批拒绝或上传范围变化。
- PR53已创建并附当前任务：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/53。实际base已并行推进至bef83e54，PR为mergeable=true、clean、未合并；已避开Issue46的STATUS插入位置并保留其状态。
- 正文SHA256为a542b46cf3750138de91ce7c0b46cbefd6cfa7a291b45d7b27dc413bdfc174d8；EVIDENCE为f6274bea585f2b2f12af2815fd2a4c38d7272f72063954ff54ef791f10963783。14复算、UTF-8/LF、用户副本与正文/EVIDENCE Git blob字节核验通过；独立文档审核未发现发布阻断项，已采纳AFM W16与W4参考区别。
- 备忘录检测到主维护者更新至b347f6af，已在独立目录重放小补丁并保留所有继承文字，不改原维护目录或根阅读副本；补丁发布状态后续追加。Issue51保持开放待审，Projects待权限。
- 备忘录补丁56e417eab5ca30354a1b1f960437f1352e736faa已实际原样上传，PR54已创建并附本任务：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/54，base task/28-project-memory @b347f6af，待审未合并。根副本继续跟随唯一主维护版本，不能将待审补丁称已同步到根文件。

## 论文任务对照补充 2026年10月19日

- 用户要求将任务/指标解释保存成文件，并按论文说明实际使用的任务。沿用Issue51；已核远端PR53实际合并为856105beaefaee307ba1a9b1972aa61d8f82ba59，Issue51仍open。
- 本补充独立目录：C:/Users/86134/Documents/a_P_BIT/tmp/paper-task-map-issue51-20261019；分支task/51-paper-task-map；base为上述TLM merge。没有改旧任务工作树或其他成员文件。
- 正式文件：architecture_tlm/LLM_PAPER_TASK_METRIC_MAP_ZH_20261019.md；用户副本：C:/Users/86134/Documents/a_P_BIT/pbit_llm_master_report_20261012/LLM_PAPER_TASK_METRIC_MAP_ZH_20261019.md；SHA256：6bdf8dc22f3a24b69f2eb8948f32697f25cb1fdd227549c56d92ee313127dbe4。单独TASK_MAP_MANIFEST记录，未重写旧MANIFEST与其已签成果。
- 11主表论文区分9项应用质量与2项工作负载清单；1项图像随机ReRAM补充，3项待全文。不把Kelle Qasper/TriviaQA的泛称Accuracy补成已确认F1，不把ARTEMIS泛称GLUE补成七项。
- 实际验证：UTF-8/LF、表格列数、相对链接、用户副本字节/SHA；逐项主源核对与独立只读审核。模型/数据版本、种子、服务器作业等本任务不适用：没有新实验。
- 命令与准备脚本：tmp/emerging-quality-preflight-20261019/prepare_task_map.py；恢复先核Issue51/后续PR与本分支远端head，再读TASK_MAP_MANIFEST。Git CLI fetch网络失败，但本地共享Git对象已有经API核实的最新base；将用Git Data API原样发布文本提交。
- 下一步：提交限定文件，创建补充PR至TLM分支，核Git blob与用户副本，更新Issue51。Projects权限待同步；旧PR54为备忘录提案，未视为已合并或根阅读副本已更新。

- 补充发布回执：58aaa7ac7c330ab3d6a5ae0d669ed10057fbb24c已通过Git Data API原样上传；PR56已创建并附本任务（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/56），待审未合并。独立复核通过，已采纳CQADupStackGisRetrieval与all-MiniLM-L6-v2的具体名称；最终文档SHA256 6bdf8dc22f3a24b69f2eb8948f32697f25cb1fdd227549c56d92ee313127dbe4，Git blob/本地/用户副本完全一致。

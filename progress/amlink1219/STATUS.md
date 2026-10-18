# amlink1219 项目进度

更新时间：2026-10-19T02:14:44.046675+08:00；负责人amlink1219。

## Issue37：完整数字Attention vs QK概率筛选＋Ising（本地/服务器完成，待PR）

- 目标rayggxia-workspace/pbit-llm-qwen-baselines；分支task/37-attention-comparison；工作目录E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/workspace_projects/ac37。远端base pbit-tlm-attention-details-20261016 @3553996，依赖本地Issue36 d3c6514；执行源7f1cc0d5c3e967f4983727c726b7e1d6e36e7873。
- Slurm2164 CPU1分配COMPLETED/0:0，23源SHA通过，9/9快照测试，32/32完整24层条件TLM完成；无GPU/PPL/RTL。首终态已保存，40返回文件独立SHA核验；服务器/home/Weican_Chen/projects/attention-compare-issue37保留冻结快照与原始结果。无本任务在运行作业。
- 正式代码/报告architecture_tlm/attention_comparison，结果architecture_tlm/results/attention_comparison_20261019，辅助work/amlink1219/37。2K D0完整29.480ms、条件10.057mJ/0.341W；P/S32 27.963ms/8.961mJ，S128 33.038ms/9.495mJ，S512 49.921ms/11.080mJ（三seed均值，100ns，warm，pending32）。全部占位参数条件值，物理完整PPA/PPL为空。
- 2K/S128宏输出周期需约<=17.27ns才在该固定映射延迟上胜过D0；S512只加快宏仍不足。当前P缓冲2K256KiB/8K448KiB，D0仅64KiB，不能从小宏面积推断全模块省面积。8K仅保留6.25%候选，质量未验收。数字screen_exact使用variable候选，不是fixed P的单模块消融。
- 本人Issue37同步实际结果并保持open；当前amlink1219 push=false，分支未上传、PR未创建；Projects缺read:project待同步。获得权限后先复核最新Issue/PR/base，按HANDOFF/PR_BODY只推本任务分支，不换账号/旧库。

## 此前状态（保留）

更新时间：2026-10-19T01:40:28.893502+08:00；负责人amlink1219；正式目标rayggxia-workspace/pbit-llm-qwen-baselines。

## Issue36：完整数字Attention参考（本地完成，待PR交付）

- 用户指定以完整模型PPL增量约束比较完整Attention的延迟/能量/面积；局部NMSE仅诊断。已把口径补入AGENTS，保留原规则。
- 工作目录：E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/workspace_projects/pbit-digital-attention-issue36；分支task/36-digital-attention-reference；base pbit-tlm-attention-details-20261016 @3553996。执行源a4f19659922b26db89c662f5c6d90cf1136bcf8c，后续文档/交付提交见git log。
- 正式代码/报告architecture_tlm/digital_attention_reference；结果architecture_tlm/results/digital_attention_reference_20261019；辅助work/amlink1219/36。本地10/10解析测试通过、3上下文运行成功，独立审阅通过。未做新模型/GPU/RTL/DC/PT。
- 参考为BF16/FP32分块在线Softmax，GQA复用；2K完整132120576MAC、KV24MiB/weights84MiB。16GB/s主SRAM两pass下界14.155776ms，不是实际延迟。宏面积0.5316195528mm²、主流式内部能量0.169958493mJ是局部项；完整PPA为null，缺计算/非线性/寄存器/接口/DRAM等。
- 文献Zotero新增1/复用3，托管PDF已回读SHA；既有BF16 PPL11.652735仅作质量锚点。无新D0有限字长/8K PPL。
- 实时核验amlink1219/id75301230，目标仓库id1420564659，pull=true/push=false/triage=false；没有推分支/建PR。Projects实际缺read:project，待同步；本人Issue36同步摘要并回读，保持open。接续先读最新Issue/PR/base；取得同账号权限后按HANDOFF/PR_BODY发布，不换账号或仓库。

## 此前任务状态（保留Issue35快照）

更新时间：2026-10-19T00:58:24.860054+08:00；负责人amlink1219。正式目标rayggxia-workspace/pbit-llm-qwen-baselines；本地工作目录 `E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/workspace_projects/pbit-attention-issue35`，分支task/35-attention-e01，PR base pbit-tlm-attention-details-20261016 @3553996。

## Issue35：Attention E0/E1 实际执行

- 代码执行源879050031ac1cc7757e3b7f54e19c25dc40faf72；Slurm2159漏fixture失败保留，2160 CPU39/39通过，2161完整BF16 PPL11.652735047455899/299077目标与原值相等，真实QK/V捕获无扰。2162 pilot12/12、2163 full465/465均完成0:0，无错误或超时；当前无本任务运行作业。
- 正式代码experiments/attention_e01；结果qwen/results/attention_e01_20261019；本人辅助/交接work/amlink1219/35；服务器/home/Weican_Chen/projects/attention-e01-issue35。大trace与每case数组留该目录，仅回收小型记录和SHA。
- 本轮数值结果：当前三个真实行的M2048/S128，数字systematic的V NMSE均值均低于串行Ising；有限输入/seed，不是全模型PPL或器件优势证明。无RTL/PT/TLM或物理随机源验证。
- 本地完成、服务器实际完成、本人Issue35结果摘要已同步并回读；push=false、triage=false，分支未上传、PR未创建，Projects待同步。不得冒称远端代码已交付/已合并。下一步在获得权限后核对最新Issue/PR和base，显式推本任务分支并建PR，回读提交/结果SHA。

## Issue33：此前计划

- 调研与623行总计划在独立工作目录pbit-attention-issue33、提交e1e564d；尚未推送。Issue35仅实现并执行其中有限E0/E1范围，不代表整个计划完成。保留该任务原进度/交接，不覆盖它的分支。

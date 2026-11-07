## 2026-11-06 Issue225：1216KiB SRAM本地候选已实现并初步验证

用户要求落实Attention缩容并尝试约1.2MiB；已读取198的SRAM64方案（此前只有文档），在新adapter实际映射全部transfer/直接读/DMA回填；八组各64KiB，640数字池两个80KiB槽，激活区128KiB，GU96/CIM256/norm32/DMA32保持，合计1216KiB=1.1875MiB、304个4KiB/1RW宏（前端176+Attention128）。没有保留旧488个端口。旧198/204/225执行源和在跑任务只读。

8项CPU检查＋三配置完整形状一层机制回放通过。解析外存和合成600拍/查询采样时序，1952/1440/1216KiB为1.14172/1.14457/1.16366ms，+0/.250%/1.922%；关键计算actions和外存128907264B一致，SRAM读词4038373/4038373/4038238，写均8645664。不是原生LPDDR、完整token/PPL或新PPA，不能声称所有SRAM动作不变。

按已有宏价覆盖面积57.573748→52.621712mm²；条件50ms计价片上24.133492mJ/.482670W，含4pJ外存197.297987mJ/3.945960W。存储小37.7%不等于动态能量同比降低。新增译码/互连PPA未标定，完整新组合同样未测TPOT。

EDA首次脚本语法失败后修复，后续SSH执行通道连续超时；只读恢复检查无对应快照/任务，没有成功作业号。用户随后确认服务器故障，要求本地初估；本轮停止EDA重试，不等待远端，不创建自动化。后续原生计划仅待办，恢复先核查PREPARED/回执，不能盲目重交或误报仍在运行。

正式architecture_tlm/sram1216_20261106/README_ZH.md及RESULTS/BUDGET_ESTIMATE/DEPENDENCIES；本地原件project_archives/sram1216_225_20261106/LOCAL_SYNTHETIC_SMOKE.json及只读14文件依赖。交接tmp/norm-stream-issue225-20261106/work/rayggxia/225/sram1216/HANDOFF.md；Issue225/PR248保持原任务，发布以PUBLICATION.json为准。根正式目录同字节阅读镜像。

---


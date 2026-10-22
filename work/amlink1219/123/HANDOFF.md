# Issue123 交接

Owner amlink1219；任务分支 task/123-full-ffn-ppa，发布基线 PR122@8007d98。用户要求核对116并接合完整FFN；随后明确将STA/PPA执行交给jieruiz，先上传任务文件并@他。

当前里程碑：CPU-only2777已捕获真实896→4864→896 layer0/context64最后token的全部权重、输入、残差。派生权重41,405,784B只在本人服务器；索引见capture_2777/MANIFEST.json。CPU-only2778通过45RTL配置/种子场景、11667输出、180reset flush，18源SHA已核。不是STA/PPA或PPL。

PPA执行交接：[HANDOFF_JIERUI_ZH.md](../../../architecture_tlm/encoding_restore_contract/ppa/HANDOFF_JIERUI_ZH.md)。模块/位宽/DEPTH/完整动作单位、准备命令、实际DC→门级精确oracle→PT门禁及回填模板在该目录；未运行licensed EDA。用户授权的@通知在Issue123发布后执行，不变更107负责人。

116仍在独立工作树活跃开发。902c49b的restore_rounding已复用，未重复其数学修复、kernel、memory、Attention/native RNG和crop/reduced-layer任务。接合代码在独立fi23-int准备，完整组共享、逐output恢复和cross-k信用验收中；未发布116代码，不声称正式后端已合入。后续发布commit/源hash和最终验证另附。

上传状态以PUBLICATION.json和远端ref为准；不自动合并。当前2777/2778均COMPLETED/0:0，无GPU任务。完整FFN仿真尚待提交。Projects缺read:project需有权限者同步。

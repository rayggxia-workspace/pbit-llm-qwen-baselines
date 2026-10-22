## 2026-10-22 随机源统一操作模型与核心RTL（Issue95 / PR97）

用户要求准确操作统计、基础LFSR/共享扩展/非LFSR后端、启动新种子与慢速换种，并由用户自行仿真PPA。本轮实际GitHub连接器身份rayggxia，独立task/95-rng-service-rtl、tmp/rng-service-issue95-20261022，基线83e15289434af50fc09c35e699d8b39965389d98。源码提交970260e21ebcf98822b9cf47b643fb8360a31e2f已发布PR97，开放待审未合并；Issue95继续open，Projects未核实/待同步。原生Git本机连接失败不影响连接器已发布事实，本地/远端状态以work/rayggxia/95/PUBLICATION.json及最新远端head为准。

入口architecture_tlm/random_service/：LFSR32 1×8bit、现有GF扩展64×8bit、Bivium177bit状态/160bit展开20×8bit；端点/种子入口Python与7份SystemVerilog，统一valid/ready、q/256阈值、响应保持、SAVE/RESTORE/RELEASE。默认1亿拍换种（10ns约1s），0仅启动；每端点每epoch独立取得新总线材料，无免费根种子派生或固定种子回退。LFSR每次32bit、Bivium192bit总线包保留177bit并明确丢15bit，预热5拍。FFN锁定重放时延期记账；无源不输出。OS/fixture/有来源trace严格区分，软件OS不宣称物理熵。操作数/总线/等待分开，PPA null。

现有parallel_sampler_v5.py只加可选计时源适配，旧理想默认保留；26个Bivium可供512路帧（额外8路收费），公平辅助另端口。核心与入口逐周期不等于整个Attention/互联RTL周期精确。GF64总秩32、两两秩16，不保证64路联合/跨时IID，Attention默认拒绝。概率LUT量化改变目标，未继承旧PPL。模拟读出、健康调理、CDC、共享仲裁器和sigmoid LUT完整RTL仍缺，记录DESIGN_QUESTIONS_ZH.md；优先综合top/活动场景见POWER_SIM_ZH.md。

47项Python检查通过，3后端×3seed×900=8100沿及连续活动6000沿逐沿一致，FFN250沿120帧通过；便携包独立19检查/fixture示例通过。有限3seed统计诊断不等于质量验收；没有DC/PT/PPL/GPU/Slurm/新Spectre。包远端上传/rng_service_v1_20261022.zip，SHA7b067edb8dfd452242830ac6f01c068d6200e76ae0d9a0711f2ab4a9097c8f45；原始验证ZIP在project_archives/rng_service_issue95_20261022/verification_raw.zip，SHA684e69f452933b05abaeafab8963f26367c313015940b49208facee2cc6d3524；失败/成功记录按成员SHA保留，PR待审保留最小工作树，不重复旧实验。

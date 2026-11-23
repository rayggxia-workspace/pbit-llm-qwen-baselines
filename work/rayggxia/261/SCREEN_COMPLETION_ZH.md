# Issue261正式筛选完成交接

2026-11-23；rayggxia；分支task/261-ffn-address-coverage；PR262，base main。

9配置×3seed，共27个completed封存结果，8窗口/9215目标/36层计分覆盖和
模型/代码/数据/目标位置SHA通过。6112无合格候选，未提交完整WT2。

正式结果：experiments/ffn_address_quality_20261122/SCREEN_REPORT_ZH.md。
原字节小型摘要、AUDIT和VALIDATION：同目录results_screen_20261123/。
重核脚本：audit_completed_screen.py，传入已授权存储中的RESULTS.tar.gz。
该包SHA为e010003550efce82b26b6918c79c44e512df4fda76ca13177f163293a9d83175。

原T64 PPL9.1849/地址99.7896%；概率减半PPL9.8190/99.5164%；读取节省不足。
低地址预算方案严重退化。没有新训练、完整WT2、RTL/PPA或TLM结果。
冻结执行a9d9af6a494d、控制896fe5515afe保持；无需重跑这些已完成任务。

PR待审未合并；Issue不自动关闭，Projects待有接口维护者同步。
下一步审阅负结果和新的方差控制候选；正式长期备忘录交Issue28维护者集成。
私有迁移记录与全部历史STATUS不包含在本次精简发布中。

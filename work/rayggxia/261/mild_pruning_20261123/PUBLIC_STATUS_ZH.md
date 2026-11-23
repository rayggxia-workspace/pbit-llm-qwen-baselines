# 温和剪枝执行交接

2026-11-23，rayggxia；Issue261 / PR262；task/261-ffn-address-coverage，base main。
仍复用原独立任务目录，不修改其它成员工作。

用户授权温和GU剪枝后继续原P-FFN采样。5配置×3seed的8窗口筛选全部完成：
未剪枝、纯输入10%/20%、输入×GU范数二次幂近似10%/20%；阈值只用训练集校准。
原T64 PPL9.18494±0.08847；范数20%实际剪去18.088%，PPL9.18258±0.04167，
所选GU payload相对减少17.915%。未训练、未跑完整WT2，不称整机能效或显著提质。

6129门禁/校准通过，6130数组15项全部completed封存，代码/模型/语料/目标位置/
36层与字节账核验通过。执行c72597f5d439，复用a9d9af6a494d，准确源码包和manifest
在本目录。正式报告experiments/ffn_mild_pruning_20261123/REPORT_ZH.md及results/。
源码包SHA8d316cf300470b409f356c0b3ea56469ef2cc2dff90690a7eb30da0872838c11；
原结果包SHAa6c4dd7c4c50d20e15dafdd4adec665c89114eaf7aca6c1f9130a74eb1f0d139。

完整本机STATUS/HANDOFF继续维护；历史内部元数据不重新上传，远端以本精简交接
和Issue/PR记录同步。新服务器运维资料及校准向量不公开。原27项地址抽样负结果
保持，不重跑。下一步完整WT2验证主候选及配对基线；PR待审未合并，Projects待维护者。

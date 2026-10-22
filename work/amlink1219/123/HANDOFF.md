# Issue123 交接

Owner amlink1219；任务分支 `task/123-full-ffn-ppa`，[PR125](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/125) 待审，未自动合并。用户要求核对116并接合完整FFN，随后明确将STA/PPA执行交给jieruiz，先上传文件并@他。

已核对116新发布的PR126，固定head `160f46e0b63bdf94499e2434dc35e09f44fc2fcc`；编码合同固定PR122@`8007d98f15676ad316180ee18b5d1b29aa00af95`。两个依赖均待审。本任务分支已合并正式后端，新增可选 `pr122_b4_fused0` 路径，legacy默认不变；未修改116开发工作树。Issue124/PR127负责短投影资源实验，本任务做完整FFN和EDA交接。

正式源在 `architecture_tlm/cycle_v1/ffn.py`、`ffn_contract.py`、`ffn_contract_reference.py`、`run_contract_ffn.py` 和 `test_ffn_contract.py`。helper与复现补丁入口为 `architecture_tlm/ffn_cycle_integration/README_ZH.md`。逐输出恢复/跨k加法、共享组编码和有限信用有独立数值、trace和存储验收。

已完成：CPU2777捕获真实896→4864→896 layer0/context64最后token fixture，41,405,784B派生权重仅在本人服务器，索引见 `capture_2777/MANIFEST.json`。CPU2778通过45RTL场景、11667输出、180reset flush，18源SHA已核。正式后端执行归档的28项测试通过，日志在 `ffn_2783/TESTS.txt`。小完整链原件及失败保留复核在 `architecture_tlm/ffn_cycle_integration/results/smoke_20261023/` 和 `reviews/`。

完整T32运行CPU-only **2783** 已提交，执行源commit `7d3b45001b48e20d39d49237a5575b0d7b487ca5`（独立集成树，父基线PR126），实际52源字节绑定 `ffn_2783/FFN_SOURCE_MANIFEST.json`。路径 `/home/Weican_Chen/projects/full-ffn-issue123-20261023/revision4`，预计输出 `ffn-results-2783/summary.json`；日志 `ffn-2783.out/.err`，Slurm2CPU/24G/90min、CUDA_VISIBLE_DEVICES为空。当前尚无完整形状通过结论。恢复先查询2783及保存的receipt，不重复提交。2779为补充耐久证据而主动中断，2780为采用经验证的主机优化而主动中断，两者CANCELLED/0:15；保留原件，不计成功。

PPA执行文件：[HANDOFF_JIERUI_ZH.md](../../../architecture_tlm/encoding_restore_contract/ppa/HANDOFF_JIERUI_ZH.md)。已上传并在 [Issue123评论](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/123#issuecomment-6348504716) @jieruiz，请其先SS/T32，再SS/TT全矩阵；模块边界、命令、严格DC→门级oracle→PT门禁和回填模板均已给出。实际licensed EDA未运行，物理PPA保持null，不更改107负责人。

下一步：观察2783终态并立即保存调度证据；取回小型summary、manifest和日志并核SHA，原始trace/阈值/派生数据保留服务器。完整通过后再登记数值/周期结果；单token单层不是PPL，声明周期不是STA，主机加速不是硬件加速。更新PR/Issue和台账，不自动合并。Projects已核缺read:project，待有权限者同步。

上传状态以各次PUBLICATION/REMOTE_VERIFY回执及远端ref为准。历史回执标记其当时head，不代表最新工作树；上传不等于合并。

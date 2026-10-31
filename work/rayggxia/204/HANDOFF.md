## 2026-10-31 Issue204：8位比较器共享LUT对照完成

PR219，task/204-gu-unified-code，base task/206-group64-scale；科学结果26c4dd72613c9c44e9514d2d7df7c455b2b74c56，待审未合并。6配置、66PT，RTL/门级各13614逐拍PASS；本轮作业38475917/38475945全部结束，无需重跑。N64/M8/T32，所有比较器主体8位；full34拍，共享单银行增加32拍准备，共66拍。

weighted全LUT/共享CE/共享ICG为436.6733/724.02/566.61pJ/8输出帧，55eq面积.1100728764/.0982922364/.0978630012mm²；OR4对应458.8867/797.06/639.562pJ和.0831721932/.0713918448/.0709626096mm²。面积raw×.81一次。LUT原本仅16.5pJ；共享主要省面积，当前冷启动能量增加。门控检查非负，weighted setup仅15.3ps且功耗模型告警保留，未物理签核。

结果及源码入口：architecture_tlm/nonlinear_wd_shared32_20261031/README_CURRENT_ZH.md；统一run nonlinear-shared32-204-20261031。48记录发布元数据check/render通过；相对路径及SHA保留，绝对地址在完整本地台账。无新GU/SRAM/随机源/跨K/BF16/PPL。后续仅审阅与真实活动/重叠方案评估；恢复凭本地work/rayggxia/204/shared_sigmoid/PUBLICATION.json，不新增昂贵实验。


此前状态与交接原文保留于[上一版本](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/747764cfe44ba5eb816832829ebea264c66cd460/work/rayggxia/204/HANDOFF.md)；本页仅列本轮当前状态。完整本地历史未删除。

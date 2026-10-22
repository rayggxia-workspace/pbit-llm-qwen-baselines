统一整机TLM源码已交付 [PR99](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/99)，draft待审，未合并。冻结源fba22b192ab914046e50cc405f6dd473bf30d154。21项新机制检查、18项已有采样器与10项v4回归通过；三模型导航anchor/dry-run通过。

Qwen2K/8K各8方案×3seed的48项整机情景在本地CPU执行；Llama1/2完整32层各数字BF16＋SC/PV两项已完成。源码/执行/结果分开封存，没有新PPL/训练/PT或DRAMSys实跑。原门禁W8元数据越界已修复，失败原件保留，不混入最终结果。

默认本地随机接口无随机流SRAM/FIFO/额外概率副本；FFN分层共享/重放与Attention候选独立提议语义单列，后端继续Issue95。完整物理能量/面积与新组合PPL仍null。下一步汇总并核验完成批次、上传报告/STATUS/HANDOFF；不接管37/78/95，不自动合并。

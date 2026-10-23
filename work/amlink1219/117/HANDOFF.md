# Issue117 ASIC资源优化交接

负责人amlink1219，正式目标rayggxia-workspace/pbit-llm-qwen-baselines。独立工作目录workspace_projects/ar117，分支task/117-asic-resource-optimization，base集成46804fb。PR base pbit-tlm-attention-details-20261016。

2026-10-23最终执行状态：208项新完整decode TLM全部完成，128项共同候选粗筛＋64项预声明代表点补充＋16项vector128跟进。五个代表点均有四方法、2K/8K、seed0/1/2，另外11个候选仅seed0；本任务没有仍在运行或待补case，没有Slurm/GPU任务。模型、tokenizer、语料不适用：未做LLM数值推理。

正式入口architecture_tlm/resource_optimization_v1/README_ZH.md、RESULTS_ZH.md和P0_RESULTS_ZH.md；机器汇总/验收在results/analysis_20261023，P0账本在results/p0_20261023。原始输出分别在results/coarse_20261023/shard_0..3、results/confirmation_20261023/shard_0..3、results/vector_confirmation_20261023/seed_1..2。保存的CONFIRMATION_SELECTION.json记录四个预声明代表点；CONFIRMATION_EXTENSION.json明确vector128是看到seed0正向时延后的跟进，非盲测质量验证。

执行提交：粗筛44dbbbdbc2720963b2b24bf03cdf7582a2d97075，首批补充315862412e15695c3fa21e6c573d9e5f3547e70d，vector128跟进b1b4d183678e25f24b7b37c273fcb3f61c37483b。十份EXECUTION.json的数值/调度源SHA集合均为cc1568efcd6cc8d192235271b16a7f20f216abb8395b99ca48d7bda3cbc5fb80；每case配置、原字节和receipt独立核验。恢复不能只因HEAD变化放宽--resume检查；本轮已经齐全，先读VALIDATION.json，不重复提交已有case。

验证：71项测试通过（28新增＋43原v6）；原52＋40封存情景145payload SHA未变。verify.py验收208项完整键集合、配置/源/receipt、全336query、相位/资源/容量守恒、24容量only配对和7个新基线锚点。主要结果：只扩容量无收益；同1MiB重新分块小幅改善；vector128下SC筛选/PV三seed均值在8K比同配置W8快7.543849%，2K仍慢4.166733%。这仍是合成事务条件TLM，完整面积/能量/A0和同配置质量未知，不做完整同面积排名或SC普遍优势声明。

从仓库根目录独立重汇总/核验，NEW_ANALYSIS须为新目录；这些命令不启动新仿真：

```sh
python -X utf8 -m architecture_tlm.resource_optimization_v1.summarize search --inputs architecture_tlm/resource_optimization_v1/results/coarse_20261023 architecture_tlm/resource_optimization_v1/results/confirmation_20261023 architecture_tlm/resource_optimization_v1/results/vector_confirmation_20261023 --output NEW_ANALYSIS
python -X utf8 -m architecture_tlm.resource_optimization_v1.verify --inputs architecture_tlm/resource_optimization_v1/results/coarse_20261023 architecture_tlm/resource_optimization_v1/results/confirmation_20261023 architecture_tlm/resource_optimization_v1/results/vector_confirmation_20261023 --expected 208 --output NEW_ANALYSIS/VALIDATION.json
```

本批执行与独立审阅全部完成，最终交付通过PR119；准确上传head及远端回读以PUBLICATION.json为准。统一台账已登记asic-resource-117-20261023，归类CALIBRATED_ESTIMATE，check/render及8项台账测试通过，不能写成RTL/PT实测。PR待审未合并，不自动关闭Issue117。Projects缺read:project，待补看板同步；历史指定本机阅读镜像C:/Users/86134/Documents/a_P_BIT/digital_circuit_simulation_registry不存在，未同步。PR120另有独立新记录，合并时须取两条记录并集后重建总览，不能互相覆盖。

后续P1先对接并行PR120/Issue118提供的FFN供数与逐档整数局部状态合同（当前待审、未纳入本轮），落实真实恢复latency/II、权重保持与有限出口，再接Issue116周期后端。新KV驻留/缓存、恢复RTL、同总面积锚点和DRAM物理校准仍未完成，不重复或覆盖两个并行任务。

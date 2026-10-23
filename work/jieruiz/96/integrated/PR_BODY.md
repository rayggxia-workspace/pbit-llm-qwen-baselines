FullDecode此前只接了足量本地源接口，新版默认使用Issue95真实有限随机服务，计算核、SC消费、随机端点、采样器和种子总线统一100MHz，SRAM保留已有SS宏支持的80MHz。

FFN通过SAVE/RESTORE/RELEASE重放同一输入组的T32/K32序列，源与矩阵计算流式重叠；筛选、PV和两个并行采样器真正消费持续存在的Bivium端点输出，计入宽度、种子包、预热、换种延后和回压。原Issue95模型/RTL没有修改。100MHz端点PPA只对原生端点做有条件active/idle回填，避免再叠加前端或原整宏的重复价格。

- 完整模型验证40/40、0失败；包含Qwen24层2K/8K、筛选PV三seed、Llama1/2完整32层及新旧接口配对。12项赢家/拒绝S8是整机连通诊断，赢家倍率1，并非默认全预算质量。
- 93项机制/回归检查通过；1421项源/配置/成果SHA、全层覆盖、时钟、种子、帧数、重放和互斥收费检查通过。96个封存artifact的已提交blob字节与manifest一致。执行源31aa4fa31fbfb7d74629b54811936ac30a41c250。
- 旧52项不改。宽扫描104项在0完成/0失败时主动取消，保留计划和取消原因；完整pilot独立封存，均不混入40项。

[实际接入设计](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/task/96-unified-tlm/architecture_tlm/unified_v6/RNG_INTEGRATION_ZH.md) · [结果、周期和PPA边界](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/task/96-unified-tlm/architecture_tlm/unified_v6/RNG_INTEGRATION_RESULTS_ZH.md)

实际验证入口：`python -m unittest architecture_tlm.unified_v6.test_rng_integrated -v`、旧整机/接口/源/采样器回归、`work/jieruiz/96/integrated/check_extra.py`及`audit.py`，完整日志/manifest在同目录。原deferred-age修正、Windows临时目录环境重试和取消扫描均留痕。

限制：全部是合成路由的完整decode事务模型，不是权重推理或整机周期精确认证。新q/256响应未获得模型PPL；普通512MAC/64向量/16非线性吞吐与部分前端/恢复/互连仍是假设或未标定。完整随机及整机能量/面积保持null；默认Link外存，本次没有新DRAMSys、GPU/Slurm、RTL/DC/PT/STA。旧检查台52项快照不自动刷新。

Refs #96, #95。沿用原任务分支和PR，等待评审；不自动合并、关闭Issue或改动他人快照。Projects仍缺read:project待同步。

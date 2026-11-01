**DMA后续增量：保持100MHz/8MiB，8通道入口＋有限DMA扩展＋权重tile排布，单层5.418→1.591ms；见[dma_expand报告](dma_expand/REPORT_ZH.md)。下方旧配置/旧结果保留。**

**时钟版本更新：新共享后端默认`chip100`，片上统一100MHz；本页原v2/v3数值属于`legacy_mixed`旧混合时钟，原表保留。见[统一100MHz配置与结果](clock100/REPORT_ZH.md)。**

# unified_v6共享存储后端（Issue227）

[中文结果与能耗审计](REPORT_ZH.md) · [机器可读结果](results/RESULTS.json) · [旧存储账复算](results/STORAGE_ENERGY_AUDIT_ZH.md)

这是既有unified_v6的可选后端，原默认模型保留。代码在同级`../unified_v6/shared_memory.py`和`shared_decode.py`。

```powershell
python -B -m unittest architecture_tlm.unified_v6.test_shared_memory architecture_tlm.unified_v6.test_shared_decode -v
python -B -m architecture_tlm --shared-memory --backend analytic --layers 1 --no-lm --out <新输出目录>
python -B -m architecture_tlm --shared-memory --backend dramsys --binary <bounded_async_v1桥> --dram-config <DDR4_OFFICIAL_POWER.json> --input <representative.json> --out <新输出目录>
```

`analytic`只有功能/时间代理，无DRAM能量，不作为DRAMSys结果。真实后端要求已有`bounded_async_v1`请求/完成桥；桥/配置/输入身份见任务EXECUTION_INDEX。标准DDR4控制器不由Python重新猜测。

可控消融：`--serial`整描述符返回屏障；`--staging`增加一次staging写/读/目标写；`--no-cross-prefetch`关闭跨阶段预取；`--return-banks 16`复现狭窄返回FIFO；`--ffn w8`数字W8 FFN隔离对照。默认8MiB、512个128bit单端口bank、100MHz；GU16/NL256测得100MHz合同，普通矩阵2048MAC/500MHz合同。不是全芯片STA或完整PPA。

事件输入格式：`rows`为3场景×8KV组，每行`dimensions`（32索引）与`candidates`（128索引）；`queries[seed][group]`为3场景×4queryhead，每个查询给`duration_ns`及`events=[时间ns,候选下标,次数]`，每头总64样本。候选/采样事件不由本TLM重新计算；原输入只在授权服务端和归档，公共Git仅记SHA，不发布本地未公开交接fixture。无输入时只用于合成机制检查，不能冒充真实模型事件。

没有模型权重、tokenizer或语料执行；模型revision只定义形状，不继承PPL。32头/8KV头、head_dim128与K128/S64为本轮显式合同，不自动等同于训练K256版本。8组共用一个DRAM时间线；QK特征/候选读取和重复V合并按地址发生。

随机供给保留逻辑需求计数/可用供给宏接口；不在SRAM存完整随机流，不把比较次数当完整PRNG个数或器件能量。CIM权重驻留期间不每采样从普通SRAM重读；实际定制读出外围/局部保持仍需单独表征。

重新汇总：

```powershell
python architecture_tlm/shared_memory_20261101/build_report.py --root <本checkout> --workspace <含project_archives的本地根>
```

不重复提交已有Slurm作业。任务工作目录的deploy.py仅负责授权服务器上的冻结打包、提交、状态及原字节SHA收集；先读HANDOFF。新结果继续同目录追加，不另建互不相通预算。

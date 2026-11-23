# Issue261：真实FFN地址覆盖（2026-11-22）

已训练100M的Qwen3-4B T64/strat64，只读捕获第一个WT2 2048窗口、36层×16位置，每种信号576个完整向量，GU2560/Wd9728维。整窗logits逐位不变、9项历史切片核对通过。GPU6094约282秒；CPU6096仅启动路径失败，6099复用原分析快照完成；无遗留作业、无新PPL/训练/RTL/TLM。

理想IID categorical有放回地址采样、p∝输入幅度×真实W8解码权重范数时，K128唯一行覆盖GU4.71%/Wd1.26%；若必须命中即搬连续64行整组，则GU94.88%/Wd53.19%。K512逻辑行16.62%/4.66%，64行组约100%/91.18%。仅输入幅度概率的曲线接近。结论是行级并集尚稀疏，而粗组搬运很早稠密；64行组是条件布局，不是现有DMA实测。每地址一次与旧每拍多路Bernoulli不等价，不能由覆盖率继承旧PPL或声称节省整机能耗。新地址分布没有压成P8硬件阈值，P8只指输入信号接口。

入口experiments/ffn_address_coverage_20261122/REPORT_ZH.md；实现coverage.py、三seed核对和原始SHA在results/RESULTS.json。原始张量仅私有服务器ffn-address-coverage-issue261-20261122/result/capture.npz，SHA8213fdd53b66b9dded08e9e70a2fd4d2c2cd53e32f47c93d0d2c7b7ac7031c37。分支task/261-ffn-address-coverage；实际发布状态查work/rayggxia/261/PUBLICATION.json，勿称已合并。正式备忘录由Issue28统一集成此条，不覆盖现有并发更新。

用户随后要求明确DRAM布局和先采样再读取的执行过程。新增ADDRESS_SAMPLER_AND_DRAM_PLAN_ZH.md及CPU参考：整数幅度质量树→地址/次数表→按输出256/512分条、条内原输入连续的W8布局→保留原64×64权重PoT尺度→精确count脉冲重放。新10项及原5项CPU检查通过，旧19文件归档SHA未改；未获得新PPL/TLM/PPA。旧并行Bernoulli T与新全向量地址数S不是同一预算。Wd需明确真实AND计数/再采样或事件选择，不能用理想z_p8mean免费驱动。TEAL稀疏全部七个矩阵但不稀疏LM head，Deja Vu靠提前预测/索引融合；可借鉴布局与流水，不把未处理部分当作不可变下限。详见PLAN_VALIDATION.json与同一PR262的增量发布回执PLAN_PUBLICATION.json。

2026-11-22用户明确授权T64训练权重的GU-only小规模PPL：新增experiments/ffn_address_quality_20261122，先真实CSR选址/次数，再只加载所选W8 bank，按原tile尺度精确累计/恢复；后级P8/LUT/AND/Wd和Attention保留。6106功能gate与全36层/2048logits no-op、6107九配置独立恢复检查通过；6105仅launcher失败保留。6109/6110/6111三seed9配置8窗口已提交，6112按completed JSON/SHA选择<=2个全WT2候选；质量<=5%优先/<=10%上限，且地址减少>=5%，否则不扩大。snapshot a9d9af6a494d、control896fe5515afe；本人服务器项目ffn-address-quality-issue261-20261122，详见新HANDOFF和SUBMISSION_INDEX。

重要纠正：此前很低的唯一行比例来自归一化单地址法，不是原P-FFN。现有单窗口seed101完整36层pilot中，原64/64分层GU地址99.79%，÷2仍99.52%；cat64约2.44%但PPL从8.0665升到约338.7万。只是单窗口pilot，正式8窗口三seed未完成；不能继承旧T64质量、不能把纯读取比例当整机能效。无新训练/TLM/RTL/PPA，main默认不变，PR待审未合并。

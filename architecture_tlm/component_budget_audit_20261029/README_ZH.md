# 原整机TLM功耗面积时间分项

Issue [210](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/210)，负责人rayggxia。固定原PR192的36层、500MHz目标、32个SC tile、2048 MAC/拍、8MiB SRAM、HBM时序候选，分解已有预算；不修改TLM、不启动新仿真。main默认仍为PR190，不能把本候选说成默认或已实测整片。

先看 [六页Word报告](results/REPORT_ZH.docx) 或 [完整中文表](results/REPORT_ZH.md)。三seed平均57.445385ms/token；已价片上144.544740mJ/token、2.516212W；原面积192.738839mm²，按0.81一次折算156.118460mm²。这里数字90%空闲动态消除为情景，500MHz为每拍能量外推。外存354.211677mJ只为64pJ/B＋50mW粗预算，不是有效HBM功耗表征；完整校准整机仍为null。

片上能量：共享MAC48.10%、FFN计数与恢复34.72%、片上SRAM和缓冲14.74%。面积前列为计数器、共享SRAM和MAC。阶段时间：FFN25.210ms、QKV/O16.357ms、Attention核心8.952ms、lm_head6.816ms，其余0.111ms。阶段可相加；资源忙时存在重叠，不能相加。

## 文件与口径

|文件|作用|
|---|---|
|results/MODULES.csv|14个物理账目，能量、同TPOT平均功率、raw/55nm等效面积、占比、已价边界|
|results/PHASES.csv|16个可相加端到端阶段|
|results/SERVICE_BUSY.csv|24类不可直接相加的资源／服务忙时|
|results/FUNCTIONAL_MAC.csv|5项功能MAC数及有效动作增量，共享MAC背景另列|
|results/DRAM_TRAFFIC.csv|外存物理事务字节和旧能量代理|
|results/ACCOUNTING_GAPS.csv|请求功能与原账本映射、合并计价、转换和Ising等缺项|
|results/BREAKDOWN.json|完整精确数据和6项闭合检查|
|results/SOURCE_MANIFEST.json|原输入、manifest、配置引用和定价代码SHA-256|
|DELIVERY_MANIFEST.json|本次小型派生交付文件原字节SHA-256|

入口SNG含64比较器，NL端点也含比较器；没有匹配独立价，不能拆出假精确数字。输入/g/u定点编码、部分FP32/宽定点→BF16及控制有时间但未独立定价。原Attention为筛选＋准确Softmax＋PV采样，未用Ising；不把新Ising或双随机结果拼进原总数，不把未启用说成零成本。

SRAM宏已有依据，但CIM全并行读出外围、互连、CTS及有效HBM能量未闭合。数字门控/500MHz、B7外推、恢复代理分别标注；同一共享阵列和归约动作不重复计费。无新电路run，因此不另建数字仿真run台账；原电路索引仍从既有ANCHORS和统一台账读取。

## 复算

Python标准库即可重建科学表；不要覆盖冻结原件。

```powershell
python architecture_tlm/component_budget_audit_20261029/derive.py --repo . --out /path/to/new-results
python -m unittest architecture_tlm.ppa_recalibration_20261027.test_rebudget -v
```

Word重建另需python-docx；本次使用Codex捆绑runtime，Word原生导出PDF并逐页检查六页。PDF/PNG仅作临时QA，不入库。

```powershell
python architecture_tlm/component_budget_audit_20261029/make_docx.py --input /path/to/new-results/BREAKDOWN.json --output /path/to/new-results/REPORT_ZH.docx
```

对四配置×三旧能量情景逐字典复算一致；6个completed摘要原字节和manifest/配置引用已核对，raw轨迹仅核对封存SHA引用，未重新下载大轨迹/门级原件。8个原会计单测通过。形状事务不运行模型，模型/语料SHA与PPL不适用。Word再次打包时间或排版环境可能改变文件字节，本次原字节以DELIVERY_MANIFEST为准。

源main基线787489192ebfcdb61ad72edde406818f450aa3dc；原PR192科学head91f68416acad0e8306b920b1b8ac779f3d24ad98。新本地端口结果只有单层＋词表，不能把其18%提速或原2.52W直接套成新36层结果。

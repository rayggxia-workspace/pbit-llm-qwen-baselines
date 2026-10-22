# 第五轮PR审核与实际合并（2026-10-22）

本轮按用户授权审阅82/83/85/86/88，并重点审查“局部模块进入仓库”与“完整组合已验证”的区别。5项均按各自可独立验收范围通过，报告PR另计。实际账号jieruiz，正式分支pbit-tlm-attention-details-20261016。

|PR|审核head|实际merge|范围|
|---|---|---|---|
|[#82](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/82)|`4677ca8b7efd2d9566ef009c30c50f2de12a88c2`|`5455e3152b172480b20b5c0ebe1cc17804c93994`|驱动局部条件律诊断|
|[#83](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/83)|`4e6fc36ee8ce9c8bdc903bff6aab7a19fd13a472`|`e218b24a203ae5fe77019630de752f92335cb649`|Llama2最终26项任务结果|
|[#85](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/85)|`39ec614be3f8bc78a8cb31d236d8a722ea828578`|`a56ff23e96b779d13ec0f2b2e34ba398872a9122`|SANTA++ v1文献核查|
|[#86](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/86)|`a3c59f2a691c645fc04626c0374d85f5dc8676e8`|`7dec2ef7edde3042edabca7852d9559f77cd614c`|真实QKV局部采样器对照|
|[#88](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/88)|`59e846f0ec0e5898863c508a2e0de62762eebc7c`|`8d4ce51be7ecace716bc83688dc4768eb2574d38`|可选全宽采样TLM与组合接入|

科学集成`8d4ce51be7ecace716bc83688dc4768eb2574d38`。回读每项merge两父必须为[base,head]、tree等审阅head，且全部为最终祖先；无force/bypass。原生status/check列表为空，无失败/changes_requested/未解决线程，不宣称CI执行。所有原PR非协作元数据blob（含work下封存档案）逐项精确保留，见evidence/FINAL_SCIENTIFIC_BLOB_PROOF.json。

## 模块究竟怎么接入

旧Qwen联合数值入口用独立ffn/mode开关：每case新模型，先安装Attention适配器，再替换所选各层MLP。FFN覆盖24层prefill/decode；Attention覆盖计分token24层decode，前缀SDPA、QKV/RoPE/cache/Wo等保留。Llama2独立32层适配，不能直接继承Qwen质量。早期单层P-DNN checkpoint仍仅替换其指定层。

82不把8位量化接进模型；86不运行整模型新采样器PPL；85不改实现。88才接入新TLM：筛选→紧凑准确QK→可替换全宽采样器→直方图/重映射→V读取累加，地址已代表PV采样，不再抽一次。原tlm/v3默认保留，审阅补齐命名的可选`qwen/run.py tlm-parallel --attention`注册/说明，dry-run及--help路由通过。

补做两个采样器×数字/历史fixed_sc_exact的4项24层全形状、context512/S16合成Link情景，均完成完整decode调度。原作者2项单层冒烟原件保留。该补测是事务模型连通，不是模型推理；SC沿历史T4096配置，不冒充最新B4/T32/K32硬件重标定。完整能量/面积和quality_reference_ppl仍null，新后端不继承旧CTMC PPL。最新短流FFN＋赢家/拒绝＋q8＋物理源的全组合仍需独立质量/硬件验收。

## 实际审核与修正

**82：**25CPU合同通过，9种格式全部数值字段重放通过，捕获为已冻结24层/2688行，实际驱动为42行×3seed理想轨迹观察。冻结源与本地源档案按实际SHA核验；具体数量/浮点误差见evidence/REVIEWS.json。accepted_law正确保留参考零态及2^-m校正、mask独立门控、最近偶数舍入和饱和。观察器不改变默认输出/RNG。局部条件TV不是量化自适应最终输出律，更不是新PPL/PPA。

**83：**补齐此前缺失的官方最终验收并随原PR发布FINAL_RESULTS_20261022_ZH.md/FINAL_METRIC_ORACLE_20261022.json。26完整配置，共54782配置内文档、109564个acc/acc_norm均用固定lm_eval0.4.8原始process_results、doc_to_choice/doc_to_target、原始YAML/parquet逐题一致；7collector守卫通过，源/输入/文档SHA、32层/active-dummy计分覆盖和三seed/BF16配对统计完整。没有重新推理、下载模型或重哈希14GB权重；模型身份继承已验证manifest。修正PR正文旧19/26及oracle pending，旧检查点与原件不改。用户已删除定时，本轮不重建。

FFN-only的PIQA/ARC-E acc均值相对BF16约−0.0544/−0.0281百分点；联合S512约+0.0181/−0.0281百分点，但acc_norm仍约−0.3264/−0.6033百分点。小幅提高不代表显著胜出或无损；完整逐seed指标/总体SD与逐题改善退化在最终JSON，seed SD不是题集置信区间。短题all-K不能证明长上下文筛选，结果也未采用新赢家/拒绝/q8。

**85：**核对用户原32页PDF实际848411B/SHA，渲染并检查2/7/13/28页，核对主文/附录A–F相关公式表与官方固定commit README。条件Gumbel纳入率不同于首抽Softmax率；分子/分母分别无偏不代表比值严格无偏；S128为32队、GPU K31/S124为单层Attention算子演示，逻辑KV不是DRAM/J/token。项目来源blob及算术匹配。候选内采样不能补回筛选遗漏，创新性判断有限且未夸成穷尽查新。原PDF不上传。

**86：**14CPU检查通过（最初精简导出缺冻结拒绝参考，补齐同tree两源后该项通过）；90原件逐SHA、源/输入/计划绑定通过，真实V参考与解析IID方差、组表、MAP不足子组和固定预算表只读重算一致。90为54原始+36筛选派生、3seed×8重复，非90独立上下文。122归档执行源按原CRLF字节及Git LF等价核验，失败捕获/绑定记录保留。公开视图仅修正40个解析IID/拒绝的MC95注释，数值全部等原服务器摘要。经验网格首次交叉不保证误差单调，也不是普遍预算或物理时钟。主表典型288更新、赢家固定S512的89/90和S1024的90/90仅适用于该样本与MSE目标，不继承PPL/能效。

**88：**18新+10旧合同通过，原始32个情景JSON及2个summary/来源manifest按实际SHA核验（精确count见REVIEWS）。读到的新模块显式核全宽源、排除参考/自身、均匀仲裁、空态校正、拒绝失败费用、偏移配置、单项回压与跨查询间隔；未标定费用不填零。旧v4仅3扩展点，旧测试数值路径通过。Windows默认临时目录及稀疏导出的历史breakdown.csv曾导致夹具失败，补齐真实Git文件和显式本轮临时目录后10/10通过，未修改原测试或算法。新增统一入口与24层证明是审阅补充，不覆盖作者执行快照。

## 交付与剩余边界

CPU分组25/7/14/18/10含历史复用与重跑，不相加宣称全为新检查。没有GPU/Slurm提交/取消、冻结快照改写、训练、新整模型PPL或PT/物理器件实验。仓库merge权限实际成功；可选code-review服务沿前轮不可用记录，本轮采用原生API门禁，Projects沿历史read:project限制待同步、未重测。

73最终结果、84文献、87可用TLM已按其有限范围实际验收关闭；继续研究78/37保持开放。Issue73回查已由用户删除，不因旧交接而恢复。本人metadata冲突保留双方有序历史，amlink1219 STATUS逐字节保留。canonical原有未提交增量先逐SHA/patch归档，HEAD不reset，root/正式工作文件/报告blob一致。

仅一个稀疏review WT，其他验证用Git对象和最小依赖；不上传私有QKV/NPZ、PDF、模型/数据或凭据。报告合并后先逐SHA归档再回收本轮本人目录；实际完成状态看Issue55最终回执和project_archives/pr_review_issue55_20261022/RECOVERY_INDEX.json/CLEANUP_RECEIPT.json，不提前宣称已回收。

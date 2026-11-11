## 2026-11-10｜28nm250两模型仿真已提交；Qwen数组取消自设两项上限

Issue225/PR249，rayggxia，交叉引用245/PR247。Qwen数字数组38650228原等待原因JobArrayTaskLimit来自本脚本--array=0-2%2，不是EDA全局只有两项能力。已只调ArrayTaskThrottle=3并核用户/jobname；后续队列实核Qwen三项均RUNNING，未重启/重交/改源，THROTTLE_UPDATE留回执。不能据此宣称集群没有其他资源/QOS规则。

按用户要求扩展Llama-3.2-3B-Instruct（revision0cb88a4f764b7a12671c53f0838cd831a0843b95，H3072/F8192/L28/Q24/KV8/V128256）和DeepSeek-LLM-7B-Chat（afbda8b347ec881666061fa67447046fc5164ec8，H4096/F11008/L30/Q32/KV32/V102400）。同28nmTT250、832KiB/178宏、B1/2K、同LPDDR/DMA和各方案原物理资源，不按参数量缩放时间。

已适配3/1Q每KV、DeepSeek4个KV波次、>32KiB尺度元数据在原96KiB激活内起点64→56KiB、无QKNorm和独立untied embedding。4Q物理issue槽时间保留，未用FMA16片增量活动门控代理，物理面积/idle保留并分列有效/物理工作量；不是最优专用映射或新模型质量验证。

本地8构造及8解析一层＋384head均PASS，工作量/字节/全部逻辑KV/完整词表尾块/池排空/账本已核。2026-11-10 14:09北京提交原生门禁数组38650669（8项，无%2），完整12任务38650670—38650681各自依赖对应门禁，不再人为限制两并行；每模型SC三seed17/503/1009＋BF16dense/W8dense/W8screen单seed。完整实际28/30层＋完整词表，结果仍待收；初查8门禁RUNNING、12完整Dependency，无即时错误。

远端tlm28cross250_225_e0291ed6b5a9，包227f2509a117c4673807074f23b303473dc8aea4065cc9fae905ea0db7ca83b1，MF874c258f0b87631b386a8567977f43920cf598e77e3336fd96a08191d58dec72。门禁1CPU12GiB、完整1CPU24GiB（实际按Slurm粒度3CPU），无GPU/训练/PPL/新电路。正式process_28nm/cross_models_20261110/；恢复work/rayggxia/225/cross28_20261110/HANDOFF.md、ops.py status。快照不可变，不重交健康任务；55nm与既有Qwen冻结不改，PR未合并，Projects待维护者同步。

---

## 2026-11-10｜28nm250概率完整收齐；55nm式三数字基线已提交

Issue225/PR249，rayggxia。用户本对话确认28nm主数字对照沿55nm的BF16_dense/W8_dense/W8_screen，新增共享尺度P8/W8数字CIM只作补充；此前“CIM唯一主对照”为先前范围，不替代本次最新决定。

概率数组38644764三seed已全部COMPLETED0:0，原件SEAL/SHA、36层/完整151936head、帧/采样/字节与闭合账本通过。完整均值51.132604ms/token，扣head43.594377ms；片上15.267553mJ，外存4pJ情景总188.432048mJ，覆盖6.480303mm²。旧46.01856ms为局部外推，现用完整原生结果。原件project_archives/tlm28p250_full225_20261110，正式process_28nm/250MHz/FULL_RESULTS_20261110_ZH.md及JSON。

数字三组已接28nm实测原语与显式宏价，同832KiB/178宏、同LPDDR/DMA；共享FMA576/448/448路，W8另16整数GU，近等总面积6.449627/6.369820/6.399385mm²（比目标低0.47/1.70/1.25%）。前端448KiB/82端口＋Attention384KiB/96端口，SC不使用的96KiB跨K状态释放，原256KiB CIM区域复用于数字FFN/投影。旧area55字段仅API名，数值28nm×1，未套55nm价或0.81。

三项最终解析一层＋384head检查PASS；原生门禁数组38650227、完整数组38650228已于北京时间13:30提交，下标0BF16_dense/1W8_dense/2W8_screen；aftercorr各组通过后自动跑36层＋完整head。每项请求1CPU12GiB（实际Slurm3CPU），各数组最多2并行，无GPU/训练/新增RTL/PT。最新状态STATUS，不把已提交或解析门禁写成原生完整完成。

恢复work/rayggxia/225/digital250_20261110/HANDOFF.md、ops.py status。包371485605a0d3ba723279345b19f62dea32f7772ba757bd40b938dd75e3f02bd，MF0873dd0ba873923be07792f19cf31f354f6914421100616cbef0ffb0ff67c967。执行快照不可变，不重交健康任务；55nm、500MHz、其他模块原交接不改。完整数字结果待收，PR待审未合并，Projects待维护者同步。

---

## 2026-11-10 完整概率任务与数字接口清单已发布

PR249源80bdfaa9f7a785b4f66469082a269e28cd62968e，20文件远端完整回读一致，Issue225评论6746072666。EDA门禁38644763已通过，完整数组38644764的_0/_1运行、_2等待并行限制，尚未完成。全量36层/151936词表/三seed、原生LPDDR、28nm250新价保持；旧46ms仍为外推，不重标签。数字优先两级量化MAC/CIM，FFN与Attention确认问题已写文件，未发消息/提交数字任务。源包/环境/回执SHA齐，恢复本work/ops.py status；PR待审未合并，Projects待维护者同步。

---

# 最新任务：完整概率版已提交

门禁38644763、全量数组38644764；恢复[本次交接](full250_20261109/HANDOFF.md)。先查STATUS，不重复提交。

## 2026-11-09 28nm250 TLM最新更新已发布

PR249源b64cbb3241dc2f0e6d6bdb5b3ce5269e3cb06d02，31文件远端完整回读一致，Issue225评论6743216455。新零余量FFN/FMA、PV参考与平台宏已接，条件面积6.480303mm²；六CPU回放及六检查通过，250时间/访存未变、500 BUDGET不变。完整46.01856ms/核心15.016133mJ仍为明确外推，不是完整36层实跑；扣head阶段39.408936ms。S12主线、832KiB、55/500默认保持，宏/PV hold限制保留。原件zip/SHA与恢复在本work，PR待审未合并，Projects待维护者同步。

---

# 最新：28nm250 TLM价卡/账本更新

[本次可执行交接](update250_20261109/HANDOFF.md)。832KiB混合宏保持；当前250面积6.4803mm²，500不变。发布实际状态见本次PUBLICATION。

# Issue225最新恢复入口

当前阶段：28nm832KiB混合宏默认，PR249待审；详见[mixed34交接](mixed34_20261109/HANDOFF.md)。持续任务此前的55nm250、统一时钟、DMA16KiB、SRAM表征与832容量回放交接保留在各有日期子目录；不要只依据早期默认恢复。正式配置以architecture_tlm/process_28nm/{250,500}MHz/WHOLE_CONFIG.json为准，55nm不变。开始或发布前核实最新Issue225/PR249、本人STATUS和本次PUBLICATION回执。

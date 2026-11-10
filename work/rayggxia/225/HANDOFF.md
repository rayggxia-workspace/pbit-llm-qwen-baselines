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

# Issue129 SRAM与DRAM节省总结

负责人：jieruiz；2026-10-23。正式仓库rayggxia-workspace/pbit-llm-qwen-baselines，base pbit-tlm-attention-details-20261016@e8705765ed3286b225e042378d57e5d010e221ee。
独立稀疏目录tmp/memory-savings-issue129-20261023；分支task/129-memory-savings-summary。

正式成果architecture_tlm/memory_savings_20261023：REPORT_ZH.md、7页Word、SOURCE_INDEX.json、CALCULATIONS.json。固定20个源文件，8项已封存的完整decode情景复算；待审PR119/120/127引用固定head，不改变任何实验或暂停任务。PR125/126仍暂停，不恢复。

本轮验证：calculate.py复算字节、宏内读写能量、Link能量和模型容量；verify_report.py 64项检查通过。Word原生只读PDF导出，因未安装LibreOffice，用packaged render_docx.py的PDF转换适配后渲染；7页逐页目视检查，无裁切/孤页/表格溢出。最初构建检查和渲染失败属于文档工具问题，已修正shape字段与原生渲染适配，不是硬件或模型失败。

无新PPL/推理、GPU/Slurm、TLM、RTL/DC/PT。模型/data/tokenizer/seed字段不适用新实验；来源执行、模型形状和配置SHA分别在SOURCE_INDEX和CALCULATIONS。没有新增电路仿真，故中央电路台账不新增run。

关键边界：Qwen已记账2K/8K流量减少31.95/35.52% DRAM、29.82/33.49% SRAM；不是芯片完整节能。W8收益也属于数字对照；KV不自动淘汰；48→5KiB是局部逻辑计数状态，不是已测PPA。最新局部保持/恢复未组成新的完整运行；Link不是实际DRAMSys。

复核命令（需固定来源Git对象；PR来源文件按SOURCE_INDEX从固定head获取到work/jieruiz/129/evidence/prNNN.md）：
python work/jieruiz/129/calculate.py
python work/jieruiz/129/build_docx.py
PowerShell -File work/jieruiz/129/render_word.ps1
python work/jieruiz/129/render_native_pdf.py
python work/jieruiz/129/verify_report.py

文档数值验证与成果SHA在VALIDATION.json。本地可用，发布状态以PUBLICATION.json为准；通过新PR交付，不自动合并。看板权限需发布时核实；不以待看板同步冒充仓库未发布。

后续如更新此报告：读取最新Issue129/PR与源PR状态，重算对应封存JSON，重渲染Word并检查每页。当前没有运行中作业，不要重跑昂贵实验。

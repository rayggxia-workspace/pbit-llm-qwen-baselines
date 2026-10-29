# Issue210实际验证

2026-10-29；rayggxia；task/210-tlm-component-audit；基线main787489192ebfcdb61ad72edde406818f450aa3dc。

- derive.py只读取已有定价和封存摘要；6项闭合检查全部通过，4配置×3情景逐字典与原RESULTS一致。
- python -m unittest architecture_tlm.ppa_recalibration_20261027.test_rebudget -v：8/8通过，覆盖门控不抹去工作/漏电、占用守卫、去重、真实原摘要及HBM缺价。
- Word由python-docx生成，Microsoft Word只读排版导出PDF；PDFium渲染并视觉检查6/6页，11表、3链接，无空白页、截断或漏字。
- 原始SHA记录SOURCE_MANIFEST；新增小型交付SHA记录DELIVERY_MANIFEST。
- 未运行GPU、PPL、DRAMSys、RTL、综合、STA、PT或新的整机TLM。无新数字run，未增加假电路记录。
- 已计价总值不是整片PPA，Ising未激活，外存粗代理与真实HBM功率分开。

发布前后Git blob原字节与本地结果、精确文件范围及远端提交复核，状态见HANDOFF与PUBLICATION.json。

## 2026-11-07 Issue225：250面积审查及TT短T时序失败标签

用户询问250还有何缩面积、是否漏接改动。本轮只审查/更正证据，不改资源或bank，不新跑TLM/RTL/PPL。确认250投影tile256×K64×BF16=32KiB，仍继承100两槽各80KiB，多留96KiB，按现4KiB宏约0.645918mm²；历史DMA返回SRAM32KiB另可回收约0.215306；Attention64→48KiB/组是未实施候选，另省128KiB/0.861224。合计1216→960KiB、参考22.59477→20.87233mm²仅容量计价，不是已验证设计；删bank必须重排并回放。2核已有对照慢约2.593%、旧核价省0.96948mm²；不优先256→192数字池，理想权重吞吐128→96GB/s。PV算术减半也只约省0.222，状态不能减半。

最新204交接已收TT250短T/C19，setup−0.421007ns未过，失败映射1.498438mm²/核。公共FFN_PROFILE/bindings与250模型/计价从pending改timing_failed，有效core仍null，失败价格不能替代达标价；100有效价不变。按失败映射面积作敏感性3核24.18165，不能据旧核参考许诺最终20.87。建议先闭合FFN加载侧门限路径并优先整理投影缓冲/历史SRAM。正式AREA_AUDIT_ZH.md/JSON位于250目录；当前304bank/1216KiB/3核/default16与所有冻结原件均不动。

归档SHA、单位、guard及100保留价验证见area_opportunities250_20261107的EVIDENCE/VALIDATION；无新电路台账run。上传以PUBLICATION.json为准，PR249待审未合并，Projects待同步。

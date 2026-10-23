# Issue139 Qwen3-4B GQA 文献调研交接

负责人 amlink1219；task/139-qwen3-gqa-literature；base pbit-tlm-attention-details-20261016 @6966739a5223680888bf0315f7bb4f73423a1ae6。

正式报告：architecture_tlm/qwen3_gqa_literature/REPORT_ZH.md；12篇来源与PDF散列：SOURCES.json。研究完成，任务通过PR交付，未自动合并或关闭Issue。

已做：核实32Q/8KV/d128；原文与官方代码分开核对；区分mean-Q、概率sum、teacher max及union；计费与Base迁移边界；独立审阅修正3处措辞。图示数字为集合/BF16 payload推导，没有模型运行或PPA实测。

未做：模型替换/下载、门控迁移、训练、完整WT2/推理评测、周期后端选择器接合、STA/PPA。当前任务没有本地或服务器计算作业。Issue116/123仍暂停；Issue136/PR137的Base任务归原负责人，不重交。

Zotero当前关闭，localhost接口拒绝连接。只读个人库已查重；12篇PDF签名、页数与SHA已核，均待官方Connector导入，未写SQLite、未启动UI。恢复时必须再次全库去重、核个人库与目标分类并独立回读条目/PDF，不能盲重放。

本机研究/待导入目录：outputs/qwen3_gqa_research_20261023/，私有完整清单ZOTERO_PENDING_PRIVATE.json，PDF为pdf_<arxiv>.pdf。默认Zotero待办副本路径C:/Users/A/.codex/zotero-library-state/pending/qwen3-gqa-20261023.json；存在性以本机最终PUBLICATION.json为准。PDF和本机库元数据不上传Git。

独立稀疏checkout：workspace_projects/gqa_lit23。发布辅助脚本与远端身份/响应保留上述outputs目录；最终本地PUBLICATION.json记录commit/PR及回读。仅提交报告、来源、审阅/交接、manifest、Zotero状态和本人STATUS/项目备忘录，不上传凭据或全文。

Projects看板同步以本轮API核验结果为准；Issue/PR交付独立完成。

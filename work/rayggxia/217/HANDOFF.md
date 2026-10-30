# Issue217：给模块开发AI的TLM交付说明

负责人 rayggxia；分支 task/217-module-handoff；PR base main，正式发布起点 7d42c7d30fa9c729c899ba7f815332dd6ed5671a。

正式成果为 architecture_tlm/module_handoff/README_ZH.md 和 PROFILE_TEMPLATE.json；同路径在本机 a_P_BIT 根提供同字节阅读副本。说明含最低交付材料、L/II/流式输出、存储/随机请求、PPA边界、旧收费替换、FFN与Attention专项要求，以及可直接转发的指令。

只定义轻量交付格式，没有实现自动加载器，没有修改 unified_v6、Ledger、存储、随机源或已有模块默认，没有新TLM/PPL/GPU/RTL/PT。模板中的参数是 null，不是0成本或0周期。实际文档验证及正文/模板SHA见 VALIDATION.json。

Git CLI fetch发生连接重置。新本地稀疏工作树 tmp/module-handoff-issue217-20261030 复用可用7874891对象；正式GitHub分支从最新main 7d42c7d创建，仅通过对象API提交本任务小文件。两侧历史不同，不强推覆盖；以正式分支提交和PR差异为发布依据。

后续AI：转发正文及模板；在各自原任务中填写模块资料；只有真正写入整机适配、选择了新版本并重新验证之后，才能标记“已接入”。不要据本次文档宣称Issue198/204等局部改进已纳入整机。缺少PPA可用有标记的宏估计，后续替换参数。

任务最新发布/待审状态见Issue217和本分支关联PR，不自动合并或关闭。本人STATUS在独立工作树增量维护；此前宽历史状态上传受审批限制，本任务公开状态采用本专项交接及Issue/PR回执，不重传无关历史。Projects当前连接器无操作接口，待维护者同步。

# Issue159七组模型HF入口交接

负责人rayggxia；独立tmp/ffn-hf-index-issue159-20261101，分支task/159-hf-model-index。接续原Issue159/PR200，只加共享位置索引，不改训练计划/源码、不接管执行方。远端PR base main@7d42c7d30fa9c729c899ba7f815332dd6ed5671a。当前本机Git基础来自既有对象，用于小型文件归档；远端发布通过Git对象API精确继承main，不把本机历史直接push/force-push到远端。

正式备注qwen3/model_artifacts/HF_SEVEN_FFN_MODELS_ZH_20261101.md和HF_SEVEN_FFN_MODELS_INDEX_20261101.json；README有导航。目标repo CyberPrometheus/p-computing4llm-models，revision xuhaoyuan02-qwen3-4b-seven-20261031。用户确认上传，但两轮匿名API和无缓存复查均401；公开Qwen3-4B对照200，不能断言目标不存在。没有本机HF凭据；未下载权重/未加载/未PPL/无Slurm/无新RTL/PPA。

已核对PR200 CASES七标签及位宽/共享/T，不能当HF真实文件名。检查脚本响应SHA和当前空字段在JSON；原训练完整报告与本次访问检查不混称。恢复时先看Issue159/新PR和本人STATUS/回执，再在有权限HF会话下读取指定分支，将其固定为完整commit SHA，核对各case实际目录、manifest/LFS oid/大小、加载器与模型/数据身份，下载后再重算SHA。不要猜子目录，不要默认Transformers可直接加载自定义packed导出，不重复下载七份大checkpoint。

本次文档验证：两份文件七组/URL/revision/null字段及读取状态一致，公开Qwen控制成功；精确文件SHA在FILES.json。远端上传/回读状态看PUBLICATION.json；未合并不称已合并，权重未验收不关闭原Issue。Projects无写接口待维护者同步。原根正式MEMORY由Issue28协调窄增量，不上传本地混合union。

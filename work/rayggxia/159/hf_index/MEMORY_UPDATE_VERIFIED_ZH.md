## 2026-11-01 七组FFN HF权重已登录核对（Issue159 / PR229）

此前401为匿名历史，用户登录后已实际读取私有模型库。固定repo CyberPrometheus/p-computing4llm-models@fa0a9e4a7ad394ffb60e8175cb0d1e34dff93caf，分支xuhaoyuan02-qwen3-4b-seven-20261031，submission submissions/20261031T115253Z-xhy12309-seven-case-weights。models/b0,w6,w10,s1,s3,t16,t64各36个ffn_XX.pt＋non_ffn.pt＋export_complete.json；整个提交276文件/37,494,721,776逻辑字节。

实际代码/配置/分词器/报告分库存放：dataset CyberPrometheus/p-computing4LLM@a7c029901637bab6caf5b79a9563697e8bbf77d6，submissions/20261031T115253Z-xhy12309-seven-case-code-results；由模型库code_reference实际读取，未再遍历dataset。自定义bit-packed全模型部署，非adapter，必须同组non_ffn与FFN；restore_sources.py恢复seven_runtime_v9_resource8后用load_seven_deployment.py；新helper全4B未运行，历史实际重载代码final_deployment_eval_v1.py。未下载37.49GB、未重算全部文件SHA/未新PPL；Hub元数据和HANDOFF已核对，不宣布管理员accepted。正式定位文件qwen3/model_artifacts/HF_SEVEN_FFN_MODELS_ZH_20261101.md和INDEX；任务HANDOFF、PR229与VERIFIED_PUBLICATION为恢复入口。根正式MEMORY由Issue28接收窄增量。

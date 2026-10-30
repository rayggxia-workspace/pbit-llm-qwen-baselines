# HSA与Kelle精读：Issue212 / PR214

负责人rayggxia，task/212-gpu-decode-profile，base main。续本Issue带宽/吞吐审计；只读PR213@759b6c0f，不修改amlink1219成果。远端父50ed17b2a4082b642c361d8605b641b8e63ea806，本地父2a6b57c3658174f1e454ca77786a40c7996a3913；API发布在实际远端父上追加，不强推本地分叉。实际发布SHA以Issue/PR评论为准。

正式报告architecture_tlm/component_budget_audit_20261029/results/HSA_KELLE_REVIEW_ZH_20261030.md，SHA256 c39b666d9d331b41489935daad6527313f9bf28582fa862ae8a46877671eed03；同名JSON给两份v1 PDF原SHA/大小/URL、形状输入SHA、算术结果和限制。PDF/渲染图仅本机工具暂存，未上传；可用版本URL和SHA恢复，不保证其他机器能读本机文件。

实际核验：HSA第5/6页、Kelle第7/8/10页原图与正文文字；HSA两表37.6与116.55×.636=74.1258的差异保留，不能混配；表I总token37.6换整请求输出分母35.25，不是纯decodeTPOT。Kelle B16/3.94倍为相对对照，图13/14未给统一绝对token/s。64GB/s+7GB+B16演示上限146.29并非论文实测。

当前Qwen3-4B D2560、KV8×128，BF16存x5120B反而大于K+V4096B；Kelle重算不能直接认定省25%或50%。可借PoT移位桶、MVM数据流、独立权重/KV端口、本地部分和、读出尽快消费；不直接改模型、数制、默认存储或新开实验。与Issue198专用Attention存储候选只读衔接，不接管其未完实现。

验证命令：python work/rayggxia/212/hsa_kelle_20261030/build_review.py --paper-dir <包含固定PDF和PDF_MANIFEST.json的目录> --tlm-summary <原封存case1 RESULT_SUMMARY.json> --output <新临时目录>。脚本核验两PDF与形状SHA、计算输出和UTF-8/LF；文献事实人工原页核对，不把复算叫硬件验证。无新PPL、模型、GPU/Slurm、TLM、RTL/EDA；不新增数字run。项目外部PPA不乘本项目面积0.81。

下一步若做HSA/本项目正式倍率，先锁定原表条件、模型/数制/分母；Kelle需要绝对时延或作者artifact，不能用归一倍数编造token/s。PR214待审不合并；Issue212保持open。本人本地STATUS/HANDOFF与长期备忘录按本次回执追加，宽历史不重传；看板未操作。

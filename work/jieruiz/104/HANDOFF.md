# Issue104 交接

负责人jieruiz；2026-10-22；分支task/104-architecture-inspector；base eb317e4f6fb1b0d8844887401f3275f128ef8a83；目标rayggxia-workspace/pbit-llm-qwen-baselines的pbit-tlm-attention-details-20261016。目录C:/Users/86134/Documents/a_P_BIT/tmp/architecture-inspector-issue104-20261022。

## 已完成

- 21可点模块、五视图、52个封存情景的自包含HTML；源码锚点绑定准确Git blob，结果封存SHA与执行SHA分开。
- 三个observer文件旁路导出stage/query统计，代码284677c；其余检查台及比较修复1efb83b/4250dc1/124d37d。新观测执行124d37d2dca5020451b6e64f19ddede882042371。原52结果未修改。
- 4新观测（Qwen24层336query、三个tiny各2），旧字段线格式严格全等。不是新模型推理/PPL，数据与权重版本不适用；事务配置/种子/精度/模型结构/源码SHA见原件及观测manifest。
- 76CPU检查、686模型不变量、16组观测守恒全部通过；浏览器交互/截图及Node语法通过。VALIDATION.json、五组log、BROWSER_QA.json与ARTIFACTS.json。
- 三个独立审阅覆盖周期、存储/随机源、数据流；审阅发现已反映CHECK_REPORT_ZH.md。最终只读复核没有必须修正项。
- hooks独立目录已验证归档回收；失败v1/v2原件保存在本地project_archives，不改原件，见FAILED_PREFLIGHT_INDEX/HELPER_RECOVERY。主104待审保留。

## 状态与限制

本地已完成；实际上传/PR状态以PUBLICATION.json、REMOTE_VERIFY.json和Issue104最新回执为准。不自动合并/关闭。无本任务远端作业或新定时；本机预览服务8840仅回环，离线HTML无需服务器。Projects沿既有read:project不足待同步；仓库admin/push可用。

SC驻留权重32KiB/波保持供给、局部48KiB计数状态、部分格式转换及随机源整机接入仍未闭合，全部列在页面。Link不是新DRAMSys；总能量/面积/PPL仍未知。不能把检查通过当作硬件或质量验收。

## 恢复步骤

1. 读PROJECT_MEMORY第0/1/12与本主题，核最新Issue104/关联PR/STATUS，避免与Issue95/96重复开工。
2. 复用本目录/分支；若已回收，从Git恢复并按README补齐统一v6/results及SRAM校准依赖，不另拷贝全库。
3. Git根运行 `python architecture_tlm/inspector/build.py`、`python work/jieruiz/104/validate.py`。本次Python3.12.14；临时文件显式位于本任务work/jieruiz/104/test_tmp。Node24.19.0仅语法验证。
4. 新观测只写全新输出目录，先提交准确源码，调用observe.py；不改52冻结原件，旧JSON与内存tuple按JSON格式比较。
5. 首先落实权重供给和计数状态电路，再接新源后端、转换、调度和成本；若改变量足以影响排序，细化相应路径。结果不能继承旧CTMC/IID PPL。

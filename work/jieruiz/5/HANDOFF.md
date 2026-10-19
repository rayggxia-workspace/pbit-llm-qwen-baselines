# Issue #5交接

负责人：@jieruiz；日期：2026-10-17。最新交付状态以个人STATUS、Issue和关联PR为准。

- 目标仓库：`rayggxia-workspace/pbit-llm-qwen-baselines`；任务分支`task/5-dram-dscim-audit`，base为`pbit-tlm-attention-details-20261016`的`9608c0d06cf8b421cbbd348aca4fc84c5990aae7`。
- 独立工作目录：`C:/Users/86134/Documents/a_P_BIT/tmp/dram-dscim-issue-5-20261017/`；没有修改其他实验工作树。
- 已读：最新远端README/TLM索引、治理规则、Issue #1/#3、PR #2/#4及评论、本人STATUS/交接；本机实际身份jieruiz，未发现重复专题任务。
- 完成：厂商数据表和实际DRAMPower源码核对；独立核心电流profile、预检查/非覆盖builder、13项测试；4份旧统计重新计价；DS-CIM原PDF图2/4/5与实现边界分析。
- 原始IEEE论文、Micron PDF和下载源码保持本地，未提交到公开仓库。来源、文件版本和SHA-256见source_evidence.json；不把内部图或工具安装当成本项目产物发布。
- 新profile不改timing、未校准I/O，不承诺实际器件典型功耗；旧默认输入和旧结果原样保留。新运行须显式选新配置并执行预检查，旧入口并未自动受guard保护。
- 本次没有新GPU/PPL、完整DRAMSys、RTL/PT作业，没有本任务运行中的远端作业。
- `reprice_ddr4_audit.py`由已有本地工具正式整理，新增auto-PRE项及测试；4份旧轨迹auto-PRE均为0。不要把这个修正写成上游DRAMPower bug。
- 看板缺read:project，待有权限后同步；Issue/PR可正常交付。

## 可执行接续

```powershell
cd C:/Users/86134/Documents/a_P_BIT/tmp/dram-dscim-issue-5-20261017
git remote -v
git status --short
python architecture_tlm/checks/test_dram_power_profile.py
python architecture_tlm/dram_power_profile.py architecture_tlm/results/dram_power_review_20261017/ddr4_2ch_micron_reva_limits.json --require-core-profile
git diff --check workspace/pbit-tlm-attention-details-20261016...HEAD
```

先读Issue #5和PR最新讨论，避免覆盖后续补充。若Git直连不可达，使用当前系统HTTPS代理逐命令传给`git -c http.proxy=...`，不保存凭据或更改全局设置。

后续：完整DRAM估算先确定目标器件及I/O边界；FFN先选普通SRAM＋静态tile保持或定制数字CIM接口。CMR=64不能直接解释成单token的64个独立采样；算法重映射OR与存储改进应分别评估。

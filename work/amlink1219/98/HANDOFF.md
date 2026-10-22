# Issue98 频率与时序补充（2026-10-22，amlink1219）

接续原负责人rayggxia的Issue98，PR100已核实合并。本人仅补充16项工作频率/时序域及原文依据，分支task/98-ppa-frequency-amlink1219，base集成eb317e4f。正式入口architecture_tlm/benchmark_protocol_20261022/README_ZH.md第2.1节，机器证据FREQUENCY_EVIDENCE.json。原报告其余内容逐字节保留，原PAPERS.json/.csv和协议不改；AttAcc计算频率仍待原始表格复核。文档与SHA/链接核验通过，无新模型/训练/GPU/Slurm/TLM/EDA或器件PPA。上传状态以work/amlink1219/98/frequency/PUBLICATION.json为准；Projects实时查询缺read:project，看板待同步。原负责人及其他成员STATUS/HANDOFF不改，不自动合并或关闭Issue。

## 恢复

先读最新Issue98及本分支PR、根AGENTS/PROJECT_MEMORY和成员进度。当前只有文献频率补充，无可恢复计算作业。

独立最小稀疏checkout位于本侧聊资料目录upload/checkout；未改动主线程任何checkout或作者原分支。正式上传目标已核实amlink1219（75301230）及repo1420564659，push=true。

本次没有改写根PROJECT_MEMORY或其唯一维护目录；待原维护任务审阅后追加频率入口即可。原作者PR100历史回执按其当时状态保留，本次以新PR回执为准。

后续只需审阅频率表及待核字段。不得将局部ns倒数、接口Gb/s、ADC GS/s或跨节点投影混成统一实测主频；勿把本补充当新的PPA实验。

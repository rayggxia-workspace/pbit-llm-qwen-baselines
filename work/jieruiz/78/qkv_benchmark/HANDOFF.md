# 发布回执：真实QKV比较已推送PR86

2026-10-21T13:41:36.925189+00:00；jieruiz；task/78-sampler-qkv-benchmark。科学head346bbb12f1181ab1b974940d79f052d0757fec80已按相同Git commit/tree/blob实际上传，草稿PR86开放未合并：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/86 。90/90统计与报告齐全；本次仅补发布回执，科学结果不改。原始QKV/长曲线留服务器，无本任务运行作业。Issue78保持open，Projects本轮未写。最终分支head与远端字节核验见Issue78最新回执；下方待发布字样是此前阶段状态。

# Issue78 真实QK/V采样器比较交接

更新时间2026-10-21T13:37:45.944700+00:00；负责人jieruiz。task/78-sampler-qkv-benchmark，base pbit-tlm-attention-details-20261016@5b26c80c28ab22383f12ab31046dd723ca985abb。工作目录C:/Users/86134/Documents/a_P_BIT/tmp/sampler-qkv-issue78-20261021，是独立稀疏worktree；不切换或覆盖PR82的field-int8工作目录。

## 完成与证据

- capture源4251660247c564d7d1ffc0da2ff386773b5cdfb8，CPU2640，六窗口全部原BF16前向逐位相同。原2639拒绝数据，日志/源码保留；根因未定位。
- 重放执行源4ec2613a634c177db536d3ae355f614886cd1d37，CPU2641 pilot行0、2642数组1–89，90/90status=completed。各方法3seed×8重复，54原始QKV行＋36筛选派生。
- 原始QKV NPZ只在个人服务器，SHA410dcfa5fddd073f6609fd2bfe42cd2f749f1850123a15d4b7433aead4910980；CAPTURE.json与RESULT_MANIFEST记录模型/数据/代码/配置和结果位置。
- 2731被配置SHA门禁拒绝：Windows Git archive执行包为CRLF，Git blob为LF。实际PLAN d06121f59d6060edd55cb7070743703b0e8c0203c50508cc0e11ac6978eca5fa未改变；SOURCE_BYTE_AUDIT和executed_sources保存原字节并验证只换行差异。不是容差放宽或重写旧manifest。
- 2732完整汇总、2733固定预算/预热派生完成；后者源25cfd9d78ed74f2f71122b9ac1ef07b7410b84b3；没有重跑采样。
- 正式报告qwen/results/sampler_qkv_20261021/DECISION_ZH.md；SUMMARY.json SHA b95c40f5098fca632e28d420e96399189e59c6f80d8ed6da048fa8ebf9ef1261，原字节与远端一致。RESULTS_ZH.md为完整组表；原始长曲线索引在RESULT_MANIFEST。
- 本地13检查通过；服务器核心8/汇总4通过，新增固定预算非单调守卫仅本地。

## 复现与来源

读取CAPTURE_SUBMISSION_2640、BENCHMARK_SUBMISSION、SUMMARY_SUBMISSION_2733和源码README中的精确命令。远端项目/home/Hongjie_Zeng/projects/pbit-qwen-ising-broadcast-20261021-issue78/；snapshots按准确commit隔离，输出位于outputs/对应执行SHA，原始源/结果不修改。capture输入通过run_model既有独立identity重新核对模型/分词器/文本/token/校准SHA；模型revision060db6499f32faf8b98477b0a26969ef7d8b9987。不在聊天/仓库复制SSH配置或凭据。

## 结论与边界

赢家c=max和校正拒绝典型主表288更新，前者还需均匀仲裁，后者需偏置反馈/空态校正，尚无确定能耗胜负。Barker/两比特/XOR未达标计数必须一起报告。赢家从argmax初始化，B0/S256均值67/90、S512为89/90、S1024为90/90到IID128目标；不是完整PPL/全输入保证。8位驱动只是理想响应下的定点控制，不是R8概率阈值或物理器件验证。

所有时间只为更新/服务波下限；须加p-bit稳定/去相关、分数加载、rank树、帧缓存、反馈和流水。固定候选原BF16轨迹不等于概率FFN的新轨迹，筛选遗漏和V去重/GQA访存尚需对应模型/TLM验证。

## 当前状态与下一步

科学结果本地完成，任务分支/PR发布以PUBLICATION与Issue78最后回执为准；不把未推送状态写成远端完成。Issue78仍open，PR82不接管。本任务无运行作业，其他Llama作业未改；Projects本轮未写入，沿既有scope限制待同步。

后续优先对照winner-hold与校正拒绝法RTL/PT，再少量全模型S512/S1024与预热配置验证；不要仅凭MSE首交叉设置在线停止。若需要新的模型评测，继续按Slurm/immutable snapshot并在相应任务记录。待审保持本最小工作目录，合并后按生命周期回收。

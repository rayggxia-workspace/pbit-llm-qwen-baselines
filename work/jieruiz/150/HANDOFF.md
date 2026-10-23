# Issue150 固定多档尺度

负责人jieruiz，2026-10-23。正式目标rayggxia-workspace/pbit-llm-qwen-baselines；base pbit-tlm-attention-details-20261016@6966739a5223680888bf0315f7bb4f73423a1ae6；分支task/150-fixed-multiscale，独立稀疏目录tmp/fixed-multiscale-issue150-20261023。内核helper独立task/150-fixed-scale-kernel。

已核实GitHub身份jieruiz、workspace admin/push和最新README/AGENTS/STATUS/Issue39、46、141、144。39/46已关闭；141/144健康作业继续，本任务不接管。用户只要求固定多档PPL，不做训练/RTL/TLM改动。

设计见experiments/qwen_static_multiscale_20261023/README_ZH.md。六候选d1/2/3×headroom0/1，x/z独立包络，fit合并W8-only与动态采样路径，TRAIN selection冻结最优，holdout不调参；随后原BF16+20项完整替换。

当前：实现与审查进行中；未提交本任务Slurm，未产生新PPL，不把本地完成称远端完成。服务器计划ROOT=/home/Hongjie_Zeng/projects/pbit-qwen-static-multiscale-20261023-issue150，复用/home/Hongjie_Zeng/pbit_llm模型/数据及pbit_llm环境。冻结提交、SHA、作业ID后补到SUBMISSION.json；CPU必须从实际snapshot预检。

下一步：内核测试/独立审查→提交冻结源→最小打包（Git原blob，依赖旧校准原件按SHA从已有个人项目补齐）→Slurm cpu→prepare GPU→20项full数组最多2GPU→收回签名JSON复核→同任务PR更新。没有本任务需取消的旧作业。Projects历史缺read:project，待本次核验/同步；不自动合并或关闭Issue。

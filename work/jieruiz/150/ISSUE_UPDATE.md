全部评测已完成并核验，结果已整理到PR153的qwen/results/static_multiscale_20261023。21/21完整WT2＋12 TRAIN selection＋4 holdout，0缺失/无效；24层全部forward输入、原字节SHA、模型/数据/配置/尺度链通过。固定四档选择d2_h0（S,S/4,S/16,S/64），x/z按层按64通道组离线设定，不再在线absmax。

三seed均值：动态T32 11.736131，固定T32 11.851810，固定T64 11.736412；BF16 11.652735。只固定x T32 11.746519，主要质量差距z侧。固定64接近动态32，但未测实际能耗，不把多采样代价忽略。attention保持准确。

Slurm2840/2841/2842已封存结果，无需重交；执行49bc6bd不改。原件83文件SHA及单份510435B压缩归档见RAW_INDEX，核心42功能测试通过。PR待审未合并，Issue保持open；看板API缺read:project，待有权限维护者同步。

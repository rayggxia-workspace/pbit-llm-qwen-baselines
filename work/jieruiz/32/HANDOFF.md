# Issue32：独立范围缩放诊断

负责人GitHub @jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines；Issue32。独立目录`tmp/qwen-dual-range-issue32-20261018`，分支`task/32-qwen-dual-range`，base依赖PR31的`task/30-qwen-dual-iid-public`@6102c83b143fa73a15d72b9fdf762f07824c4045；目标PR base为该分支，尚未创建PR。

用户授权输入/权重分别取适合范围，定位双随机误差。新代码`experiments/qwen_dual_range_20261018/`，不改旧冻结源和结果。四范围2×2、mean量化控制、fixed控制、gu/down噪声消融、37替换配置及2 BF16参考。全部24FFN、原准确Attention；IID共享64，W独立，准确归约。当前替换PPL是128token前缀，不是完整WT2。

本地已核Git根/分支/差异/远端，GitHub API登录jieruiz；TLM base仍3553996，PR31当前head6102c83、未合并；最新README/AGENTS/状态入口及Issue/PR已阅读，无重叠范围Issue，已建立Issue32。SSH核Hongjie_Zeng，gpu5090八卡idle、本人squeue为空。未取消他人作业。

当前实现与本地数学测试完成，服务器执行未提交。提交后用git archive制作只有两个实验目录的源快照，旧校准原件仅从服务器原Issue30不可变快照拷入并按原SHA验证。模型/数据链接原pbit_llm；新个人项目`/home/Hongjie_Zeng/projects/pbit-qwen-dual-range-20261018-issue32`。不要覆盖旧快照或发布原始校准、激活、权重和逐case长结果。

下一步：服务器Slurm prepare先运行全部测试、重新核身份和原BF16完整WT2，再输出teacher逐投影方差；通过READY后提交37项数组（最多2GPU）。核结果SHA，报告无采样误差/采样方差/2×2改进/分支消融；更新代码/汇总/索引PR和长期备忘录。动态absmax和64倍权重尺度元数据是新增硬件成本，本次不估PPA。Projects权限待同步。

部署修订：5e12524的Git blob为LF，但git archive按默认autocrlf导出为CRLF，Slurm拒绝，未生成作业。已为新实验显式设置text/eol=lf，使用新提交新快照重试，原快照保留。原Issue30冻结归档不改。

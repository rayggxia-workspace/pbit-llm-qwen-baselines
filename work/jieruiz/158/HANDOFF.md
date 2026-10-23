# Issue158 Qwen3-4B 非Base迁移

2026-10-23；负责人jieruiz。用户指定Qwen/Qwen3-4B，不使用Base。task/158-qwen3-4b-posttrained，独立tmp/qwen3-4b-posttrained-issue158-20261023；依赖PR147/base task/144-qwen3-stochastic@357db5884726a66d988d75f92447ff8ecf8698e6，旧Base证据不覆盖。Issue157的SparQ由amlink1219负责，本任务只提供新模型/基线接口并做原方案13项后缀。

固定HF revision1cfa9a7208912126459214e8b04321603b3df60c、hf-mirror。先CPU下载/文件SHA/tiny门槛，再1GPU原生完整WT2及精确复跑、真实SDPA wrapper bitwise、新TRAIN校准、13后缀配置。只换权重不换动态B4/T32/K32/max4/采样参数；原文PPL不加聊天模板、不生成thinking。详见qwen3/posttrained/README_ZH.md。

新ROOT /home/Hongjie_Zeng/projects/pbit-qwen3-stochastic-nonbase-20261023-issue158；原Issue136 venv只读复用，现有Base模型不能当作新权重。尚未提交作业/无新PPL；源SHA和ID冻结后追加。CPU/GPU失败原件保留，不修改快照、不重交健康或完成任务。完整概率WT2、任务准确率、新硬件验证不在本轮范围。PR待建立，不合并/不关闭Issue。Projects待权限；分工评论网络异常待确认后补。

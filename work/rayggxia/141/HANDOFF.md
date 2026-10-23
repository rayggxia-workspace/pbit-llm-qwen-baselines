# Issue141：Qwen采样器PPL

负责人rayggxia（连接器身份）。分支task/141-qwen-sampler-ppl，base6966739，独立目录tmp/qwen-sampler-ppl-issue141-20261023。原Issue138训练模块持续独立，不改其目录；116/123暂停保持。

新增experiments/qwen_parallel_sampler_ppl_20261023，冻结参数见README。当前实现完成，GPU门禁/新PPL待提交；没有把准备写成完成。服务器仍使用Hongjie_Zeng授权项目目录；只用Slurm，不占用其他作业。

下一步：冻结提交与逐blob源码包、上传本人新project；prepare执行SHA/BF16/采样器GPU规则/6项pilot，成功后提交同协议16项。根据pilot实际吞吐设完整任务时间，最多2GPU并行。每个结果必须status=completed且SHA一致，后缀非完整。发布/作业回执后更新本文件，不改执行快照。

尚未同步看板；未有新PPA、模型训练或实际硬件RNG质量结论。

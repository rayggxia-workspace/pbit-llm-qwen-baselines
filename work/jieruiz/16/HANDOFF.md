# Issue16合并交接

更新 2026-10-18T13:55:40+08:00，负责人@jieruiz。三模型目录PR #17已实际合入pbit-tlm-attention-details-20261016，merge `8cb76da45502469a5e5e66947b25f63ca3f0f6fe`，原头 `df459fe082a86a702c435db25ec646ce714e49d4`。用户已确认合并要求；此前待审状态不是权限阻塞。

目录整理正式范围为qwen/、llama1/、llama2/、scripts/model_workspace.py与根README。三个目录各有配置、运行、基线、TLM和结果入口，历史实现/结果原字节和共享硬件模块未移动。24次命令、93链接、17锚点、119冻结输入及Git字节核验通过；本次没有新GPU/DRAM/Slurm作业。模型/数据/参数/原成果版本沿用project.json和原manifest，不生成新质量或芯片性能数字。

本目录MERGE_RECEIPT.json记录PR17确切验收；本次只更新合并状态和回执，另通过同Issue的文档PR同步到目标分支。该文档PR最终状态见Issue16评论，不以提前写入的状态代替GitHub确认。任务分支task/16-model-folders、独立目录C:/Users/86134/Documents/a_P_BIT/tmp/model-folders-issue16-20261018；没有重置、删除其他成员工作树，也未合main或其他待审任务。

Llama2 PR15与LLaMA1 PR13均已合并，记录保持。Issue16在文档回执同步确认后关闭。恢复时读Issue16最终评论、PR17 merged状态、个人STATUS；不重复实验或目录上传。Projects仍缺read:project，只有看板同步待有权限成员操作。

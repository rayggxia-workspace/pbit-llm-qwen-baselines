# 20层 P-DNN 准确率状态

Issue151，负责人amlink1219。**目前为评测准备，等待真实20层权重；无新的20层准确率结果。** 用户正在向师弟获取权重。

CPU-only Slurm2862已COMPLETED/0:0：22项评分机制＋6项流程检查通过，同模型／tokenizer／数据／固定题ID／官方harness及145三项完整新BF16已匹配。执行源码`ecd9418510565d76585aee71a4c5675dbcbd61e9`；缺20份权重，`gpu_allowed=false`，没有GPU-ready标记或20层GPU作业。[实际准备记录](preparation/PREPARATION_ONLY.json)与[终态／原件SHA核验](../../../work/amlink1219/151/preparation/VERIFICATION.json)。

已准备同协议PIQA1838、ARC-Easy2376、HellaSwag固定1000/10042题，N4、seed0/1/2，共9个候选case，配合Issue145三项匹配新BF16。所有真实推理须在权重SHA／配置／源／数据及基线验证后执行。

[代码、协议与启动入口](../../../experiments/pdnn20_task_accuracy_20261023/README_ZH.md)、[给师弟的20文件交接清单](../../../experiments/pdnn20_task_accuracy_20261023/CHECKPOINT_REQUEST_ZH.md)、[接续记录](../../../work/amlink1219/151/HANDOFF.md)。CPU机制／准备检查与未来实际20层模型结果分开记录，不能把inspect-only成功写成模型评测成功。权重和数据保留本人服务器。

# 动态组共享PoT：原GPU单种子初测

2026-11-25 17:30北京时间，用户要求改在原GPU先测，已提交Slurm6318并实际RUNNING，分配GPU1/RTX5090，开始时32105MiB空闲。4项CPU测试通过；GPU整数核R6/12/15/29 oracle检查通过（在driver加载BF16之前执行）；同轮完整BF16已跑至292窗，尚待封存汇总，未宣称动态候选PPL完成。

实验：固定训练100M T64 W8及其原non_ffn，准确Attention。x/g/u各连续64项独立计算max(abs)，选覆盖它的最小二次幂。取消每组原四档候选表；最小指数−6，初始上限x512/g256/u512，超上限明确饱和并统计，不声称任意输入都不截断。g/u各自尺度独立；sigmoid仍用恢复真实幅度的S8Q3/P8 LUT；三流AND事件直接送Wd，最终整数归约/恢复。随机字共享仍64路。

GU16/Wd32与GU64/Wd128两档，前级16/64层各1次，后级4×2×4或8×2×8联合分层。单seed101，8个分散2048上下文WT2窗口，逐元素四档和组64四档同轮对照。若动态64任一档比同预算逐元素对照PPL高5%以上，按此前用户授权补组32/16；5%只是调度触发阈值，不是质量合格线。不是候选完整WT2或重新训练。

数值源码9789339555f8059dc02cf42d152db02d43a3cf81，manifest SHA e87991b403e4c72bc765ee5106e78cc16cf4a6c056e669cdae1fa7eb5953a89c。原GPU root=/home/Hongjie_Zeng/projects/zhj/t64-dynamic-scale-issue225-20261125/gpu_run_v1；outputs/PROGRESS.json为中间进度，outputs/RESULT.json及其SHA才是完成回执。source和outputs提交后不修改；权重、数据和runtime只读复用，未复制大文件。resource_launch.py是独立资源包装器，不在原数值manifest内，其SHA与精确命令见original_gpu_v1/SUBMISSION.json。

原组四档完整WT2作业6309及单片补跑6316/汇总6317保持；不重复其健康计算。EDA1871089环境导入已通过，但仍等待模型暂存；已核对未传输模型并取消重复作业，释放GPU，成功环境配置记录保留。原GPU任务提交后不依赖本机保持在线。

本轮无新训练、RTL/PT/PPA或TLM默认修改；Issue225 / PR266沿用、未合并。下一步读取6318封存门禁和candidate逐窗目标/模型/数据SHA，比较对应预算与缩组结果。失败则保留快照另开执行目录修复，不改已提交source。

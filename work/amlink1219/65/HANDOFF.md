# Issue65 可执行交接

更新时间：2026-10-19T12:49:16.201193+00:00。负责人amlink1219，目标rayggxia-workspace/pbit-llm-qwen-baselines，分支task/65-apple-sigmoid-7b-eval。独立本地目录workspace_projects/sa7；开始base b2527f12924a53da7334afbe78c752c101814193，协作刷新集成6197f24a9cc03ab0dc5e2e72297457f638e37292。Issue50/59及其他成员工作未修改或重交。

已完成：官方两组Apple7B step250000及原tokenizer，2865文件共50,174,620,426字节，通过来源MD5并记录SHA。下载2517为COMPLETED/0:0。模型根/home/Weican_Chen/models/apple-sigmoid-attention-7b，sigmoid/softmax各自step_00250000。完整下载索引在results的model_manifest.json。

DS-CIM Zotero NQ8CM3TZ / RC92PCQQ，表II六项BoolQ、PIQA、HellaSwag、WinoGrande、ARC-e/c；具体来源/SHA见SOURCES.json。数据19份固定parquet，服务器原文WT2 SHA与项目一致；本机网络下载后校验传入本人目录，服务器HF不可达，后续保持离线。2537全部19,965题/67,106计分请求分词边界通过；原SP32000 pieces，模型容量32768。

数值状态：2536两模型以BF16量化参数、FP32计算的CPU原生对齐通过。GPU BF16的2538/2539在预检处失败，未运行正式PPL或准确率；2540是诊断，FP32 RMS单改未通过，编译RMS默认头文件路径Python.h查找失败。原因尚未全部解决，不称BF16部署成功，不放宽门禁。

当前首轮改用官方原始FP32权重、FP32计算建立质量参考：CPU准备2541，source/run-v6，converted-original-fp32，原生参考*-native-original-fp32.npz、CPU对齐*-cpu-original-fp32.json。该作业状态必须实时重查；尚未完成时不重交。已有执行快照run-v1..v6与失败日志原地保留。native环境env-native-v4使用固定官方AXLearn03cfa39推断层，避免训练TF/SeqIO依赖；评估env-eval-v4复用本人只读CUDA12.8 Torch，安装只在本任务隔离环境。

恢复先查看最新Issue65/相关PR与成员STATUS，再SSH核实Weican_Chen、canonical home=/home/Weican_Chen、project=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019以及本人GPU队列。所有重型工作经Slurm，最多一个本用户GPU作业，CPU-only显式CUDA_VISIBLE_DEVICES=''。

可执行只读命令：/opt/slurm/21.08.8/bin/scontrol show job 2541；读取logs/fp32-prepare-2541.out/err与reports/*cpu-original-fp32.json。调度记录可能过期，优先保留的reports/scheduler-first-terminal-<job>.txt和应用报告，squeue消失不等于成功。

原始FP32 CPU门禁通过后，单GPU质量脚本准备为source/gpu_fp32_worker.py及quality_fp32.sbatch（是否已上传/提交见quality_fp32_submission.json或PUBLICATION与后续交接追加）。顺序为两个FP32 GPU对齐、各六任务两题smoke、两个完整WT2、两个完整六任务；输出reports/float32/<model>/，两题smoke不是正式结果，FP32不继承BF16或硬件成本结论。完整语料计分window2048/stride1024，每个真实target一次，不沿用其他tokenizer计数。

待办：收齐真实质量结果、校验计分数/来源/命令/版本/结果SHA，保存小型汇总和原始逐题输出索引；大权重/数据/原始样本保留本人服务器。通过本任务PR交付，区分已推送/待审/合并。看板GraphQL缺read:project，待同步；不修改账号、凭据scope或权限。当前尚无正式质量结果；以实时报告为准。

更新：原始FP32的CPU2541和GPU2542两模型对齐均已通过。当前唯一GPU质量作业2542，source/gpu_fp32_worker.py，source/run-v6；动态应用reports/gpu_fp32_status.json，正式输出reports/float32/<model>/。scontrol show job 2542，并读取logs/quality-fp32-2542.out/err；先核验已存在作业与完成文件，不重复提交。

完整WT2已收齐：原始FP32 Softmax5.911825276082767，Sigmoid5.88607319951146，同317546计分token，逐窗覆盖/NLL/PPL与文本/token SHA通过。质量作业2542仍运行六项；已推结果提交6d3d5d5a64a7709aab5733f38269c1b331521cd2和Draft https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/67，未合并。下一步只读取2542及reports/float32/{softmax,sigmoid}/任务JSON、逐题JSONL和six_task_summary.json，成功收齐后归档SHA并更新本PR，不重交。

全量PPL结果已实际推送 d120381e089fcf8cbd56ac9aeca250118c85497b，Draft PR67 head和远端ref均核验，57项稳定Git blob SHA通过。六项准确率仍在2542运行。stderr中的not-a-git-repository来自harness读取Git版本的可选记录；执行源码由固定run-v6 manifest与代码提交定位，不因此重交或更改运行目录。

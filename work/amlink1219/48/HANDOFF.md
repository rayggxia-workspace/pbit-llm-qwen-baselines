# 远端状态已核验

结果提交`c2811a61e94226cc79607d91dfeba0d0b9dac992`已推送PR49（draft，待审未合并）；Issue48阶段与结果评论已更新。执行源仍为11f1d6eea2776e201f2021081f8b0fbae2cc455e；完整联合WT2及物理PPA尚未执行，Projects缺scope。此交付回执随后的元数据提交不改变实验源/成果。

# Issue48 接续：34项曲线完成，结果准备交付

负责人amlink1219；GitHub id75301230；唯一目标rayggxia-workspace/pbit-llm-qwen-baselines。分支task/48-attention-joint-ppl；独立目录workspace_projects/aj48；PR49 base task/35-attention-e01，待审未合并。执行源11f1d6eea2776e201f2021081f8b0fbae2cc455e，不可变服务器snapshot同完整SHA；文档/结果提交另记，不能以当前HEAD代替执行源。

已完成：CPU2362 38/38；GPU2365严格BF16接入门禁及原BF16完整WT2锚点；Slurm2380 34/34 suffix案例和SHA回收。原FFN与模型状态保持；所有目标均走24层decode。原CPU2327/GPU2331失败阶段单列归档。当前没有本任务运行中作业；不得重复提交2380。

成果：qwen/results/attention_joint_ising_20261019/RESULTS_ZH.md、summary.json/csv、sampling_ppl.png/svg、ARTIFACTS.json；runs/含原件及first_terminal，provenance/含冻结配置与source manifest。源manifest按11f1d6e读取Git blob，不能用修订后README/HEAD字节冒充原源文件。原始服务器目录为/home/Weican_Chen/projects/attention-joint-issue48/outputs/sweep-2380，模型/语料仍在本人pbit-qwen-sigmoid-20260929下，未上传权重或语料。

恢复先查最新Issue48/33/35/37、PR49与其他成员STATUS。核验仓库/本人身份/权限/实际push URLs；读取VALIDATION_ZH.md与PUBLICATION.json的准确上传状态。第一次终态与jobID已保留，SSH断开不构成重交依据。

后续：将当前误差曲线与Issue37同边界PPA对照；若需完整WT2确认，先明确或列出待决质量预算，选少量代表S，以相同cached scorer配SDPA/IID。full_confirm入口已实现但尚未执行；需独立新配置并按实测增加max_case_seconds（原1800仅suffix预算，预计CTMC完整目标可能超30分钟），保留预算理由，最多一个本人GPU，不能在登录节点计算。无需重新获取/复制他人数据。

Projects仍缺scope，看板待同步；不改凭证或权限。PR/Issue验收不自动合并/关闭。三seed SD仅推理随机性，不是语料置信区间；理想CTMC不等于物理Ising，GPU计时不是硬件PPA。

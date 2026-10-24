## Issue168 Qwen3-4B固定四档试测完成（2026-10-24）

jieruiz/task/168-qwen3-fixed-scale，PR169；执行679f370fa09199b67052ae6f71c0811873f4ec7e，Slurm2879已结束、18项封存/原字节SHA/36层覆盖通过。Qwen/Qwen3-4B后训练revision1cfa9a7208912126459214e8b04321603b3df60c；准确Attention，W8/A8共享64、T=K分层；无训练。TRAIN16×512，W8连续+动态32两路径分别覆盖后冻结每层每64通道x/z四档S/S4/S16/S64；测试不在线absmax。

这是batch1向量化32段×128=4096目标后缀，不是完整WT2或旧cached结果。同轮BF16 10.685883；W8-only10.525384、固定mean10.498386；三seed动态32 10.533212±0.018421、固定32 10.551331±0.071962、动态64 10.517682±0.010649、固定64 10.502135±0.028439、固定x32 10.559898±0.015856。固定相对动态32为+0.172%、64为-0.148%；固定seed波动更大，不能声称更优。BF16与替换FP32内部算术不同，下降不单独归因尺度。固定2/8档、W4/W6、任务准确率及联合Attention未测。

报告qwen3/results/fixed_scale_20261024/REPORT_ZH.md，实际固定表CALIBRATION.json；归档project_archives/qwen3_fixed_scale_20261024/sealed-2879.tar.gz，SHA ca09d749353b911aa372b80b3f6aacdebe470bc7bc41be1ee4f2020814135679。19服务器测试及17本地静态测试通过，原冻结快照未改，勿重交。PR169源码已推，结果发布以work/jieruiz/168/PUBLICATION.json为准；未合并/不关闭Issue，Projects未同步。

## 已提交（2026-10-24）

Slurm2879，冻结执行679f370fa09199b67052ae6f71c0811873f4ec7e；19项服务器测试通过，BF16及TRAIN校准完成，18项后缀试测运行。单卡gpu5090/4CPU/48G/3h上限。PR169 draft/open未合并，源码已推送。不要重交或修改快照。ROOT见SUBMISSION.json，日志logs/pilot-2879.log；results/complete.json及documents SHA全部核验后才算18项完成。无新训练/完整WT2/PPA。

Issue168；jieruiz；task/168-qwen3-fixed-scale，base PR160@989546376f2295990b7712ea553615f0b8d88cb4。独立目录tmp/qwen3-fixed-scale-issue168-20261024。准备18项小型后缀PPL，尚未提交；已核对原2870日志PILOT_COMPLETE，未重交旧任务。源码qwen3/fixed_scale，只有新目录和本人交接/状态改动。模型复用个人issue158只读权重。工作区目标rayggxia-workspace/pbit-llm-qwen-baselines；身份jieruiz。

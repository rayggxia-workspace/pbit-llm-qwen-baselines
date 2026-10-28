## 2026-10-28 Issue206发布确认：PR207草稿，3211扫描运行中

代码/28项验证/封存pilot已实际推送PR207（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/207），draft/open未合并，依赖PR202分支。发布科学head d08c3732，五个关键远端blob原字节核验一致，PUBLICATION/REMOTE_VERIFICATION保存回执。Issue206已同步；主3211四片仍在运行，三seed结果及质量建议未完成，不能将阶段交付当最终验收。继续收同一任务，不重交/不改source4d6883b2、不新建自动回查。Projects待权限同步。

## 2026-10-28 Issue206：28项通过，共享尺度Slurm3211运行

2026-10-28T13:49:22+08:00；jieruiz，task/206-group64-scale，tmp/group64-scale-issue206-20261028，依赖PR202@fbd67c39。冻结4d6883b24ad27d9fa96feb84592696c374cfd808、62执行blob；28项CPU/CUDA通过，3210 pilot5项封存核验通过。正式3211四片运行，40主输出/37唯一待齐，固定W约20min、双随机60～90min；不重交，不碰3208。四次BF16同13.566049，原固定首seed15.551865复现。无新训练/RTL/PPA/TLM。

x/g/u每token连续64项各共用一档，限TRAIN原冻结四PoT。固定W GU64及双随机联合GU256分别六配置：lane、仅x max、仅g/u max、all max、all trim1、all trim4；g/u分开选，sigmoid恢复真实g，NL128/Wd/准确SDPA不动。共享尺度可将组内对齐移到归约后；质量及能效还未验收。1024目标后缀非完整WT2；GU恢复FP32oracle。成果qwen3/group_shared及qwen3/results/group_shared_20261028，交接work/jieruiz/206/HANDOFF；collect_group_scale.py收complete/documents，audit_artifacts.py --write-final须四片齐才运行。SOURCE/SUBMISSION/RECOVERY含SHA；源码包仅project_archives/group64_scale_issue206_20261028一份。PR待创建，本地阶段成果尚未发布，实际状态以后续PUBLICATION为准；Projects待权限，无定时。

## 2026-10-28 Issue206：每64元素共享四档尺度实验准备

用户要求x及非线性g/u每64个数共享一个尺度，限于原先规定四个二次幂。jieruiz，新独立task/206-group64-scale，目录tmp/group64-scale-issue206-20261028，依赖PR202@fbd67c39，不改旧冻结扫描。Qwen3-4B后训练、准确SDPA；固定W GU64及双随机联合GU256分开测试，NL128/Wd固定W8不变。六配置lane/x_max/gu_max/all_max/all_trim1/all_trim4，各三seed；g和u分别使用各自冻结表，sigmoid恢复真实g。

选档采用64路阈值超限计数：max零超限，trim1/4允许最多1/4项裁剪，不生成新的尺度、无排序、无数据拟合。目标为减少逐元素档号与对齐，不能默认精度或PPA无损。源码qwen3/group_shared；当前本地实现和AST检查完成，GPU/CPU实际验证与Slurm尚未提交，无新PPL。计划先28项核心检查和32目标pilot，后四片40物理/37唯一1024目标后缀（非完整WT2）。执行以work/jieruiz/206/SUBMISSION为准，未有回执不声称运行；不新建定时、不碰健康3208或其他任务。更新时间2026-10-28T13:39:38+08:00。

## 后续执行

冻结当前提交，打包qwen3的必要Python和group_shared/config.json，生成SOURCE manifest，上传个人服务器路径pbit-qwen3-group64-scale-20261028-issue206。Slurm验证+pilot依赖成功后主数组四片；先验6lane控制须复现PR202，BF16须13.566049。只用complete/documents/sidecar SHA认定完成，结果40主分数/37唯一；pilot5份独立。未提交前无作业ID，提交后记录SOURCE/SUBMISSION和准确命令。

GPUruntime沿Issue201个人venv，服务器路径/权重/语料与TRAIN表按config及prepared校验，无新下载或训练。用户面积规则raw×.81只适用后续面积，本轮无RTL/PPA；原算法GU恢复仍FP32oracle，全链路bittrue未验收。Projects缺read:project待同步。PR base应为task/201-dual-gu-short，待实际创建更新；不合并。

## 恢复命令（已有作业，不重新submit）

使用bundled Python运行work/jieruiz/206/collect_group_scale.py，再运行audit_artifacts.py。四片全部封存后才加--write-final，生成FINAL_SUMMARY；主40输出/37唯一，pilot5份独立，28功能检查。g/u/X每组mixed_scale_groups必须为0；main36层各8次/17400输入词，1024目标SHA与PR202一致。固定/双随机lane三seed必须逐值复现旧15.364688/15.895140均值。

报告对比仅x、仅NL、全共享，区分max与有意裁剪；聚合clip、事件密度、零事件和逐层NMSE平均（不可伪称全局功率加权NMSE）。只测准确Attention，无训练或新PPA。旧Cim/计数PPA范围不因共享策略改变而自动验收。

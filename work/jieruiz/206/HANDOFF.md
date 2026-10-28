## 2026-10-28 Issue206：每64元素共享四档尺度实验准备

用户要求x及非线性g/u每64个数共享一个尺度，限于原先规定四个二次幂。jieruiz，新独立task/206-group64-scale，目录tmp/group64-scale-issue206-20261028，依赖PR202@fbd67c39，不改旧冻结扫描。Qwen3-4B后训练、准确SDPA；固定W GU64及双随机联合GU256分开测试，NL128/Wd固定W8不变。六配置lane/x_max/gu_max/all_max/all_trim1/all_trim4，各三seed；g和u分别使用各自冻结表，sigmoid恢复真实g。

选档采用64路阈值超限计数：max零超限，trim1/4允许最多1/4项裁剪，不生成新的尺度、无排序、无数据拟合。目标为减少逐元素档号与对齐，不能默认精度或PPA无损。源码qwen3/group_shared；当前本地实现和AST检查完成，GPU/CPU实际验证与Slurm尚未提交，无新PPL。计划先28项核心检查和32目标pilot，后四片40物理/37唯一1024目标后缀（非完整WT2）。执行以work/jieruiz/206/SUBMISSION为准，未有回执不声称运行；不新建定时、不碰健康3208或其他任务。更新时间2026-10-28T13:39:38+08:00。

## 后续执行

冻结当前提交，打包qwen3的必要Python和group_shared/config.json，生成SOURCE manifest，上传个人服务器路径pbit-qwen3-group64-scale-20261028-issue206。Slurm验证+pilot依赖成功后主数组四片；先验6lane控制须复现PR202，BF16须13.566049。只用complete/documents/sidecar SHA认定完成，结果40主分数/37唯一；pilot5份独立。未提交前无作业ID，提交后记录SOURCE/SUBMISSION和准确命令。

GPUruntime沿Issue201个人venv，服务器路径/权重/语料与TRAIN表按config及prepared校验，无新下载或训练。用户面积规则raw×.81只适用后续面积，本轮无RTL/PPA；原算法GU恢复仍FP32oracle，全链路bittrue未验收。Projects缺read:project待同步。PR base应为task/201-dual-gu-short，待实际创建更新；不合并。

# 结果回传与验收

请回传一个有README的结果目录/共享存储索引；无需向GitHub上传模型、语料或大型轨迹。

1. 执行仓库URL、准确commit、源码文件SHA、未提交修改的patch；整个执行快照提交后不可原地修改。
2. `assets.json`的脱敏副本：保留HF模型/overlay revision、所有文件SHA、raw/token SHA；本机绝对路径可改为制品相对路径。凭据不可回传。
3. `GATE.json`、完整终端命令、Python/Torch/Transformers/Triton/CUDA/GPU信息、TF32设置、环境锁定清单；如用Slurm，附jobID和最终退出状态。
4. 每项case的`RESULT.json`及其全部`part_*.json`。完整计分的299077目标、292窗、36层覆盖、sampled_head_rows、原FFN不变和overlay哈希是必须字段。不要只给一张PPL表。
5. `verify.py --results ...`生成的`SUMMARY.json`，必须如实保留pending和三seed样本标准差。若仍有pending，不能标记整轮完成。
6. 将上面文件打包后记录文件大小和SHA256；大型结果使用双方已有授权共享存储，GitHub只放小摘要及可访问的路径/权限说明，不上传模型/语料本体。

先验收父模型参考约11.538160，再看同K_WH64控制和三条曲线。记录参考NLL差值、所有失败gate/非有限NLL/仲裁cap失败。失败结果不能填0或从均值删除。

主图只使用完整WT2。Gate中少量目标的PPL是调试值，不进入Fig.5。不要因为某个seed不符合预期就重新抽seed；固定0/1/2。算法/源码修复后必须把修复前后结果分成不同版本，并重做相关门禁与配套控制。

本轮发出时：CPU协议/覆盖/GF映射验证已通过；GPU便携移植门禁、新41项PPL均待远程执行；没有新训练或硬件PPA数据。Projects看板接口未同步，Issue/PR为任务状态入口。

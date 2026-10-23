# 固定多档幅度尺度：Issue150

目的：在Qwen2.5-0.5B全部24个FFN中，去除每token/64路的动态幅度最大值归约。Attention保持原始BF16 SDPA。本实验只改变输入范围编码，不训练、不改变固定W8、不改随机源共享规则，也不宣称RTL/PPA收益已经得到验证。

## 六个预注册候选

每层、每个信号x/z、每个连续64通道组分别离线确定顶档指数e。四档为 `2^e, 2^(e-d), 2^(e-2d), 2^(e-3d)`；d取1、2、3，即相邻2、4、8倍。e取校准包络最大值的ceil(log2)，以及再加1位余量，共六种。所有组、层和信号共用所选d/headroom，但各自顶档独立。零组顶档从1起。

推理阶段选择能容纳当前绝对值的最小固定档，不做组amax或遇到溢出动态扩档；超过顶档则真正截断为该档满幅。q255表示255/256，满幅1有独立旁路。需要保留选档、符号、舍入、概率编码、档标签和跨档恢复，它们不因去掉最大值而免费。

## TRAIN校准与选择

原语料SHA和token SHA沿用验证过的Qwen基线。使用WT2 TRAIN（不是test）：

| 用途 | token半开区间 | 使用规则 |
|---|---|---|
| fit | [0,8192) | 4个独立2048窗口；W8-only连续路径及dynamic B4/T32/K32 seed917分别捕获x/z，取两路逐组包络 |
| selection | [16384,24576) | 六候选各seed101/102，窗口2048/stride1024；按两seed平均NLL最低选定，精确同分按名称排序 |
| holdout | [32768,40960) | 选定后才评估固定方案及动态控制，seed201/202；不再改变尺度 |
| 最终test | 完整原始WT2 test | 尺度冻结，完整299077目标；不根据test挑档或删掉失败结果 |

选择范围有限、仅8192个fit token，未见文本可能超界。因此每层x/z报告clip数量、截断误差能量、被截值能量、最大超界倍率、编码NMSE、各档占比，不能仅凭“截断很少”认定安全。既有Issue39静态单尺度/双随机负结果保留；此次权重没有概率重编码，四档和随机分层均与当前主参考一致。

## 冻结计算与最终20项替换

保持历史64x64 symmetric INT8解码矩阵、FP32矩阵归约/SiLU(g)*u、BF16残差接口。gate/up共享同一x采样，z另用独立流；每64路和各档共用R8。T32/K32和T64/K64为随机分层，非自然IID、非256点完全枚举。软件精确压缩联合计数分布，不是有限位宽硬件模拟。

准备阶段重新运行原始BF16完整WT2，然后固定：W8-only一次、固定mean一次；动态/全固定/仅x固定/仅z固定的T32各3seed；动态/全固定T64各3seed，共20项替换、加1项BF16。mean是无采样编码控制，不是非线性随机网络的数学期望。每项都审计24层调用覆盖，评分复用历史完整滑窗函数，绝不将后缀PPL冒充完整PPL。

先CPU Slurm预检，后GPU校准/选择，最后最多2GPU完整数组。每次执行源Git SHA冻结，输出存个人项目下独立目录；signed JSON原字节SHA、源码、模型、数据、配置、尺度表、作业和环境一起记录。CPU失败或校准未完成时依赖作业不运行；不改任何已提交快照。

主命令：`python experiments/qwen_static_multiscale_20261023/run_static.py cpu|prepare|worker --model MODEL --data DATA --project-root ROOT --output OUTPUT --code-commit SHA [--index N]`。

状态与实际作业以work/jieruiz/150/HANDOFF.md为准。最终结果放qwen/results/static_multiscale_20261023；目前不修改TLM、硬件PPA或其他成员的Attention实验。

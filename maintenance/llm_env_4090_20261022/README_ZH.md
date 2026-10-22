# 两台 RTX 4090 的 LLM 环境已安装并验证

2026-10-22，Issue [#90](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/90)，负责人 `amlink1219`。两台个人隔离环境均已完成安装、`pip check`、19项CPU检查和6项单卡GPU synthetic smoke。94包的完整版本冻结完全同字节；进程wrapper和预载库SHA也相同。正式调用入口为个人环境的 **`bin/llm-python`**。

| 项目 | 备用一 | 备用二 |
|---|---|---|
| 系统 / glibc / GPU驱动 | CentOS7 / 2.17 / 525.116.03 | CentOS7 / 2.18 / 525.116.03 |
| Python / Torch / CUDA wheel | 3.12.3 / 2.6.0+cu118 / 11.8 | 相同 |
| Transformers / lm_eval | 4.45.2 / 0.4.8 | 相同 |
| CPU、兼容层、pip check | 9041，COMPLETED/0:0；19项通过 | 14101，COMPLETED/0:0；19项通过；先前安装pip check通过 |
| GPU synthetic smoke | 9042，COMPLETED/0:0；6项通过 | 14104，COMPLETED/0:0；6项通过 |
| 保存重载严格状态 / logits误差 | 27参数+3buffer逐位相同 / 0.0 | 相同 |
| 完整包冻结 | 94包，与备用二字节相同 | 94包，与备用一字节相同 |

本任务安装和smoke作业均已结束。仓库交付通过任务分支/PR审阅，实际发布状态见 [PUBLICATION.json](../../work/amlink1219/90/PUBLICATION.json)；不自动合并或关闭Issue。

## 使用入口与环境边界

部署环境为 `/home/pwmat/envs/llm-qwen-py312-cu118`，独立Python为 `/home/pwmat/opt/cpython-3.12.3-20240415`，安装源码/日志/缓存为 `/home/pwmat/projects/llm-env-bootstrap-20261022`。这些是本次已核验的个人部署实例，脚本保留账号、canonical路径及所有权门禁；换账号或服务器必须重新核验。系统与共享Conda/驱动保持只读，不存在5090上通过另一项目`.pth`借用Torch的依赖关系。

后续LLM任务在自己的Slurm作业中使用wrapper，不重复运行安装或smoke作业：

```bash
# 示例放入已获资源分配的 Slurm 脚本；先完成账号/路径/队列门禁。
unset PYTHONPATH PYTHONHOME VIRTUAL_ENV
export PYTHONNOUSERSITE=1
export TMPDIR=/home/pwmat/projects/llm-env-bootstrap-20261022/tmp
/home/pwmat/envs/llm-qwen-py312-cu118/bin/llm-python -I -B YOUR_TASK.py
```

wrapper仅在该进程启动前预载本环境sklearn wheel自带的唯一libgomp，解决旧glibc的static TLS导入问题；OMP/MKL/OpenBLAS/NumExpr线程数取当前Slurm CPU分配。未修改系统库、共享环境、shell profile或驱动。wrapper SHA为 `6cec8785d3fb87d62ceb10ba4310ca1c7bac305e5bf40d46a37bb4e64a86f5cb`；预载库SHA为 `3a7eaece7231911be2fbb1b3e7cb4cb5c2e0f84e0c2bb73739472b5a1feec8c1`。

5090继续优先，使用备用服务器仍在当次对话告知。计算通过Slurm，CPU作业显式隐藏GPU，GPU作业最多单卡；提交前核对全部已配置服务器相关任务及本账号GPU队列，本项目跨服务器至多一个GPU作业。SSH登录、空队列旧快照或GPU可见性均不替代资源分配。

## 已验证与未覆盖范围

CPU检查验证隔离前缀、17个包的精确版本/导入路径和Torch CUDA构建元数据，共19项；另有`pip check`及兼容wrapper下真实sklearn指标与线程池检查。完整 [pip_freeze.txt](pip_freeze.txt) 保存两台相同的94包原始字节，SHA-256为 `636ea0599fc983e7c003c3a8881aefa2f05d8167f2877dcab8992dfc3f145ae5`。

GPU的6项为单卡/版本门禁、BF16因果SDPA、tiny Qwen前向/4 token生成/本地safetensors保存重载、冻结FFN源SHA、B4/T32/K32和B4/T32/K4小输入FFN。tiny Qwen为2层、328832参数、合成WordLevel词表。重载比较先证明27参数和3个非持久RoPE buffer的值/shape/dtype/device逐位相同，再用原`rtol=atol=0.001`阈值比较，实测最大logits差0.0。两侧RoPE buffer均保持FP32。SDPA相对RMSE为0.0017545506125316024，最大绝对误差0.005356907844543457。

这次是环境安装与synthetic连通检查，没有下载真实模型/语料，没有训练、完整WT2 PPL、真实Qwen/Llama任务准确率或PPA结果。这里也没有验证完整Attention采样路径或7B显存容量。5090环境使用Torch2.7.1+cu128，本次因旧系统采用2.6.0+cu118；不能据包版本或小型测试宣称跨服务器数值/速度等价。后续实验须用相同真实模型、语料、种子和协议重建匹配数字基线。

## 可复现输入与结果

实际安装、compat、导出和离线恢复以及GPU v2输入位于 [scripts/llm_env_4090_20261022](../../scripts/llm_env_4090_20261022)。保留原字节和原换行，目录`.gitattributes`禁止隐式转换；原失败脚本/各阶段manifest继续保留，未通过发布变换执行源码。固定W8 smoke导入闭包来自提交 `9b43ba070a5b30a666c6a23519a09b57798438fa`，含源manifest与LICENSE。

原Python网络失败、static TLS、原GPU保存重载、导出来源allowlist及旧launcher解释器失配的处理见 [失败与恢复记录](FAILURE_AND_RECOVERY_ZH.md)。恢复使用的70wheel归档164065280 bytes，SHA `1c999138495f92b9e7c5fd2e69a79a6cfcb09b0103f6e025a8f7c110aa27b9aa`，只包含LLM扩展层，不含Torch/CUDA底座；接收端已验证固定Torch元数据前后不变并先dry-run闭包后离线安装。环境、wheelhouse、归档、缓存、模型和数据本体不入Git。

[RESULT_MANIFEST.json](../../work/amlink1219/90/RESULT_MANIFEST.json) 记录13份经独立大小/SHA核验的私有服务器原件及公开派生视图对应关系。发布的 [A CPU](../../work/amlink1219/90/A_CPU_RECOVERY_SUMMARY.json)、[A GPU](../../work/amlink1219/90/A_GPU_V2_SUMMARY.json)、[B CPU](../../work/amlink1219/90/B_CPU_SUMMARY.json)、[B GPU](../../work/amlink1219/90/B_GPU_V2_SUMMARY.json) 只替换个人home/主机标识及移除进程地址映射，保留检查和数值；派生JSON与原报告hash分别记录，不冒充原字节。连接地址、SSH/密钥配置及本机路径不发布。

[交接](../../work/amlink1219/90/HANDOFF.md)、[执行历史](../../work/amlink1219/90/EXECUTION_HISTORY.json) 和 [本地交付验证](../../work/amlink1219/90/VALIDATION.json) 给出任务边界、失败记录、版本与哈希检查。项目AGENTS新增一条据14102/14104验证的保存重载规则；全局AGENTS和memory未改。

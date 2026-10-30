# 服务器Nsight Systems配置与验证（2026-10-30）

已配置可直接使用的用户命令，复用CUDA自带Nsight Systems 2024.6.2.225。服务器Ubuntu24.04/glibc2.39，RTX5090驱动570.172.08。原预检只查PATH，漏掉了CUDA目录的已有工具；本次纠正判断，旧原件不改写。没有重复下载，也没有修改驱动/CUDA/Python环境。

用户入口 `$HOME/.local/bin/nsys` 是两行启动脚本，调用 `/usr/local/cuda-12.8/bin/nsys`；新登录shell已核验能直接找到nsys。非登录Slurm脚本可使用绝对入口，或source个人项目 `env/nsys.sh` 后使用nsys。

```bash
nsys --version
# Slurm中也可直接使用：
"$HOME/.local/bin/nsys" --version
```

真实Qwen3-4B后训练版B1/2K/BF16/SDPA验证：Slurm3434采集、3435 CPU-only导出/核验均完成。采集4步原生固定forward、4步带模块NVTX、8次CUDA Graph；模型/输入SHA验证，logits逐位一致。报告有34308个CUDA kernel，其中graphNodeId非零17152个；QKV432、gate/up288、down144、Attention144、KV追加144标签符合4步×36层计数。

报告位于个人任务目录 `results/nsys_99b9dbd2a97b75a1/qwen3_decode.nsys-rep`，约1.76MB；SQLite约4.44MB。原件保留服务器，不重复下载；具体SHA/大小在VALIDATION.json。MODEL_COMPLETED/VALIDATION保存原字节，非新PPL或能量结果。

采集使用cuda/nvtx/osrt、CPU sampling/context-switch关闭、capture-range=cudaProfilerApi、cuda-graph-trace=node。脚本在预热/图捕获后调用cudaProfilerStart/Stop限制采集范围。此配置已以非root用户通过，无需全系统性能计数权限。

代码nsys_smoke.py和nsys_validate.py为真实执行字节；前者的executed-code参数指向原执行依赖快照7911a0aff763f0dc（对应公开执行源码20d46ec7），prepared指向已有校验清单，output需新的未占用位置。所有新实验继续通过Slurm，不能在健康作业上附加重型采集。

当前2024.6.2没有新版nvml_metrics功率插件，当前可用性结论是CUDA/NVTX/Graph时间线；总能量沿用已验证的独立NVML长窗口。CPU调用栈采样、GPU性能计数器和ncu本轮未启用。跟踪引入开销，不能用本次跟踪时长替代此前无重型Profiler的TPOT。

本轮归Issue212/PR214，不修改旧3399/3417的封存结果。后续先用短范围时间线定位CPU发射、KV拼接/GQA展开及同步开销；详细计数器可按热点另测。

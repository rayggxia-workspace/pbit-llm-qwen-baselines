# Issue212：速度与带宽口径审计补充

负责人rayggxia；仓库rayggxia-workspace/pbit-llm-qwen-baselines；task/212-gpu-decode-profile / PR214（base main），待审，不合并。

此目录与同PR原GPU评测连续，未接管Issue182/186。用户要求核对token/s较低的带宽/batch/工艺原因；本轮只有文献与原数据派生报告，无新训练、PPL、GPU、RTL、EDA、DRAMSys/TLM或Slurm任务，无模型/语料变更。

本地恢复基线11882248881fa1da04af24f94fdcc91e21257e6a；远端父00d7a486b60dfaed1af46e9dfadd0e2315c02f67。Git CLI历史网络重置，采用GitHub对象API在实际远端HEAD上追加四个限定文件，不强推本地分叉。正式发布提交见本Issue/PR回执；不可将本地提交等同远端提交。

结果：封存候选17.407839token/s、57.445385ms；B1/2K，Attention筛选+准确Softmax+PV（非最新Ising），500MHz目标、32×64×64SC、2048MAC/拍、8MiB。GPU原生连续生成44.001634token/s、静态KV Graph100.570403次/s，后者不是连续生成。物理流量5.489678GB/token，权重5.354947GB；峰值256GB/s的搬运下限21.444056ms，整token平均有效字节速率95.563GB/s。37.3%不是DRAM bus activity计数器。不能将资源忙时相加、将差额全当可回收调度损失，或单独归因55nm。

验证：3份TLM JSON原SHA与FMA2 SUMMARY.sources全部相符；独立矩阵形状按W8/BF16算出的权重单遍字节与实际逻辑/物理读量完全相等；GPU CSV原字节SHA/大小与既有DELIVERY_SHA256.json相符。数值与现有统一模块报告交叉核对。公开来源逐项读正文/表格，FlightLLM VHK158为模拟、Qwen速度含prefill、Hummingbird为短上下文B1均明确保留。外部整篇PDF SHA未封存，不能冒称已保存。

报告SHA256 a7d372418361d729d7f21590b880adaa9a78d79f44a60492b76ac1874177b7aa；JSON及输入SHA见同名JSON。新脚本及报告均UTF-8/LF，旧CSV/JSON/科学SHA不变。模型revision及原GPU实验环境仍以原科学8ea8d0f4的不可变manifest为准；不继承跨模型质量结论。

复核命令（两个源码根可不同，TLM源b516e1d9，GPU源8ea8d0f4及交付原件）：

```powershell
python work/rayggxia/212/benchmark_audit_20261030/build_audit.py --tlm-root <TLM结果根> --gpu-root <GPU结果根> --output <新的临时输出目录>
```

下一步：用户若授权新的存储消融，固定模型/B1/精度/资源只改通道或数据流；同资源全数字对照另存。不要重跑本轮封存健康作业。500MHz完整STA、局部供数/重叠消融、PHY/controller成本与质量匹配没有被本报告补齐。项目看板未操作，Issue/PR同步即可追踪，权限允许后可同步看板。

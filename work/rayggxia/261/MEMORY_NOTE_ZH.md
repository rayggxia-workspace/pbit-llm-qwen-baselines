# Issue261：真实FFN地址覆盖（2026-11-22）

已训练100M的Qwen3-4B T64/strat64，只读捕获第一个WT2 2048窗口、36层×16位置，每种信号576个完整向量，GU2560/Wd9728维。整窗logits逐位不变、9项历史切片核对通过。GPU6094约282秒；CPU6096仅启动路径失败，6099复用原分析快照完成；无遗留作业、无新PPL/训练/RTL/TLM。

理想IID categorical有放回地址采样、p∝输入幅度×真实W8解码权重范数时，K128唯一行覆盖GU4.71%/Wd1.26%；若必须命中即搬连续64行整组，则GU94.88%/Wd53.19%。K512逻辑行16.62%/4.66%，64行组约100%/91.18%。仅输入幅度概率的曲线接近。结论是行级并集尚稀疏，而粗组搬运很早稠密；64行组是条件布局，不是现有DMA实测。每地址一次与旧每拍多路Bernoulli不等价，不能由覆盖率继承旧PPL或声称节省整机能耗。新地址分布没有压成P8硬件阈值，P8只指输入信号接口。

入口experiments/ffn_address_coverage_20261122/REPORT_ZH.md；实现coverage.py、三seed核对和原始SHA在results/RESULTS.json。原始张量仅私有服务器ffn-address-coverage-issue261-20261122/result/capture.npz，SHA8213fdd53b66b9dded08e9e70a2fd4d2c2cd53e32f47c93d0d2c7b7ac7031c37。分支task/261-ffn-address-coverage；实际发布状态查work/rayggxia/261/PUBLICATION.json，勿称已合并。正式备忘录由Issue28统一集成此条，不覆盖现有并发更新。

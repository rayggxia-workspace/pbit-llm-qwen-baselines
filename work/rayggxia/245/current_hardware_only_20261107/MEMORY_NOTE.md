## 2026-11-07 Issue245：用户明确跨模型只做硬件时间/功耗，不需准确率基线

本阶段目的为Qwen3-4B、Llama3.2-3B-Instruct、DeepSeek-LLM-7B-Chat在当前概率硬件及等面积数字对照上的PPA/TLM，不要求下载权重、tokenizer、PPL、任务准确率或GPU基线；不取消其他已授权质量任务。CPU/EDA Slurm跑TLM即可。真实模型权重不是shape工作量的前置条件；数据依赖部分可使用明确标注的参考/合成轨迹与情景敏感性，不宣称真实文本功耗。

固定1001088KiB/6核与250960KiB/3核两种芯片，三模型改变层/矩阵/头/波数，不按模型复制面积。三模型×两频率×概率、BF16dense、W8dense、W8同SparQ准确PV＝24主配置。当前compile_current_hardware.py已生成CURRENT_WORKLOAD_PLAN.json，校验Llama3Q/KV、DeepSeek4波及33024B尺度元数据；只是工作量/执行清单，非完成仿真。旧67.5mm²解析预算保留历史来源，不能改名成当前结果。

Attention主表固定带SHA的参考驱动，screen数字与概率同候选；补集中/均匀/分散访问情景、随机三seed，实际记录提议/更新/有效样本及V去重命中，不将S64当64周期。静态FFN/投影/权重字节可直接算，onlineSoftmax重缩放与Ising采样延迟不能只凭shape认定。当前还须参数化Qwen硬编码、g/u及元数据地址、QK norm开关、小SRAM及数字共享池，单层门禁后再完整28/30/36层CPU任务。

正式model_scaling_20261106/CURRENT_HARDWARE_ONLY_ZH.md、compile_current_hardware.py及CURRENT_WORKLOAD_PLAN.json；配额/数字模块接口沿Issue236/PR244，不新造整机模拟器。250合格核PPA待收仍条件。当前无新TLM/GPU/训练/PPL/RTL/PT任务；Issue245/PR247交付见PUBLICATION.json，待审不合并，Projects待同步。

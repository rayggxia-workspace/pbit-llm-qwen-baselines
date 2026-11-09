# Issue245：硬件范围纠正与当前执行清单

负责人rayggxia，2026-11-07；复用task/245-cross-model-estimate / tmp/cross-model245-20261106，PR247 base main，远端起点8a1d4e4faa78b6478e62b3936f82deeb18476bce。本地原b8a83f8保持历史成果；新范围只做硬件PPA，先前“必须建立真实模型准确率基线”的建议已被用户明确排除。

交付CURRENT_HARDWARE_ONLY_ZH.md、shape/工作量编译器及24case清单；复用并包含Issue236当前workload.py/TARGETS.json两份同字节公共依赖。没有下载模型或执行任何新模型/TLM/GPU任务。旧estimate.py和原REPORT/CALIBRATION原字节不改，旧39.9/83.5ms属于原100MHz/2.5MiB/12核T64解析估计。

已验证编译器执行成功、24case、三模型身份/维度、Llama3Q/KV、DeepSeek4KV波/33024B元数据；返回latency/energy均为空，状态requires_parameterized_executing_adapter。没有声称当前Qwen构造器已经可跑新模型。

恢复命令：python -B architecture_tlm/model_scaling_20261106/compile_current_hardware.py --project <含当前公共helper及TARGETS的项目根> --out <新JSON>。实际代码/配置/输出SHA见SOURCE_MANIFEST.json。优先把当前数字/概率模块的Qwen硬编码改成shape参数、同物理资源下重排缓冲并处理Q/KV头掩码；每模型单层守恒后才提交24项CPU完整回放，默认不加PPL前置。

Attention输入用声明的参考/合成轨迹，不把Qwen实际分布当另外两模型真实分布；采样实际提议/输出时间戳和访问情景要计入。只做shape可确定的部分时输出下界/条件估计，不能称完整仿真。总/无head时间、面积、片上/外存能量、平均功率和计费边界需统一。

本轮不接管236数字适配或198/204模块源码，不改两版默认/250失败门禁，不取消其他健康作业。上传/逐内容回读以PUBLICATION.json为准，PR待审未合并；Projects待维护者同步。

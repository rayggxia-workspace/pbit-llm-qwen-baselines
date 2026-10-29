# Issue212 GPU decode测量交接

负责人：rayggxia；分支task/212-gpu-decode-profile；PR base为main `787489192ebfcdb61ad72edde406818f450aa3dc`。本地目录为tmp/gpu-decode-issue212-20261029。

Slurm3389预检、3398真实模型门禁、3399正式测量均完成。无运行中作业，不重跑已完成测量。GPU结果目录 `results/gpu_decode_energy_20261029/`，执行代码 `experiments/gpu_decode_energy_20261029/`。模型为Qwen/Qwen3-4B后训练版revision1cfa9a7208912126459214e8b04321603b3df60c，B1/BF16/SDPA，2K/8K各三次；未做PPL或训练。

服务器任务存储相对本人HOME：`projects/pbit-qwen3-gpu-decode-energy-20261029-issue212/`；冻结源码在 `snapshots/7911a0aff763f0dc/`，封存结果在 `results/formal_7911a0aff763f0dc/`。日志在logs/。运行环境只读复用Issue136 venv，模型/准备清单只读复用Issue158；不复制或清理它们。不要公开SSH配置/凭据；连接沿用本地已有授权配置。

真实执行源码Git提交 `20d46ec7f04021e90bba42312681ad4f7bbe81ee`。后续仅修复Profiler汇总选择：Kineto同名CPU范围和CUDA注释范围不可混用，正式报告选CPU范围关联的kernel总时间。原始TIME_PROFILE保留双行，原始JSON和SHA不变；未来entrypoint已显式过滤CPU类型。PUBLICATION记录新版汇总源码SHA。

2K原生decode25.720ms/token、5931.5mJ/token、230.6W；固定forward25.607ms/5196.9mJ；CUDA Graph固定forward10.531ms/3927.7mJ。8K原生25.756ms/8437.8mJ、327.6W；Graph固定forward16.774ms/7823.2mJ。固定forward不含argmax/上下文增长，不是完整生成。

GPU模块延时是Profiler核时间；模块能量是全36层同类操作隔离回放，不能相加或冒充原生独立轨能量。Embedding/最终Norm窗口约0.5/1秒，能量低置信，其余主要模块约5秒三次。FlashAttention已观测。四个大trace/安装源码文件留服务器，manifest有路径/大小/SHA，下载43个小文件479702字节并核验全部远端文件。

CPU验证：在代码目录运行 `python -m unittest test_meter test_report`，8项通过。重建报告：`python build_report.py --raw ../../results/gpu_decode_energy_20261029/raw --output /new/report --tlm ../../results/gpu_decode_energy_20261029/TLM_REFERENCE.json`。禁止直接改封存数据。源码/配置/数据/结果SHA见PROVENANCE、COMPLETED、ARTIFACT_MANIFEST和PUBLICATION。

2K TLM为FMA2候选，57.445ms、片上已计价92.989mJ＋片外旧代理354.212mJ；完整校准能量未知，质量未匹配。不是Ising路径。不修复其他任务/PR211的容量评审项，不合并本PR。8K同版本TLM配对待后续任务。

本次代码/小结果准备通过同一PR交付；PR实际创建与远端状态以Issue212最新评论为准，未合并不关闭Issue。长期备忘录只做本地增量同步，未重传此前自动审查拒绝的整份历史文档；远端恢复依据本交接和Issue212。

发布传输：Git CLI连接被重置，改用核验账号rayggxia的GitHub连接器。执行源码远端20d46ec7f04021e90bba42312681ad4f7bbe81ee与本地归档1828e300f9b7ba548b04f8139d03ed26e911d5f0的Git树相同（ec80ecd22f9f326f76052c243b499465be0d9b42）。后续从远端任务分支恢复，不向其强推本地分叉历史。

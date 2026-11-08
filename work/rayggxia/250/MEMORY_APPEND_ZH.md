## 2026-11-08 Issue250：用户确认最终Qwen3质量清单

用户确认经典六项（PIQA/HellaSwag/WinoGrande/BoolQ/ARC-E/ARC-C）＋完整MMLU＋LAMBADA，另GSM8K生成与完整WT2 PPL；WiC/ANLI-r2可选，College CS/Int.law/Jurisprudence由完整MMLU覆盖。正式文件architecture_tlm/paper_figure_references_20261108/QWEN3_ACCURACY_BENCHMARK_PLAN_ZH.md；同目录README新增Fig.9入口，更新早先“两项代表任务”的最终覆盖建议。Fig.8保持空。

shot/模板/thinking/生成预算待执行前冻结；按最终检查点核BF16与联合方案、计分token实际随机路径、prefill/decode作用范围、真实源与有限精度、模型/文本SHA。旧单seed授权不自动扩三seed。文件是清单而非完成结果，无新GPU/Slurm/模型/TLM/EDA。接续PR251（待审未合并），回执work/rayggxia/250/BENCHMARK_PUBLICATION.json。唯一记忆由Issue28维护者接入，不编辑其并发工作树。

## 2026-11-08 Issue250 白板九张论文图的原图参考

用户给Fig.1–10白板并要求逐图找原文绘制参考，补充明确Fig.8暂时留空。已对11篇一手论文37处图/页进行图像与caption核对，43项文档/定位检查通过。主文件architecture_tlm/paper_figure_references_20261108/README_ZH.md含逐图速查、具体借鉴与改绘建议；SOURCES.json保留PDF SHA。重点p-bit原理→SOFA/Tender整机→LeOPArd/SparQ Attention→Ising/ASCEND非线性→DS-CIM/FIGNA FFN→SCIM成本→质量与整机收益。

不上传白板/PDF/截图，不改198/204/225实现或默认，无新模型、PPL、TLM、RTL、EDA。Fig.9第二模型字迹有划改，不擅自固定；Fig.10同一ASIC面积按配置统计。FIGNA Fig.13不含SRAM、Fig.17含SRAM已明确。分支task/250-figure-references-20261108，最小工作目录tmp/figure-references-issue250-20261108，base main206bf81；实际发布SHA/PR见该任务PUBLICATION.json，待审不当已合并。唯一记忆维护目录有其他增量，本摘要供单一维护任务接入。
